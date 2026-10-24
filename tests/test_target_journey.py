"""Target journey contracts for cited attendance, bounded routes and auth scope."""

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone


def _journey_seed(seed, private=False):
    data = copy.deepcopy(seed)
    today = datetime.now(timezone.utc).date()
    data["conferences"] = [
        {"id": "conference_now", "name": "Current Graph Summit", "starts": today.isoformat(),
         "ends": (today + timedelta(days=1)).isoformat()},
        {"id": "conference_later", "name": "Future Graph Summit",
         "starts": (today + timedelta(days=30)).isoformat(),
         "ends": (today + timedelta(days=31)).isoformat()},
    ]
    data["people"].extend(
        {"id": f"journey_{number}", "name": f"Journey Person {number}",
         "handle": f"journey_{number}", "kind": "attendee", "consented": False}
        for number in range(1, 7))
    data["people"].append({"id": "journey_target", "name": "Journey Target",
                           "handle": "journey_target", "kind": "speaker", "consented": False})
    evidence, edges = [], []
    chain = ["me", "journey_1", "journey_2", "journey_3", "journey_4", "journey_5", "journey_target"]
    for index, (left, right) in enumerate(zip(chain, chain[1:]), 1):
        eid = f"journey_link_{index}"
        evidence.append({"id": eid, "url": f"https://example.org/journey/link-{index}",
                         "claim": f"Public professional source for route link {index}",
                         "observed_at": today.isoformat(), "visibility": "public"})
        edges.append({"type": "COAUTHORED", "from": left, "to": right, "evidence": eid})
    attendance = (("journey_1", "conference_now", "attendee_now"),
                  ("journey_target", "conference_now", "target_now"),
                  ("journey_1", "conference_later", "attendee_later"),
                  ("journey_target", "conference_later", "target_later"))
    for pid, cid, suffix in attendance:
        eid = "journey_" + suffix
        evidence.append({"id": eid, "url": f"https://example.org/journey/{suffix}",
                         "claim": f"Confirmed attendance source for {suffix}",
                         "observed_at": today.isoformat(), "visibility": "public"})
        edges.append({"type": "ATTENDS", "from": pid, "to": cid,
                      "confirmed": True, "evidence": eid})
    edges.append({"type": "ATTENDS", "from": "journey_2", "to": "conference_now",
                  "confirmed": False, "evidence": "journey_link_1"})
    data["evidence"].extend(evidence)
    data["edges"].extend(edges)
    if private:
        data["private"]["owner_b"] = {"knows": [
            {"from": "owner_b", "to": "journey_1", "category": "colleague",
             "features": {"shared_repos": 1}, "owner_strength": None}]}
    return data


def _request(store, requester="me", target="journey_target", token=None):
    from warmopen.requests import create_request

    return create_request(store, requester, target, "invest", requester_token=token)


def test_seed_loads_only_confirmed_attendance_with_public_citation(store, seed):
    from warmopen.seed import load_seed

    load_seed(store, _journey_seed(seed))
    rows = store.query(store.event(),
                       "MATCH (p:Person)-[r:ATTENDS]->(c:Conference) "
                       "RETURN p.id, c.id, r.confirmed, r.evidence_id ORDER BY p.id, c.id").result_set
    assert [row for row in rows if row[0] == "journey_1"] == [
        ["journey_1", "conference_later", True, "journey_attendee_later"],
        ["journey_1", "conference_now", True, "journey_attendee_now"],
    ]
    assert not any(row[0] == "journey_2" for row in rows)


def test_reloading_withdrawn_attendance_removes_the_old_confirmation(store, seed):
    from warmopen.seed import load_seed

    data = _journey_seed(seed)
    load_seed(store, data)
    withdrawn = copy.deepcopy(data)
    next(edge for edge in withdrawn["edges"]
         if edge["type"] == "ATTENDS" and edge["from"] == "journey_1"
         and edge["to"] == "conference_now")["confirmed"] = False
    load_seed(store, withdrawn)
    rows = store.query(store.event(),
                       "MATCH (:Person {id: 'journey_1'})-[r:ATTENDS]->"
                       "(:Conference {id: 'conference_now'}) RETURN r.confirmed").result_set
    assert rows == []


