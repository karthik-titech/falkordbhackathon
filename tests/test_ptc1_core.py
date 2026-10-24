"""ptc1 frozen contract: graph core, consent, broker, request state, agent log.

Source: specs.ptc/ptc1-graph-core.spec.txt; product from the joint Claude + Sol
debate 2026-10-23 (fold-ins: one intermediary, separate reachability and reveal
consent, topic overlap never a warm hop, no hidden names in shared records).
"""
import json

import pytest

from conftest import HIDDEN_IDS, HIDDEN_TEXT


def _event_text(store):
    return json.dumps(store.dump("event"), sort_keys=True, default=str)


# T2 seed loader

def test_seed_is_idempotent(store, seed):
    from warmopen.seed import load_seed

    first = load_seed(store, seed)
    dump1 = _event_text(store)
    second = load_seed(store, seed)
    assert first == second
    assert _event_text(store) == dump1


def test_private_graph_is_not_in_event_graph(loaded):
    text = _event_text(loaded)
    for hidden in HIDDEN_TEXT:
        assert hidden not in text
    assert "tok-b" not in text and "tok-a" not in text


# T3 tie strength

def test_tie_strength_formula_and_override():
    from warmopen.ties import tie_strength

    assert tie_strength({}) == (0.0, "formula")
    assert tie_strength({"shared_repos": 2}) == (0.503, "formula")
    assert tie_strength({"shared_repos": 9}) == tie_strength({"shared_repos": 5})
    assert tie_strength({"met_today": True}, owner_strength=0.25) == (0.25, "owner")
    with pytest.raises(ValueError):
        tie_strength({}, owner_strength=1.5)


def test_tie_strength_is_monotone_and_bounded():
    from warmopen.ties import tie_strength

    base, _ = tie_strength({"shared_repos": 1})
    more, _ = tie_strength({"shared_repos": 1, "coauthored": True})
    top, _ = tie_strength({"shared_repos": 5, "coauthored": True, "mutual_follow": True,
                           "met_today": True, "same_company": True})
    assert 0.0 <= base < more < top < 1.0


# T4 public paths

def test_public_route_via_shared_work_then_co_speaker(loaded):
    from warmopen.paths import public_paths

    routes = public_paths(loaded, "me", "vc_kay")
    assert routes, "expected a warm public route me -> owner_a -> vc_kay"
    first = routes[0]
    assert first["route_id"] == "public_1"
    assert first["persons"] == ["me", "owner_a", "vc_kay"]
    assert first["hops"] == 2
    assert [e["category"] for e in first["edges"]] == ["shared_work", "co_speaker"]
    assert first["edges"][1]["evidence_id"] == "ev_talk_pair"
    hops = [r["hops"] for r in routes]
    assert hops == sorted(hops)


def test_topic_overlap_is_never_a_warm_hop(loaded):
    from warmopen.paths import public_paths

    assert public_paths(loaded, "me", "topic_twin") == []


def test_public_paths_rejects_unknown_people(loaded):
    from warmopen.paths import public_paths

    with pytest.raises(ValueError):
        public_paths(loaded, "me", "nobody")


# T5 request state machine

def test_request_state_machine(loaded):
    from warmopen.requests import StateError, advance, create_request, get_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    assert get_request(loaded, rid)["state"] == "draft"
    advance(loaded, rid, "draft", "awaiting_approval")
    with pytest.raises(StateError):
        advance(loaded, rid, "draft", "awaiting_approval")
    with pytest.raises(StateError):
        advance(loaded, rid, "awaiting_approval", "requested")
    assert get_request(loaded, rid)["state"] == "awaiting_approval"
    advance(loaded, rid, "awaiting_approval", "approved")
    advance(loaded, rid, "approved", "requested")
    assert get_request(loaded, rid)["state"] == "requested"


def test_request_rejects_unknown_goal(loaded):
    from warmopen.requests import create_request

    with pytest.raises(ValueError):
        create_request(loaded, "me", "vc_kay", "friendship")


# T6 consent

