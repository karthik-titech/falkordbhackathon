"""ptc2b frozen contract: the JEV request shape confirmed by a live call.

Source: live probe 2026-10-23 against https://api.typesafe.ai/v1/systemone
(model jev-1.14.0). A "choices" list plus a string "criteria" returns HTTP 422
("questions.fit.choice.criteria: Input should be a valid dictionary"). A
"criteria" map of {choice: description} with no "choices" key returns 200.
"""


def _sales_request(store):
    from warmopen.requests import create_request

    return create_request(store, "me", "eng_lee", "sales")


def _payload(store, rid):
    from warmopen.features import extract_features
    from warmopen.scoring import build_payload

    feats = extract_features(store, rid)
    choices = [r["route_id"] for r in feats["routes"]] + ["APPROACH_DIRECTLY", "INSUFFICIENT_EVIDENCE"]
    return build_payload(feats, choices), choices


def test_choice_questions_use_criteria_maps(loaded):
    payload, choices = _payload(loaded, _sales_request(loaded))
    assert payload["model"] == "jev-latest"
    fit = payload["questions"]["fit"]
    intro = payload["questions"]["introducer"]
    for question in (fit, intro):
        assert question["type"] == "choice"
        assert "choices" not in question
        assert isinstance(question["instructions"], str) and question["instructions"]
        assert isinstance(question["criteria"], dict)
        assert all(isinstance(v, str) and v for v in question["criteria"].values())
    assert list(fit["criteria"]) == ["high", "medium", "low", "INSUFFICIENT_EVIDENCE"]
    assert list(intro["criteria"]) == choices


def test_criteria_text_carries_no_graph_strings(loaded):
    import json

    from conftest import HIDDEN_TEXT, SEED

    payload, _ = _payload(loaded, _sales_request(loaded))
    questions = json.dumps(payload["questions"])
    # Ids shorter than 4 characters ("me") collide with ordinary words.
    names = [p["name"] for p in SEED["people"]] + [p["id"] for p in SEED["people"] if len(p["id"]) >= 4]
    urls = [e["url"] for e in SEED["evidence"]]
    for text in names + urls + list(HIDDEN_TEXT):
        assert text not in questions
