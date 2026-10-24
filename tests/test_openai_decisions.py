import copy
import io
import json
from unittest.mock import patch

import pytest

from warmopen.decisions import API_URL, MODEL, _wire_payload, decisions_client
from warmopen.scoring import build_payload


def _state():
    return {
        "goal": "invest",
        "public_route_count": 1,
        "best_public_hops": 2,
        "revealed": False,
        "revealed_hops": None,
        "revealed_min_tie": None,
        "shared_work_links": 0,
        "co_speaker_links": 1,
        "coauthor_links": 0,
        "topic_overlap_count": 2,
        "seeking_overlap_count": 1,
        "met_before": False,
        "has_portfolio_news": False,
        "team_member_present": False,
        "has_stated_interest": False,
        "stage_match": True,
        "sector_overlap_count": 1,
        "category_match": None,
        "evidence_count": 2,
        "gaps_count": 0,
        "routes": [{"route_id": "public_1", "hops": 2, "min_tie": None, "kind": "public"}],
    }


def _scoring_payload(state=None):
    state = state or _state()
    choices = [route["route_id"] for route in state["routes"]]
    choices += ["APPROACH_DIRECTLY", "INSUFFICIENT_EVIDENCE"]
    return build_payload(state, choices)


def _planner_payload():
    state = {
        "goal": "invest",
        "conference_timing": "current",
        "target_confirmed": True,
        "route_count": 1,
        "routes": [{
            "route_id": "route_1",
            "hops": 2,
            "supported_edge_count": 2,
            "confirmed_attendance_count": 1,
        }],
    }
    criteria = {
        "route_1": "Choose this supported route using fewer hops and confirmed attendance.",
        "APPROACH_DIRECTLY": "Use no route.",
        "INSUFFICIENT_EVIDENCE": "Abstain from choosing a route.",
    }
    return {
        "model": "jev-latest",
        "state": state,
        "questions": {"route": {
            "type": "choice",
            "instructions": "Select one fixed route label, APPROACH_DIRECTLY, or INSUFFICIENT_EVIDENCE.",
            "criteria": criteria,
        }},
    }


def _api_response(payload, refusal=()):
    answers = []
    for name, question in payload["questions"].items():
        if name in refusal:
            answers.append({"type": "refusal", "name": name})
            continue
        choices = list(question["criteria"])
        preferred = {
            "fit": "high",
            "introducer": "APPROACH_DIRECTLY",
            "cue_type": "shared_interest",
            "next_action": "start_conversation",
            "route": "route_1",
        }.get(name)
        choice = preferred if preferred in choices else choices[0]
        answers.append({
            "type": "choice",
            "name": name,
            "choice": choice,
            "confidence": 0.8,
            "probabilities": [
                {"value": label, "probability": 1.0 if label == choice else 0.0}
                for label in choices
            ],
        })
    return {"model": MODEL, "answers": answers}


def _fake_response(payload, refusal=()):
    return io.BytesIO(json.dumps(_api_response(payload, refusal)).encode("utf-8"))


def test_decisions_client_builds_wire_payload_and_normalizes_choices():
    payload = _scoring_payload()
    with patch("warmopen.decisions.urlopen", return_value=_fake_response(payload)) as open_url:
        result = decisions_client("test-key", timeout=4.0)(payload)

    request = open_url.call_args.args[0]
    wire = json.loads(request.data)
    assert request.full_url == API_URL
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert open_url.call_args.kwargs == {"timeout": 4.0}
    assert wire["model"] == MODEL
    assert wire["input"] == [{"role": "user", "content": [
        {"type": "input_json", "data": payload["state"]}
    ]}]
    assert [question["name"] for question in wire["questions"]] == [
        "fit", "introducer", "cue_type", "next_action"
    ]
    for sent, original in zip(wire["questions"], payload["questions"].values()):
        assert sent["type"] == "choice"
        assert sent["instructions"] == original["instructions"]
        assert sent["choices"] == [
            {"value": value, "description": description}
            for value, description in original["criteria"].items()
        ]
    assert result["answers"]["fit"] == {
        "choice": "high",
        "confidence": 0.8,
        "probabilities": {"high": 1.0, "medium": 0.0, "low": 0.0,
                          "INSUFFICIENT_EVIDENCE": 0.0},
    }


