"""ptc4 frozen contract: "I met someone" memory changes the next path search.

Source: Karthik's pick 2026-10-24 (idea A from the ChatGPT brainstorm review):
a logged meeting lands in the requester's own private graph, and Find a path
immediately returns a new warm route that uses it. The FalkorDB track judges
persistent memory and shared state; this is the live "graph changed the answer"
moment. Privacy rule: only the requester's own direct edges, only as the first
hop, never another person's graph, nothing written to the shared event graph.

AMENDMENT 2026-10-24 (Astra plan review): own edges are used only when the
caller asks for them (include_own=True) and, over HTTP, only for a request
created with the requester's valid token; meetings are a separate "met" edge;
only seed-public people can be logged; error bodies never echo token values.
"""
import copy
import json
import math
import threading
import urllib.error
import urllib.request

import pytest

MET_TIE = round(1 - math.exp(-0.5), 3)  # tie_strength({"met_today": True})


def _event_text(store):
    return json.dumps(store.dump("event"), sort_keys=True, default=str)


def test_logged_meeting_creates_a_direct_warm_route(loaded):
    from warmopen.memory import log_meeting
    from warmopen.paths import public_paths

    assert public_paths(loaded, "me", "eng_lee") == []
    out = log_meeting(loaded, "me", "tok-me", "eng_lee")
    assert out == {"requester": "me", "person": "eng_lee", "category": "met", "tie": MET_TIE}
    assert public_paths(loaded, "me", "eng_lee") == []  # own memory is opt-in
    routes = public_paths(loaded, "me", "eng_lee", include_own=True)
    assert routes[0]["persons"] == ["me", "eng_lee"]
    assert routes[0]["edges"][0]["category"] == "met"
    assert routes[0]["edges"][0]["evidence_id"] is None


def test_meeting_extends_through_public_links(store, seed):
    from warmopen.memory import log_meeting
    from warmopen.paths import public_paths
    from warmopen.seed import load_seed

    no_repo = copy.deepcopy(seed)
    no_repo["edges"] = [e for e in no_repo["edges"] if not (e["type"] == "CONTRIBUTED_TO" and e["from"] == "me")]
    load_seed(store, no_repo)
    assert public_paths(store, "me", "vc_kay") == []
    log_meeting(store, "me", "tok-me", "owner_a")
    routes = public_paths(store, "me", "vc_kay", include_own=True)
    assert routes and routes[0]["persons"] == ["me", "owner_a", "vc_kay"]
    assert [e["category"] for e in routes[0]["edges"]] == ["met", "co_speaker"]
    assert routes[0]["edges"][1]["evidence_id"] == "ev_talk_pair"


def test_meeting_is_private_to_the_requester(loaded):
    from warmopen.memory import log_meeting
    from warmopen.paths import public_paths

    before = _event_text(loaded)
    log_meeting(loaded, "me", "tok-me", "eng_lee")
    assert _event_text(loaded) == before
    assert public_paths(loaded, "topic_twin", "eng_lee", include_own=True) == []
    assert public_paths(loaded, "owner_b", "eng_lee", include_own=True) == []
    private = json.dumps(loaded.dump(loaded.private("me").name), sort_keys=True, default=str)
    assert "eng_lee" in private


def test_meeting_needs_the_requesters_token_and_a_real_person(loaded):
    from warmopen.memory import log_meeting

    with pytest.raises(PermissionError):
        log_meeting(loaded, "me", "tok-a", "eng_lee")
    with pytest.raises(PermissionError):
        log_meeting(loaded, "me", None, "eng_lee")
    with pytest.raises(ValueError):
        log_meeting(loaded, "me", "tok-me", "nobody")
    with pytest.raises(ValueError):
        log_meeting(loaded, "me", "tok-me", "me")
    with pytest.raises(ValueError):
        log_meeting(loaded, "me", "tok-me", "carol_hidden")


def test_revealed_private_people_cannot_be_logged(loaded):
    from warmopen.broker import reachability, reveal
    from warmopen.consent import grant
    from warmopen.memory import log_meeting
    from warmopen.requests import create_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    grant(loaded, "owner_b", "tok-b", "me", rid, "reachability")
    offer = reachability(loaded, "owner_b", rid)["offer_id"]
    grant(loaded, "owner_b", "tok-b", "me", rid, "reveal")
    reveal(loaded, "owner_b", rid, offer)
    with pytest.raises(ValueError):
        log_meeting(loaded, "me", "tok-me", "carol_hidden")


def test_meeting_never_overwrites_an_owner_edge(loaded):
    from warmopen.memory import log_meeting

    def owner_edges():
        rows = loaded.query(loaded.private("owner_a").name,
                            "MATCH (:Person {id: 'owner_a'})-[r:KNOWS]->(b) "
                            "WHERE r.category <> 'met' RETURN b.id, r.category, r.strength ORDER BY b.id").result_set
        return rows

    loaded.query(loaded.private("owner_a").name,
                 "MERGE (a:Person {id: 'owner_a'}) MERGE (b:Person {id: 'vc_kay'}) "
                 "MERGE (a)-[:KNOWS {category: 'colleague', strength: 0.9, strength_source: 'owner'}]->(b)")
    before = owner_edges()
    log_meeting(loaded, "owner_a", "tok-a", "vc_kay")
    assert owner_edges() == before


def test_logging_twice_is_idempotent(loaded):
    from warmopen.memory import log_meeting

    log_meeting(loaded, "me", "tok-me", "eng_lee")
    first = json.dumps(loaded.dump(loaded.private("me").name), sort_keys=True, default=str)
    log_meeting(loaded, "me", "tok-me", "eng_lee")
    assert json.dumps(loaded.dump(loaded.private("me").name), sort_keys=True, default=str) == first


def test_meeting_api_and_route_refresh(loaded):
    from warmopen.app import make_server

    server = make_server(loaded, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_address[1]

    def post(path, body, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Owner-Token"] = token
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    try:
        status, body = post("/api/meetings", {"requester": "me", "person": "eng_lee"}, token="wrong")
        assert status == 403 and "wrong" not in json.dumps(body) and "tok-me" not in json.dumps(body)
        status, body = post("/api/meetings", {"requester": "me", "person": "eng_lee"}, token="tok-me")
        assert status == 200 and body["tie"] == MET_TIE and body["mode"] == "live"
        status, body = post("/api/requests", {"requester": "me", "target": "eng_lee", "goal": "sales"})
        assert status == 200 and body["routes"] == []  # no token: memory stays private
        status, body = post("/api/requests", {"requester": "me", "target": "eng_lee", "goal": "sales"}, token="tok-me")
        assert status == 200
        assert body["routes"][0]["edges"][0]["category"] == "met"
        assert body["people"]["eng_lee"] == "Lee Buyer"
    finally:
        server.shutdown()