def test_conference_dates_do_not_keep_a_stale_appearance_current():
    from warmopen.target_plan import _timing

    day = datetime(2030, 4, 10).date()
    assert _timing({"starts": "2030-04-10"}, day) == "current"
    assert _timing({"starts": "2030-04-09"}, day) == "past_or_unknown"
    assert _timing({"starts": "2030-04-09", "ends": "2030-04-11"}, day) == "current"
    assert _timing({"starts": "not-a-date"}, day) == "past_or_unknown"


def test_six_hops_cycles_and_only_the_first_intermediary_must_attend(loaded, seed):
    from warmopen.seed import load_seed
    from warmopen.target_plan import _journey_routes

    load_seed(loaded, _journey_seed(seed))
    routes, attendance, truncated = _journey_routes(loaded, "me", "journey_target", "conference_now")
    assert not truncated
    six_hop = next(route for route in routes if route["hops"] == 6)
    assert six_hop["persons"] == ["me", "journey_1", "journey_2", "journey_3",
                                   "journey_4", "journey_5", "journey_target"]
    assert six_hop["intermediaries"] == [
        {"person": "journey_1", "evidence_id": "journey_attendee_now"}]
    assert "journey_2" not in attendance
    assert all(edge["evidence_id"] for edge in six_hop["edges"])


def test_seven_hops_do_not_reach_the_target(loaded, seed):
    from warmopen.seed import load_seed
    from warmopen.target_plan import _journey_routes

    data = _journey_seed(seed)
    data["people"].append({"id": "journey_target_7", "name": "Journey Target Seven",
                           "handle": "journey_target_7", "kind": "speaker", "consented": False})
    for index, (left, right) in enumerate((("journey_5", "journey_6"),
                                           ("journey_6", "journey_target_7")), 7):
        eid = f"journey_link_{index}"
        data["evidence"].append({"id": eid, "url": f"https://example.org/journey/link-{index}",
                                 "claim": f"Public professional source for route link {index}",
                                 "observed_at": "2026-10-24", "visibility": "public"})
        data["edges"].append({"type": "COAUTHORED", "from": left, "to": right, "evidence": eid})
    data["evidence"].append({"id": "journey_target7_now",
                             "url": "https://example.org/journey/target-7-attendance",
                             "claim": "Journey Target Seven is attending the current graph summit",
                             "observed_at": "2026-10-24", "visibility": "public"})
    data["edges"].append({"type": "ATTENDS", "from": "journey_target_7", "to": "conference_now",
                          "confirmed": True, "evidence": "journey_target7_now"})
    load_seed(loaded, data)
    routes, _, _ = _journey_routes(loaded, "me", "journey_target_7", "conference_now")
    assert routes == []


def test_decision_is_abstract_and_malformed_confidence_abstains(loaded, seed):
    from warmopen.seed import load_seed
    from warmopen.target_plan import plan_conference

    load_seed(loaded, _journey_seed(seed))
    request = {"requester": "me", "target": "journey_target", "goal": "invest"}
    seen = []

    def provider(payload):
        seen.append(payload)
        return {"answers": {"route": {"choice": "route_1", "confidence": 0.8}}}

    plan = plan_conference(loaded, request, "conference_now", jev=provider)
    encoded = json.dumps(seen[0])
    for hidden in ("Journey Person", "Journey Target", "journey_target", "conference_now",
                   "https://example.org", "Confirmed attendance source"):
        assert hidden not in encoded
    assert plan["decision"] == {"choice": "route_1", "abstained": False, "source": "model"}

    invalid = plan_conference(
        loaded, request, "conference_now",
        jev=lambda _: {"answers": {"route": {"choice": "route_1", "confidence": 0.2}}})
    assert invalid["decision"] == {"choice": None, "abstained": True, "source": "deterministic"}