def test_grants_are_separate_and_token_checked(loaded):
    from warmopen.consent import grant, has_grant
    from warmopen.requests import create_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    with pytest.raises(PermissionError):
        grant(loaded, "owner_b", "wrong", "me", rid, "reachability")
    with pytest.raises(ValueError):
        grant(loaded, "owner_b", "tok-b", "me", rid, "everything")
    grant(loaded, "owner_b", "tok-b", "me", rid, "reachability", now=1000.0)
    assert has_grant(loaded, "owner_b", "me", rid, "reachability", now=1001.0)
    assert not has_grant(loaded, "owner_b", "me", rid, "reveal", now=1001.0)
    assert not has_grant(loaded, "owner_b", "me", rid, "reachability", now=1000.0 + 901)


def test_revoked_grant_is_denied(loaded):
    from warmopen.consent import grant, has_grant, revoke
    from warmopen.requests import create_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    gid = grant(loaded, "owner_b", "tok-b", "me", rid, "reachability")
    revoke(loaded, "owner_b", "tok-b", gid)
    assert not has_grant(loaded, "owner_b", "me", rid, "reachability")


# T7 broker

def test_reachability_without_grant_is_no_consent(loaded):
    from warmopen.broker import reachability
    from warmopen.requests import create_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    res = reachability(loaded, "owner_b", rid)
    assert res == {"status": "no_consent", "hops": None, "tie": None, "offer_id": None}


def test_reachability_reveals_counts_not_names(loaded):
    from warmopen.broker import reachability
    from warmopen.consent import grant
    from warmopen.requests import create_request, get_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    grant(loaded, "owner_b", "tok-b", "me", rid, "reachability")
    res = reachability(loaded, "owner_b", rid)
    assert set(res) == {"status", "hops", "tie", "offer_id"}
    assert res["status"] == "reachable"
    assert res["hops"] == 2
    assert res["tie"] == 0.741  # min(formula 0.741 for owner_b->carol, owner 0.8 for carol->eng_lee)
    blob = json.dumps(res)
    for hidden in HIDDEN_IDS:
        assert hidden not in blob
        assert hidden not in res["offer_id"]
    for hidden in HIDDEN_TEXT:
        assert hidden not in _event_text(loaded)
    assert get_request(loaded, rid)["state"] == "awaiting_approval"


def test_reveal_needs_its_own_grant(loaded):
    from warmopen.broker import reachability, reveal
    from warmopen.consent import grant
    from warmopen.requests import create_request, get_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    grant(loaded, "owner_b", "tok-b", "me", rid, "reachability")
    offer = reachability(loaded, "owner_b", rid)["offer_id"]
    with pytest.raises(PermissionError):
        reveal(loaded, "owner_b", rid, offer)
    grant(loaded, "owner_b", "tok-b", "me", rid, "reveal")
    route = reveal(loaded, "owner_b", rid, offer)
    assert route["route_id"] == "revealed_1"
    assert route["persons"] == ["owner_b", "carol_hidden", "eng_lee"]
    assert [e["category"] for e in route["edges"]] == ["colleague", "friend"]
    assert all("tie" in e for e in route["edges"])
    assert get_request(loaded, rid)["state"] == "approved"
    with pytest.raises(ValueError):
        reveal(loaded, "owner_b", rid, "not-an-offer")


# T8 agent log

def test_agent_events_record_the_handoff(loaded):
    from warmopen.agentlog import events, log
    from warmopen.broker import reachability
    from warmopen.consent import grant
    from warmopen.requests import create_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    reachability(loaded, "owner_b", rid)
    grant(loaded, "owner_b", "tok-b", "me", rid, "reachability")
    reachability(loaded, "owner_b", rid)
    evs = events(loaded, rid)
    assert [e["seq"] for e in evs] == sorted(e["seq"] for e in evs)
    actions = [(e["agent"], e["action"]) for e in evs]
    assert actions[0] == ("seeker", "request_created")
    assert ("broker", "reachability_asked") in actions
    assert ("broker", "reachability_answered") in actions
    with pytest.raises(ValueError):
        log(loaded, rid, "intruder", "x")
