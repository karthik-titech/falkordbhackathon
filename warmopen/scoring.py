"""One abstract JEV decision with graph-sourced explanations."""

import math
import re

from .agentlog import log
from .broker import revealed_route
from .features import _public_evidence, extract_features, gaps
from .paths import public_paths
from .requests import get_request

FIT_CHOICES = ("high", "medium", "low", "INSUFFICIENT_EVIDENCE")
_INSTRUCTIONS = {
    "invest": "Would this fund partner take a first meeting with the requester?",
    "sales": "Would this buyer take a 20-minute call with the requester?",
}
_CRITERIA = {
    "invest": {
        "high": "High fit for a first meeting based on stage match, sector overlap, public evidence, topics and warm routes.",
        "medium": "Mixed fit for a first meeting based on stage match, sector overlap, public evidence, topics and warm routes.",
        "low": "Low fit for a first meeting based on stage match, sector overlap, public evidence, topics and warm routes.",
        "INSUFFICIENT_EVIDENCE": "The abstract facts do not support a first-meeting fit decision.",
    },
    "sales": {
        "high": "High fit for a 20-minute call based on product-category match with company needs, public evidence, topics and warm routes.",
        "medium": "Mixed fit for a 20-minute call based on product-category match with company needs, public evidence, topics and warm routes.",
        "low": "Low fit for a 20-minute call based on product-category match with company needs, public evidence, topics and warm routes.",
        "INSUFFICIENT_EVIDENCE": "The abstract facts do not support a 20-minute-call fit decision.",
    },
}
_INTRODUCER_CRITERIA = {
    "public": "Use this public warm route; prefer fewer hops.",
    "revealed": "Use this approved revealed warm route; prefer fewer hops and higher minimum tie strength.",
    "APPROACH_DIRECTLY": "Approach directly when no warm route is available.",
    "INSUFFICIENT_EVIDENCE": "Abstain when the abstract facts do not support a route decision.",
}
_ABSTRACT_LABEL = re.compile(r"(?:invest|sales|public|revealed|public_\d+|revealed_\d+)\Z")


def _abstract(value):
    if isinstance(value, dict):
        return all(_abstract(item) for item in value.values())
    if isinstance(value, list):
        return all(_abstract(item) for item in value)
    if value is None or type(value) is bool:
        return True
    if type(value) in (int, float):
        return math.isfinite(value)
    return isinstance(value, str) and _ABSTRACT_LABEL.fullmatch(value) is not None


def build_payload(features, choices):
    """Build fixed criteria-map questions from abstract features and ordered choices."""
    expected = [route["route_id"] for route in features["routes"]]
    expected += ["APPROACH_DIRECTLY", "INSUFFICIENT_EVIDENCE"]
    if not _abstract(features) or list(choices) != expected:
        raise ValueError("JEV requires abstract features and fixed route choices")
    goal = features["goal"]
    introducer_criteria = {route["route_id"]: _INTRODUCER_CRITERIA[route["kind"]]
                           for route in features["routes"]}
    introducer_criteria.update({choice: _INTRODUCER_CRITERIA[choice]
                               for choice in ("APPROACH_DIRECTLY", "INSUFFICIENT_EVIDENCE")})
    return {
        "model": "jev-latest", "state": features,
        "questions": {
            "fit": {"type": "choice", "instructions": _INSTRUCTIONS[goal],
                    "criteria": _CRITERIA[goal].copy()},
            "introducer": {
                "type": "choice",
                "instructions": "Select one available route, APPROACH_DIRECTLY, or INSUFFICIENT_EVIDENCE.",
                "criteria": introducer_criteria,
            },
        },
    }


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _validate(answer):
    fit = answer["answers"]["fit"]
    intro = answer["answers"]["introducer"]
    if fit["choice"] not in FIT_CHOICES or not isinstance(intro["choice"], str):
        raise ValueError("Invalid decision choice")
    for decision in (fit, intro):
        confidence = decision["confidence"]
        if not _finite_number(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Invalid decision confidence")
    weights = [fit["probabilities"][band] for band in ("high", "medium", "low")]
    if any(not _finite_number(weight) or weight < 0 for weight in weights):
        raise ValueError("Invalid fit weights")
    total = sum(weights)
    if not math.isfinite(total) or total == 0:
        raise ValueError("Empty or invalid fit weights")
    return fit, intro, weights, total


def _introducer(store, request_id, request, choice, include_own=False):
    if choice == "APPROACH_DIRECTLY":
        return {"route_id": choice, "via": None}
    if choice == "INSUFFICIENT_EVIDENCE":
        return None
    if choice.startswith("public_"):
        for route in public_paths(store, request["requester"], request["target"],
                                  include_own=include_own):
            if route["route_id"] == choice:
                return {"route_id": choice, "via": route["persons"][1]}
    if choice.startswith("revealed_"):
        route = revealed_route(store, request_id)
        if route and route["route_id"] == choice:
            return {"route_id": choice, "via": route["persons"][0]}
    return None


def score_fit(store, request_id, jev, min_confidence=0.6, include_own=False):
    """Score once, reject malformed answers, and retain graph reasons on abstention."""
    request = get_request(store, request_id)
    features = extract_features(store, request_id, include_own=include_own)
    routes = public_paths(store, request["requester"], request["target"],
                          include_own=include_own)
    evidence = _public_evidence(store, request, routes)
    missing = gaps(store, request_id, include_own=include_own)
    # Deterministic improvement: address the first gap in the contract's order.
    improvement = [{"text": "Resolve this evidence gap: " + missing[0]["text"]}] if missing else []
    result = {
        "label": "uncalibrated fit", "band": None, "value": None,
        "confidence": None, "abstained": True, "reason": "jev_unavailable",
        "introducer": None,
        "supports": [{"text": item["claim"], "evidence_id": item["id"]}
                     for item in evidence if item.get("claim")][:2],
        "against": [{"text": gap["text"], "gap_id": gap["id"]} for gap in missing[:1]],
        "would_improve": improvement,
    }
    choices = [route["route_id"] for route in features["routes"]]
    choices += ["APPROACH_DIRECTLY", "INSUFFICIENT_EVIDENCE"]
    try:
        fit, intro, weights, total = _validate(jev(build_payload(features, choices)))
    except Exception:
        # Provider errors and malformed answers expose no provider text to callers.
        pass
    else:
        result["confidence"] = fit["confidence"]
        result["introducer"] = _introducer(store, request_id, request, intro["choice"],
                                           include_own=include_own)
        if fit["choice"] == "INSUFFICIENT_EVIDENCE":
            result["reason"] = "insufficient_evidence"
        elif fit["confidence"] < min_confidence:
            result["reason"] = "low_confidence"
        else:
            result.update(abstained=False, reason=None, band=fit["choice"],
                          value=round((weights[0] + 0.5 * weights[1]) / total, 2))
    log(store, request_id, "scorer", "fit_scored")
    return result