def test_future_conference_needs_target_attendance_and_an_attending_connection(loaded, seed):
    from warmopen.seed import load_seed
    from warmopen.target_plan import future_conferences

    data = _journey_seed(seed)
    load_seed(loaded, data)
    request = {"requester": "me", "target": "journey_target", "goal": "invest"}
    plans = future_conferences(loaded, request)
    assert [plan["conference"]["id"] for plan in plans] == ["conference_later"]
    assert plans[0]["routes"]
    assert plans[0]["routes"][0]["intermediaries"][0] == {
        "person": "journey_1", "evidence_id": "journey_attendee_later"}

    no_target_attendance = copy.deepcopy(data)
    next(edge for edge in no_target_attendance["edges"]
         if edge["type"] == "ATTENDS" and edge["from"] == "journey_target"
         and edge["to"] == "conference_later")["confirmed"] = False
    load_seed(loaded, no_target_attendance)
    assert future_conferences(loaded, request) == []


def test_shared_work_needs_both_public_membership_citations(loaded):
    from warmopen.target_plan import _adjacency

    event = loaded.event()
    loaded.query(event, "MATCH (:Person {id: 'owner_a'})-[r:CONTRIBUTED_TO]->"
                       "(:Repo {id: 'r_tool'}) REMOVE r.evidence_id")
    without_second_source = _adjacency(loaded, "me", False, {"owner_a"})
    assert not any(edge["to"] == "owner_a" for edge in without_second_source["me"])

    loaded.query(event, "MATCH (:Person {id: 'owner_a'})-[r:CONTRIBUTED_TO]->"
                       "(:Repo {id: 'r_tool'}) SET r.evidence_id = 'ev_repo_a'")
    with_both_sources = _adjacency(loaded, "me", False, {"owner_a"})
    edge = next(edge for edge in with_both_sources["me"]
                if edge["to"] == "owner_a" and edge["category"] == "shared_work")
    assert edge["evidence_id"] == "ev_repo_me"
    assert edge["other_evidence_id"] == "ev_repo_a"


def test_private_first_hop_requires_same_call_token_and_replay_binding(loaded, seed, tmp_path):
    from warmopen.app import _Replay, _live
    from warmopen.seed import load_seed

    load_seed(loaded, _journey_seed(seed, private=True))
    rid = _request(loaded, requester="owner_b", token="tok-b")
    path, body = f"/api/requests/{rid}/plan", {"conference_id": "conference_now"}
    unauthenticated = _live(loaded, "POST", path, body, None, None, None)
    assert unauthenticated["plan"]["routes"] == []
    recording = {}
    authenticated = _live(loaded, "POST", path, body, "tok-b", None, None, recording)
    assert authenticated["plan"]["routes"]
    assert recording["auth_sha256"] == hashlib.sha256(b"tok-b").hexdigest()

    record = {"method": "POST", "path": path, "request_body": body,
              "status": 200, "body": authenticated, **recording}
    (tmp_path / "0001.json").write_text(json.dumps(record), encoding="utf-8")
    assert _Replay(tmp_path).response("POST", path, body, None)[0] == 404
    assert _Replay(tmp_path).response("POST", path, body, "tok-b")[0] == 200


def test_nearby_flag_uses_existing_cited_openers(loaded, seed):
    from warmopen.app import _live
    from warmopen.seed import load_seed

    load_seed(loaded, _journey_seed(seed))
    rid = _request(loaded)
    result = _live(loaded, "POST", f"/api/requests/{rid}/plan", {"nearby": True}, None, None, None)
    assert result["nearby"] is True
    assert result["plan"] is None
    assert len(result["openers"]) == 3
