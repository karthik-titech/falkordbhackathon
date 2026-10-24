"""OpenAI Decisions API adapter for abstract conference-fit choices."""

import json
import math
import re
from urllib.request import Request, urlopen


API_URL = "https://api.openai.com/v1/decisions"
MODEL = "gpt-6-luna"
_LEGACY_MODEL = "jev-latest"
_CONVERSATION_MODEL = "conference-conversation-v1"
_QUESTION_NAMES = ("fit", "introducer", "cue_type", "next_action")
_TIMING_LABELS = {"current", "future", "past_or_unknown"}
_BASE_STATE_KEYS = {
    "goal", "public_route_count", "best_public_hops", "revealed",
    "revealed_hops", "revealed_min_tie", "shared_work_links",
    "co_speaker_links", "coauthor_links", "topic_overlap_count",
    "seeking_overlap_count", "met_before", "has_portfolio_news",
    "team_member_present", "has_stated_interest", "stage_match",
    "sector_overlap_count", "category_match", "evidence_count",
    "gaps_count", "routes",
}
_PLANNER_STATE_KEYS = {"conference_timing", "target_confirmed", "route_count"}
_PLANNER_ONLY_KEYS = {"goal", "conference_timing", "target_confirmed", "route_count", "routes"}
_PLANNER_ROUTE_KEYS = {
    "route_id", "hops", "supported_edge_count", "confirmed_attendance_count",
}
_COUNT_FIELDS = (
    "public_route_count", "shared_work_links", "co_speaker_links",
    "coauthor_links", "topic_overlap_count", "seeking_overlap_count",
    "evidence_count", "gaps_count",
)
_BOOL_FIELDS = (
    "revealed", "met_before", "has_portfolio_news", "team_member_present",
    "has_stated_interest",
)
_ABSTRACT_BOOL_FIELDS = ("stage_match", "category_match")
_CONVERSATION_STATE_KEYS = {
    "topic_overlap_count", "seeking_overlap_count", "cited_route_count", "best_hops",
    "supported_edge_count", "professional_evidence_count", "source_listed", "target_listed",
    "public_context_count", "public_context_match_count", "opener_candidates", "mentions",
}
_CONVERSATION_COUNTS = {
    "topic_overlap_count", "seeking_overlap_count", "cited_route_count",
    "supported_edge_count", "professional_evidence_count", "public_context_count",
    "public_context_match_count",
}
_CONVERSATION_FIT_CHOICES = ("high", "medium", "low", "INSUFFICIENT_EVIDENCE")
_CONNECTION_CHOICES = ("mirror", "missing_piece", "unexpected_connection", "unknown")
_OPENER_STYLES = {"public_talk", "shared_topic", "public_route", "public_context"}
_MENTION_COUNTS = {
    "professional_mention_count", "positive_mention_count", "neutral_mention_count",
    "critical_mention_count", "unclear_mention_count", "recent_mention_count",
    "mention_source_count",
}
_MENTION_KEYS = _MENTION_COUNTS | {"mentions_available"}


def _invalid():
    raise ValueError("Invalid abstract decision payload")


