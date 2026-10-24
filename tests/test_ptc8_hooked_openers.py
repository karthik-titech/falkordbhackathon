"""ptc8 frozen contract: hooked openers for investors and buyers.

Source: Karthik 2026-10-24: "If founder F is looking for an angel in AI security
and VC V fits, find what V invested in (unicorn U) and open with: Hey, I am
founder F. Nice to meet you. Did you see the news about U? Great company! Do
you know if someone from their team is here?" Graph multi-hop: target ->
PARTNER_AT -> Fund -> INVESTED_IN -> Company <- WORKS_AT <- speaker. JEV picks
the hook (cue_type portfolio_news) from booleans only. Facts come from company
news and self-published bios with source URLs; never personal social feeds.
"""
import copy
import json

import pytest

from conftest import HIDDEN_TEXT


def _hooked_seed(seed, with_member=True):
    data = copy.deepcopy(seed)
    data["companies"].append({"id": "c_port", "name": "Port Co", "needs": [], "evidence": None})
    data["evidence"].append({"id": "ev_port_news", "url": "https://example.org/news/port-co-series-a",
                             "claim": "Kay Ventures led Port Co's Series A", "observed_at": "2026-10-24",
                             "visibility": "public"})
    data["edges"].append({"type": "INVESTED_IN", "from": "f_kay", "to": "c_port", "round": "Series A",
                          "lead": True, "evidence": "ev_port_news"})
    if with_member:
        data["people"].append({"id": "pm_port", "name": "Pat Member", "handle": "pat", "kind": "speaker",
                               "consented": False})
        data["talks"].append({"id": "t_port", "title": "Where are your agents?", "conference": "aie",
                              "starts": "2026-10-25T14:50", "room": "C", "speakers": ["pm_port"],
                              "topics": ["agents"], "evidence": "ev_talk_port"})
        data["evidence"].append({"id": "ev_talk_port", "url": "https://example.org/aie/port",
                                 "claim": "Pat Member speaks on where your agents are", "observed_at": "2026-10-24",
                                 "visibility": "public"})
        data["edges"].append({"type": "WORKS_AT", "from": "pm_port", "to": "c_port", "role": "Engineer",
                              "evidence": "ev_talk_port"})
    return data


class HookJEV:
    def __init__(self, cue="portfolio_news"):
        self.cue = cue
        self.calls = []

    def __call__(self, payload):
        self.calls.append(payload)
        return {"answers": {
            "fit": {"choice": "high", "confidence": 0.8,
                    "probabilities": {"high": 0.7, "medium": 0.2, "low": 0.05, "INSUFFICIENT_EVIDENCE": 0.05}},
            "introducer": {"choice": "public_1", "confidence": 0.7, "probabilities": {"public_1": 0.7}},
            "cue_type": {"choice": self.cue, "confidence": 0.85, "probabilities": {self.cue: 0.85}},
            "next_action": {"choice": "start_conversation", "confidence": 0.8,
                            "probabilities": {"start_conversation": 0.8}},
        }}


def _load(store, data):
    from warmopen.seed import load_seed

    load_seed(store, data)
    return store


def _invest(store):
    from warmopen.requests import create_request

    return create_request(store, "me", "vc_kay", "invest")


def test_hook_features_are_booleans(store, seed):
    from warmopen.features import extract_features

    s = _load(store, _hooked_seed(seed))
    feats = extract_features(s, _invest(s))
    assert feats["has_portfolio_news"] is True
    assert feats["team_member_present"] is True
    assert feats["has_stated_interest"] is False
    text = json.dumps(feats)
    for banned in ("Port Co", "Pat Member", "example.org", "c_port", "pm_port"):
        assert banned not in text


def test_portfolio_hook_opener_with_team_member(store, seed):
    from warmopen.openers import generate_openers
    from warmopen.scoring import score_fit

    s = _load(store, _hooked_seed(seed))
    rid = _invest(s)
    score_fit(s, rid, HookJEV())
    out = generate_openers(s, rid, None)
    first = out[0]
    assert first["evidence_id"] == "ev_port_news"
    assert first["url"] == "https://example.org/news/port-co-series-a"
    text = first["text"]
    assert text.startswith("Hi, I'm Requester Me, founder of My Startup.")
    assert "Port Co" in text and "Pat Member" in text
    assert text.endswith("Is anyone from their team here?")
    assert len(text) <= 280
    assert len({o["text"] for o in out}) == 3


def test_portfolio_hook_without_team_member(store, seed):
    from warmopen.openers import generate_openers
    from warmopen.scoring import score_fit

    s = _load(store, _hooked_seed(seed, with_member=False))
    rid = _invest(s)
    score_fit(s, rid, HookJEV())
    text = generate_openers(s, rid, None)[0]["text"]
    assert "Port Co" in text and "Pat Member" not in text
    assert text.endswith("Is anyone from their team here?")


def test_invested_in_is_a_public_fact_with_evidence(store, seed):
    s = _load(store, _hooked_seed(seed))
    rows = s.query(s.event(), "MATCH (:Fund {id: 'f_kay'})-[r:INVESTED_IN]->(c:Company {id: 'c_port'}) "
                              "RETURN r.evidence_id, r.round").result_set
    assert rows == [["ev_port_news", "Series A"]]


def test_hooks_never_use_private_text(store, seed):
    from warmopen.openers import generate_openers
    from warmopen.scoring import score_fit

    s = _load(store, _hooked_seed(seed))
    rid = _invest(s)
    score_fit(s, rid, HookJEV())
    seen = []
    generate_openers(s, rid, lambda prompt: seen.append(prompt) or "[]")
    blob = json.dumps(generate_openers(s, rid, None)) + "".join(seen)
    for hidden in HIDDEN_TEXT:
        assert hidden not in blob
    assert seen and "portfolio_news" in seen[0] and "Port Co" in seen[0]


@pytest.mark.parametrize("cue", ["capability", "problem"])
def test_other_cues_keep_their_ptc6_endings(store, seed, cue):
    from warmopen.openers import generate_openers
    from warmopen.scoring import score_fit

    endings = {"capability": "How did you approach it?", "problem": "What problem are you most focused on there?"}
    s = _load(store, _hooked_seed(seed))
    rid = _invest(s)
    score_fit(s, rid, HookJEV(cue=cue))
    cited = [o for o in generate_openers(s, rid, None) if o["evidence_id"]]
    assert cited and all(o["text"].endswith(endings[cue]) for o in cited)
