"""ptc2 frozen contract: features, gaps, JEV fit scoring, sourced openers.

Source: specs.ptc/ptc2-score-openers.spec.txt; joint debate fold-ins 2026-10-23
(uncalibrated fit label, abstention, one JEV call, cited openers only).
"""
import json
import re

import pytest

from conftest import HIDDEN_IDS

ALLOWED_STR = re.compile(r"^(invest|sales|public|revealed|public_\d+|revealed_\d+)$")


def _leaves(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _leaves(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _leaves(v)
    else:
        yield obj


class FakeJEV:
    def __init__(self, fit_choice="high", confidence=0.8, intro="public_1", raises=False,
                 probs=None):
        self.calls = []
        self.fit_choice, self.confidence, self.intro, self.raises = fit_choice, confidence, intro, raises
        self.probs = probs or {"high": 0.7, "medium": 0.2, "low": 0.05, "INSUFFICIENT_EVIDENCE": 0.05}

    def __call__(self, payload):
        self.calls.append(payload)
        if self.raises:
            raise TimeoutError("jev down")
        return {"model": "jev-test", "answers": {
            "fit": {"choice": self.fit_choice, "confidence": self.confidence, "probabilities": self.probs},
            "introducer": {"choice": self.intro, "confidence": 0.7, "probabilities": {self.intro: 0.7}},
        }}


def _invest_request(store):
    from warmopen.requests import create_request

    return create_request(store, "me", "vc_kay", "invest")


def _sales_request(store):
    from warmopen.requests import create_request

    return create_request(store, "me", "eng_lee", "sales")


# T2 features and gaps

def test_features_are_abstract_only(loaded):
    from warmopen.features import extract_features

    feats = extract_features(loaded, _invest_request(loaded))
    for leaf in _leaves(feats):
        if isinstance(leaf, str):
            assert ALLOWED_STR.match(leaf), leaf
        else:
            assert leaf is None or isinstance(leaf, (int, float, bool)), leaf
    text = json.dumps(feats)
    for banned in ("vc_kay", "owner_a", "me\"", "http", "Kay"):
        assert banned not in text


def test_invest_features_and_gaps(loaded):
    from warmopen.features import extract_features, gaps

    rid = _invest_request(loaded)
    feats = extract_features(loaded, rid)
    assert feats["goal"] == "invest"
    assert feats["best_public_hops"] == 2
    assert feats["stage_match"] is False
    assert feats["sector_overlap_count"] == 1
    assert feats["category_match"] is None
    assert [g["id"] for g in gaps(loaded, rid)] == ["gap_stage"]
    assert feats["gaps_count"] == 1


def test_sales_features_and_gaps(loaded):
    from warmopen.features import extract_features, gaps

    rid = _sales_request(loaded)
    feats = extract_features(loaded, rid)
    assert feats["category_match"] is True
    assert feats["stage_match"] is None
    assert feats["public_route_count"] == 0
    assert [g["id"] for g in gaps(loaded, rid)] == ["gap_no_warm_route"]


# T3 scoring

def test_fit_value_band_and_single_call(loaded):
    from warmopen.scoring import score_fit

    jev = FakeJEV()
    out = score_fit(loaded, _invest_request(loaded), jev)
    assert len(jev.calls) == 1
    assert set(out) == {"label", "band", "value", "confidence", "abstained", "reason",
                        "introducer", "supports", "against", "would_improve"}
    assert out["label"] == "uncalibrated fit"
    assert out["abstained"] is False and out["reason"] is None
    assert out["band"] == "high"
    assert out["value"] == 0.84
    assert out["introducer"] == {"route_id": "public_1", "via": "owner_a"}
    assert "probability" not in json.dumps(out)


def test_jev_payload_state_is_the_abstract_features(loaded):
    from warmopen.features import extract_features
    from warmopen.scoring import score_fit

    rid = _invest_request(loaded)
    jev = FakeJEV()
    score_fit(loaded, rid, jev)
    assert jev.calls[0]["state"] == extract_features(loaded, rid)


@pytest.mark.parametrize("kwargs,reason", [
    ({"fit_choice": "INSUFFICIENT_EVIDENCE"}, "insufficient_evidence"),
    ({"confidence": 0.4}, "low_confidence"),
    ({"raises": True}, "jev_unavailable"),
])
def test_abstains_honestly(loaded, kwargs, reason):
    from warmopen.scoring import score_fit

    out = score_fit(loaded, _invest_request(loaded), FakeJEV(**kwargs))
    assert out["abstained"] is True
    assert out["reason"] == reason
    assert out["band"] is None and out["value"] is None
    assert out["label"] == "uncalibrated fit"
    assert isinstance(out["supports"], list) and isinstance(out["against"], list)


def test_unknown_introducer_choice_is_dropped(loaded):
    from warmopen.scoring import score_fit

    out = score_fit(loaded, _invest_request(loaded), FakeJEV(intro="owner_a"))
    assert out["introducer"] is None


def test_reasons_cite_graph_and_stay_short(loaded):
    from warmopen.scoring import score_fit

    out = score_fit(loaded, _invest_request(loaded), FakeJEV())
    assert 1 <= len(out["supports"]) <= 2
    assert all(s["evidence_id"] and s["evidence_id"] != "ev_private_b" for s in out["supports"])
    assert len(out["against"]) <= 1
    assert out["against"] and out["against"][0]["gap_id"] == "gap_stage"
    assert len(out["would_improve"]) <= 1


def test_revealed_route_is_offered_to_jev(loaded):
    from warmopen.broker import reachability, reveal
    from warmopen.consent import grant
    from warmopen.features import extract_features
    from warmopen.scoring import score_fit

    rid = _sales_request(loaded)
    grant(loaded, "owner_b", "tok-b", "me", rid, "reachability")
    offer = reachability(loaded, "owner_b", rid)["offer_id"]
    grant(loaded, "owner_b", "tok-b", "me", rid, "reveal")
    reveal(loaded, "owner_b", rid, offer)
    feats = extract_features(loaded, rid)
    assert feats["revealed"] is True and feats["revealed_hops"] == 2
    assert feats["revealed_min_tie"] == 0.741
    assert {"route_id": "revealed_1", "hops": 2, "min_tie": 0.741, "kind": "revealed"} in feats["routes"]
    for hidden in HIDDEN_IDS:
        assert hidden not in json.dumps(feats)
    out = score_fit(loaded, rid, FakeJEV(intro="revealed_1"))
    assert out["introducer"] == {"route_id": "revealed_1", "via": "owner_b"}


# T4 openers

def _llm_returning(items):
    def llm(prompt):
        return json.dumps(items)
    return llm


def test_openers_keep_only_cited_public_cues(loaded):
    from warmopen.openers import generate_openers

    rid = _invest_request(loaded)
    llm = _llm_returning([
        {"text": "Your talk on funding agent infrastructure matched our roadmap.", "evidence_id": "ev_talk_kay"},
        {"text": "Leaked private context", "evidence_id": "ev_private_b"},
        {"text": "Made up", "evidence_id": "ev_does_not_exist"},
        {"text": "x" * 281, "evidence_id": "ev_fund_thesis"},
    ])
    out = generate_openers(loaded, rid, llm)
    assert len(out) == 3
    assert out[0] == {"text": "Your talk on funding agent infrastructure matched our roadmap.",
                      "evidence_id": "ev_talk_kay", "url": "https://example.org/aie/kay", "source": "llm"}
    assert all(o["evidence_id"] != "ev_private_b" for o in out)
    assert [o["source"] for o in out[1:]] == ["template", "template"]
    assert len({o["evidence_id"] for o in out}) == 3
    for o in out:
        assert o["url"] and o["url"].startswith("https://example.org/")


def test_openers_fall_back_when_llm_fails(loaded):
    from warmopen.agentlog import events
    from warmopen.openers import generate_openers

    rid = _invest_request(loaded)

    def broken(prompt):
        raise RuntimeError("llm down")

    out = generate_openers(loaded, rid, broken)
    assert len(out) == 3 and all(o["source"] == "template" for o in out)
    assert ("writer", "openers_written") in [(e["agent"], e["action"]) for e in events(loaded, rid)]


def test_opener_prompt_has_no_private_evidence(loaded):
    from warmopen.openers import generate_openers

    rid = _sales_request(loaded)
    seen = []

    def llm(prompt):
        seen.append(prompt)
        return "not json"

    generate_openers(loaded, rid, llm)
    assert seen and "ev_private_b" not in seen[0] and "Carol" not in seen[0]