def _finite(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _validate_state(state):
    if type(state) is not dict:
        _invalid()
    keys = set(state)
    if not _BASE_STATE_KEYS <= keys or keys - (_BASE_STATE_KEYS | _PLANNER_STATE_KEYS):
        _invalid()
    if keys & _PLANNER_STATE_KEYS and not _PLANNER_STATE_KEYS <= keys:
        _invalid()
    if state["goal"] not in ("invest", "sales"):
        _invalid()
    for key in _COUNT_FIELDS:
        if type(state[key]) is not int or state[key] < 0:
            _invalid()
    for key in _BOOL_FIELDS:
        if type(state[key]) is not bool:
            _invalid()
    for key in _ABSTRACT_BOOL_FIELDS:
        if state[key] is not None and type(state[key]) is not bool:
            _invalid()
    for key in ("best_public_hops", "revealed_hops"):
        value = state[key]
        if value is not None and (type(value) is not int or not 1 <= value <= 6):
            _invalid()
    sector_overlap = state["sector_overlap_count"]
    if sector_overlap is not None and (type(sector_overlap) is not int or sector_overlap < 0):
        _invalid()
    tie = state["revealed_min_tie"]
    if tie is not None and (not _finite(tie) or not 0 <= tie <= 1):
        _invalid()
    if _PLANNER_STATE_KEYS <= keys:
        if (state["conference_timing"] not in _TIMING_LABELS
                or type(state["target_confirmed"]) is not bool
                or type(state["route_count"]) is not int or state["route_count"] < 0):
            _invalid()

    routes = state["routes"]
    if type(routes) is not list:
        _invalid()
    route_ids = []
    public_hops = []
    revealed_route = None
    for route in routes:
        if type(route) is not dict:
            _invalid()
        legacy_fields = {"route_id", "hops", "min_tie", "kind"}
        if set(route) != legacy_fields:
            _invalid()
        route_id, hops, route_tie, kind = (route["route_id"], route["hops"],
                                           route["min_tie"], route["kind"])
        if (not isinstance(route_id, str)
                or not re.fullmatch(r"(?:public|revealed)_[0-9]+", route_id)
                or type(hops) is not int or not 1 <= hops <= 6
                or kind not in ("public", "revealed")):
            _invalid()
        if (route_id.startswith("public_") and kind != "public"
                or route_id.startswith("revealed_") and kind != "revealed"
                or route_id in route_ids):
            _invalid()
        if route_tie is not None and (not _finite(route_tie) or not 0 <= route_tie <= 1):
            _invalid()
        if kind == "public":
            public_hops.append(hops)
        else:
            if revealed_route is not None:
                _invalid()
            revealed_route = route
        route_ids.append(route_id)

    if state["public_route_count"] != len(public_hops):
        _invalid()
    expected_best = min(public_hops) if public_hops else None
    if state["best_public_hops"] != expected_best:
        _invalid()
    if state["revealed"] != (revealed_route is not None):
        _invalid()
    if revealed_route is None:
        if state["revealed_hops"] is not None or state["revealed_min_tie"] is not None:
            _invalid()
    elif (state["revealed_hops"] != revealed_route["hops"]
          or state["revealed_min_tie"] != revealed_route["min_tie"]):
        _invalid()
    return route_ids


def _api_question(name, question):
    choices = [
        {"value": label, "description": description}
        for label, description in question["criteria"].items()
    ]
    if not 2 <= len(choices) <= 255:
        _invalid()
    return {
        "type": "choice",
        "name": name,
        "instructions": question["instructions"],
        "choices": choices,
    }


def _planner_questions(payload):
    state = payload["state"]
    if type(state) is not dict or set(state) != _PLANNER_ONLY_KEYS:
        _invalid()
    if (state["goal"] not in ("invest", "sales")
            or state["conference_timing"] not in _TIMING_LABELS
            or type(state["target_confirmed"]) is not bool
            or type(state["route_count"]) is not int or state["route_count"] < 0
            or type(state["routes"]) is not list
            or state["route_count"] != len(state["routes"])):
        _invalid()
    route_ids = []
    for route in state["routes"]:
        if type(route) is not dict or set(route) != _PLANNER_ROUTE_KEYS:
            _invalid()
        if (not isinstance(route["route_id"], str)
                or not re.fullmatch(r"route_[0-9]+", route["route_id"])
                or route["route_id"] in route_ids
                or type(route["hops"]) is not int or not 1 <= route["hops"] <= 6
                or type(route["supported_edge_count"]) is not int
                or route["supported_edge_count"] < 0
                or type(route["confirmed_attendance_count"]) is not int
                or route["confirmed_attendance_count"] < 0):
            _invalid()
        route_ids.append(route["route_id"])
    criteria = {
        route_id: "Choose this supported route using fewer hops and confirmed attendance."
        for route_id in route_ids
    }
    criteria.update({
        "APPROACH_DIRECTLY": "Use no route.",
        "INSUFFICIENT_EVIDENCE": "Abstain from choosing a route.",
    })
    expected = {"route": {
        "type": "choice",
        "instructions": "Select one fixed route label, APPROACH_DIRECTLY, or INSUFFICIENT_EVIDENCE.",
        "criteria": criteria,
    }}
    if payload["questions"] != expected:
        _invalid()
    return [_api_question("route", expected["route"])]


def _conversation_expected(state):
    fit_criteria = {
        "high": "Several cited features support the choice.",
        "medium": "Some cited features support the choice.",
        "low": "The cited basis is limited.",
        "INSUFFICIENT_EVIDENCE": "Abstain because the evidence is insufficient.",
    }
    category_criteria = {
        "mirror": "The fixed topic overlap features support this label.",
        "missing_piece": "The fixed seeking overlap features support this label.",
        "unexpected_connection": "The fixed cited-route features support this label.",
        "unknown": "No category is supported by the fixed features.",
    }
    opener_criteria = {
        row["candidate_id"]: "Rank this anonymous source-backed opener candidate."
        for row in state["opener_candidates"]
    }
    opener_criteria["INSUFFICIENT_EVIDENCE"] = "Abstain from ranking an opener."
    questions = {}
    for name in ("conversation_fit", "mirror_fit", "missing_piece_fit",
                 "unexpected_connection_fit"):
        questions[name] = {
            "type": "choice",
            "instructions": ("Choose a fixed fit level using only numeric and boolean public-evidence features. "
                             "Professional mention tone is weak context only; do not infer reputation, "
                             "personality, intent, or success probability from it."),
            "criteria": fit_criteria,
        }
    questions["connection_type"] = {
        "type": "choice",
        "instructions": ("Use this precedence: missing_piece when seeking_overlap_count is positive; "
                         "otherwise mirror when topic_overlap_count is positive; otherwise "
                         "unexpected_connection when cited_route_count is positive; otherwise unknown."),
        "criteria": category_criteria,
    }
    questions["opener"] = {
        "type": "choice",
        "instructions": "Choose one anonymous candidate using only its abstract style and support features.",
        "criteria": opener_criteria,
    }
    return {"model": _CONVERSATION_MODEL, "state": state, "questions": questions}


def conversation_payload(state):
    """Build the closed, abstract schema used by the conversation decision."""
    if type(state) is not dict or set(state) != _CONVERSATION_STATE_KEYS:
        _invalid()
    for key in _CONVERSATION_COUNTS:
        if type(state[key]) is not int or state[key] < 0:
            _invalid()
    mentions = state["mentions"]
    if (type(mentions) is not dict or set(mentions) != _MENTION_KEYS
            or type(mentions["mentions_available"]) is not bool):
        _invalid()
    for key in _MENTION_COUNTS:
        if type(mentions[key]) is not int or mentions[key] < 0:
            _invalid()
    if (state["best_hops"] is not None
            and (type(state["best_hops"]) is not int or not 1 <= state["best_hops"] <= 6)):
        _invalid()
    if type(state["source_listed"]) is not bool or type(state["target_listed"]) is not bool:
        _invalid()
    candidates = state["opener_candidates"]
    if type(candidates) is not list or len(candidates) > 3:
        _invalid()
    expected_ids = [f"candidate_{number}" for number in range(1, len(candidates) + 1)]
    for candidate in candidates:
        if (type(candidate) is not dict
                or set(candidate) != {"candidate_id", "cited", "topic_match_count", "style"}
                or candidate["candidate_id"] not in expected_ids
                or type(candidate["cited"]) is not bool
                or type(candidate["topic_match_count"]) is not int
                or candidate["topic_match_count"] < 0
                or candidate["style"] not in _OPENER_STYLES):
            _invalid()
    if [candidate["candidate_id"] for candidate in candidates] != expected_ids:
        _invalid()
    return _conversation_expected(state)


def _conversation_questions(payload):
    expected = conversation_payload(payload["state"])
    if payload != expected:
        _invalid()
    return [_api_question(name, question) for name, question in expected["questions"].items()]


def _wire_payload(payload):
    """Validate either internal choice contract, then translate to API schema."""
    if (type(payload) is not dict or set(payload) != {"model", "state", "questions"}
            or type(payload["state"]) is not dict):
        _invalid()
    if payload["model"] == _CONVERSATION_MODEL:
        questions = _conversation_questions(payload)
        state = payload["state"]
        return {
            "model": MODEL,
            "input": [{"role": "user", "content": [{"type": "input_json", "data": state}]}],
            "questions": questions,
        }
    if payload["model"] != _LEGACY_MODEL:
        _invalid()
    state = payload["state"]
    if _BASE_STATE_KEYS <= set(state):
        route_ids = _validate_state(state)
        choice_values = route_ids + ["APPROACH_DIRECTLY", "INSUFFICIENT_EVIDENCE"]

        # Rebuild the fixed questions so caller-supplied prompts or options cannot
        # add profile text, identifiers, URLs, or arbitrary choice labels.
        from .scoring import build_payload

        expected = build_payload(state, choice_values)
        if payload != expected:
            _invalid()
        questions = [_api_question(name, payload["questions"][name])
                     for name in _QUESTION_NAMES]
    elif set(state) == _PLANNER_ONLY_KEYS:
        questions = _planner_questions(payload)
    else:
        _invalid()
    return {
        "model": MODEL,
        "input": [{"role": "user", "content": [{"type": "input_json", "data": state}]}],
        "questions": questions,
    }


def _probability(value):
    return _finite(value) and 0 <= value <= 1


def _normalize_response(response, payload):
    """Convert named API choice answers into the scorer's existing answer map."""
    if type(response) is not dict or type(response.get("answers")) is not list:
        raise ValueError("Invalid decision response")
    criteria_by_name = {
        name: question["criteria"] for name, question in payload["questions"].items()
    }
    seen = set()
    normalized = {}
    for answer in response["answers"]:
        if type(answer) is not dict or not isinstance(answer.get("name"), str):
            raise ValueError("Invalid decision response")
        name = answer["name"]
        if name not in criteria_by_name or name in seen:
            raise ValueError("Invalid decision response")
        seen.add(name)
        if answer.get("type") == "refusal":
            if set(answer) != {"type", "name"}:
                raise ValueError("Invalid decision response")
            continue
        if (set(answer) != {"type", "name", "choice", "confidence", "probabilities"}
                or answer["type"] != "choice"):
            raise ValueError("Invalid decision response")
        criteria = criteria_by_name[name]
        choice, confidence = answer["choice"], answer["confidence"]
        if (not isinstance(choice, str) or choice not in criteria
                or not _probability(confidence)
                or type(answer["probabilities"]) is not list):
            raise ValueError("Invalid decision response")
        probabilities = {}
        for entry in answer["probabilities"]:
            if type(entry) is not dict or set(entry) != {"value", "probability"}:
                raise ValueError("Invalid decision response")
            label, probability = entry["value"], entry["probability"]
            if (not isinstance(label, str) or label not in criteria
                    or label in probabilities or not _probability(probability)):
                raise ValueError("Invalid decision response")
            probabilities[label] = probability
        if set(probabilities) != set(criteria) or sum(probabilities.values()) <= 0:
            raise ValueError("Invalid decision response")
        normalized[name] = {
            "choice": choice,
            "confidence": confidence,
            "probabilities": probabilities,
        }
    if seen != set(criteria_by_name):
        raise ValueError("Invalid decision response")
    return {"model": MODEL, "answers": normalized}


def decisions_client(api_key, timeout=8.0):
    """Return a callable; construction performs no network I/O."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("A Decisions API key is required")
    if not _finite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be a positive finite number")

    def decide(payload):
        wire = _wire_payload(payload)
        request = Request(
            API_URL,
            data=json.dumps(wire, allow_nan=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + api_key,
                     "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
        return _normalize_response(result, payload)

    return decide
