"""ptc6 frozen contract: JEV picks the opener style and the next move.

Source: Karthik 2026-10-24 ("add it as ptc6") after reviewing ChatGPT's JEV
design. Accepted: cue_type and best_next_action as two more choice questions in
the SAME single JEV call; abstract features only (seeking_overlap_count,
met_before). Rejected: evidence_grounded (would send free text to JEV).
score_fit's frozen key set is unchanged; the move is stored on the request and
read through scoring.suggested_move().

AMENDMENT 2026-10-24 (ptc4 Astra plan review): met_before is True only for a
request created with the requester's valid token (create_request(...,
requester_token=...)); a tokenless request never reveals private memory.
"""
import copy
import json
import threading
import urllib.request

import pytest

from conftest import HIDDEN_TEXT, SEED

# AMENDMENT 2026-10-24 (Karthik: investor hooks): portfolio_news and personal_interest added;
# their opener text is built in ptc8 from graph evidence.
CUES = ["shared_interest", "capability", "problem", "previous_conversation", "portfolio_news",
        "personal_interest", "INSUFFICIENT_EVIDENCE"]
ACTIONS = ["start_conversation", "ask_discovery_question", "request_intro", "no_approach", "INSUFFICIENT_EVIDENCE"]
CUE_ENDINGS = {
    "shared_interest": "What drew you to it?",
    "capability": "How did you approach it?",
    "problem": "What problem are you most focused on there?",
    "previous_conversation": "What has changed since we last spoke?",
}


class FakeJEV6:
    def __init__(self, cue="capability", cue_conf=0.8, action="ask_discovery_question", action_conf=0.9):
        self.calls = []
        self.cue, self.cue_conf, self.action, self.action_conf = cue, cue_conf, action, action_conf

    def __call__(self, payload):
        self.calls.append(payload)
        return {"answers": {
            "fit": {"choice": "high", "confidence": 0.8,
                    "probabilities": {"high": 0.7, "medium": 0.2, "low": 0.05, "INSUFFICIENT_EVIDENCE": 0.05}},
            "introducer": {"choice": "public_1", "confidence": 0.7, "probabilities": {"public_1": 0.7}},
            "cue_type": {"choice": self.cue, "confidence": self.cue_conf, "probabilities": {self.cue: self.cue_conf}},
            "next_action": {"choice": self.action, "confidence": self.action_conf,
                            "probabilities": {self.action: self.action_conf}},
        }}


@pytest.fixture
def seeking(store, seed):
    from warmopen.seed import load_seed

    data = copy.deepcopy(seed)
    data["startups"][0]["seeking"] = ["graphs"]
    load_seed(store, data)
    return store


def _invest(store):
    from warmopen.requests import create_request

    return create_request(store, "me", "vc_kay", "invest")


def test_one_call_carries_four_choice_questions(seeking):
    from warmopen.scoring import score_fit

    jev = FakeJEV6()
    out = score_fit(seeking, _invest(seeking), jev)
    assert len(jev.calls) == 1 and out["value"] == 0.84
    questions = jev.calls[0]["questions"]
    assert list(questions) == ["fit", "introducer", "cue_type", "next_action"]
    assert list(questions["cue_type"]["criteria"]) == CUES
    assert list(questions["next_action"]["criteria"]) == ACTIONS
    for q in questions.values():
        assert q["type"] == "choice" and "choices" not in q
    text = json.dumps(questions)
    for p in SEED["people"]:
        assert p["name"] not in text
    for e in SEED["evidence"]:
        assert e["url"] not in text and e["claim"] not in text
    for hidden in HIDDEN_TEXT:
        assert hidden not in text


def test_new_abstract_features(seeking):
    from warmopen.features import extract_features
    from warmopen.memory import log_meeting

    from warmopen.requests import create_request

    rid = create_request(seeking, "me", "vc_kay", "invest", requester_token="tok-me")
    plain = _invest(seeking)
    feats = extract_features(seeking, rid, include_own=True)
    assert feats["seeking_overlap_count"] == 1
    assert feats["met_before"] is False
    log_meeting(seeking, "me", "tok-me", "vc_kay")
    assert extract_features(seeking, rid, include_own=True)["met_before"] is True
    assert extract_features(seeking, rid)["met_before"] is False  # ptc4b: explicit opt-in per call
    assert extract_features(seeking, plain, include_own=True)["met_before"] is False


def test_suggested_move_is_stored_and_gated(seeking):
    from warmopen.scoring import score_fit, suggested_move

    rid = _invest(seeking)
    assert suggested_move(seeking, rid) == {"cue_type": None, "next_action": None}
    score_fit(seeking, rid, FakeJEV6(cue_conf=0.4))
    move = suggested_move(seeking, rid)
    assert move["cue_type"] is None
    assert move["next_action"] == {"choice": "ask_discovery_question", "confidence": 0.9}


def test_older_jev_answers_without_moves_still_score(seeking):
    from warmopen.scoring import score_fit, suggested_move

    class OldJEV(FakeJEV6):
        def __call__(self, payload):
            out = super().__call__(payload)
            del out["answers"]["cue_type"], out["answers"]["next_action"]
            return out

    rid = _invest(seeking)
    out = score_fit(seeking, rid, OldJEV())
    assert out["abstained"] is False and out["value"] == 0.84
    assert suggested_move(seeking, rid) == {"cue_type": None, "next_action": None}


@pytest.mark.parametrize("cue", list(CUE_ENDINGS))
def test_template_openers_follow_the_cue(seeking, cue):
    from warmopen.openers import generate_openers
    from warmopen.scoring import score_fit

    rid = _invest(seeking)
    score_fit(seeking, rid, FakeJEV6(cue=cue))
    out = generate_openers(seeking, rid, None)
    cited = [o for o in out if o["evidence_id"] is not None]
    assert cited
    for o in cited:
        assert o["text"].endswith(CUE_ENDINGS[cue]) and len(o["text"]) <= 280


def test_llm_prompt_names_the_cue(seeking):
    from warmopen.openers import generate_openers
    from warmopen.scoring import score_fit

    rid = _invest(seeking)
    score_fit(seeking, rid, FakeJEV6(cue="problem"))
    seen = []

    def llm(prompt):
        seen.append(prompt)
        return "[]"

    generate_openers(seeking, rid, llm)
    assert seen and "problem" in seen[0]


def test_score_api_returns_the_move_and_ui_shows_it(seeking):
    from pathlib import Path

    from warmopen.app import make_server

    server = make_server(seeking, "127.0.0.1", 0, jev=FakeJEV6())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        rid = _invest(seeking)
        req = urllib.request.Request("http://127.0.0.1:%d/api/requests/%s/score" % (server.server_address[1], rid),
                                     data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.load(r)
        assert body["label"] == "uncalibrated fit"
        assert body["move"] == {"cue_type": {"choice": "capability", "confidence": 0.8},
                                "next_action": {"choice": "ask_discovery_question", "confidence": 0.9}}
    finally:
        server.shutdown()
    js = (Path(__file__).resolve().parents[1] / "warmopen" / "static" / "app.js").read_text(encoding="utf-8")
    assert "Suggested move" in js and "Opener style" in js