def test_planner_payload_uses_its_fixed_abstract_route_schema():
    payload = _planner_payload()
    wire = _wire_payload(payload)
    assert wire["model"] == MODEL
    assert wire["input"][0]["content"][0]["data"] == payload["state"]
    assert wire["questions"] == [{
        "type": "choice",
        "name": "route",
        "instructions": payload["questions"]["route"]["instructions"],
        "choices": [
            {"value": value, "description": description}
            for value, description in payload["questions"]["route"]["criteria"].items()
        ],
    }]


def test_constructor_does_not_make_a_request():
    with patch("warmopen.decisions.urlopen") as open_url:
        decide = decisions_client("test-key")
    assert callable(decide)
    open_url.assert_not_called()


@pytest.mark.parametrize("name", ["fit", "route"])
def test_refusal_is_normalized_as_a_missing_answer(name):
    payload = _planner_payload() if name == "route" else _scoring_payload()
    with patch("warmopen.decisions.urlopen", return_value=_fake_response(payload, refusal=(name,))):
        result = decisions_client("test-key")(payload)
    assert name not in result["answers"]


@pytest.mark.parametrize("mutate", [
    lambda payload: payload["state"].update({"requester_name": "private name"}),
    lambda payload: payload["state"].update({"topic": "free text"}),
    lambda payload: payload["questions"].update({"extra": {}}),
    lambda payload: payload["questions"]["fit"]["criteria"].update({"person-17": "Unknown"}),
])
def test_unknown_keys_and_unapproved_text_are_rejected_before_request(mutate):
    payload = copy.deepcopy(_scoring_payload())
    mutate(payload)
    with patch("warmopen.decisions.urlopen") as open_url:
        with pytest.raises(ValueError):
            decisions_client("test-key")(payload)
    open_url.assert_not_called()


def test_planner_rejects_unapproved_labels_and_route_fields():
    payload = _planner_payload()
    payload["state"]["conference_timing"] = "Example Conference"
    with pytest.raises(ValueError):
        _wire_payload(payload)

    payload = _planner_payload()
    payload["state"]["routes"][0]["speaker_name"] = "private name"
    with pytest.raises(ValueError):
        _wire_payload(payload)


def test_nonfinite_and_unknown_answer_values_are_rejected():
    payload = _scoring_payload()
    answer = _api_response(payload)
    answer["answers"][0]["confidence"] = float("nan")
    with patch("warmopen.decisions.urlopen", return_value=io.BytesIO(json.dumps(answer).encode())):
        with pytest.raises(ValueError):
            decisions_client("test-key")(payload)

    answer = _api_response(payload)
    answer["answers"][0]["choice"] = "person-17"
    with patch("warmopen.decisions.urlopen", return_value=io.BytesIO(json.dumps(answer).encode())):
        with pytest.raises(ValueError):
            decisions_client("test-key")(payload)


def test_unknown_or_duplicate_answer_names_are_rejected():
    payload = _scoring_payload()
    answer = _api_response(payload)
    answer["answers"][0]["name"] = "person-17"
    with patch("warmopen.decisions.urlopen", return_value=io.BytesIO(json.dumps(answer).encode())):
        with pytest.raises(ValueError):
            decisions_client("test-key")(payload)

    answer = _api_response(payload)
    answer["answers"][1]["name"] = "fit"
    with patch("warmopen.decisions.urlopen", return_value=io.BytesIO(json.dumps(answer).encode())):
        with pytest.raises(ValueError):
            decisions_client("test-key")(payload)
