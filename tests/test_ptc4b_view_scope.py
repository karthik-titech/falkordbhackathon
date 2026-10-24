"""ptc4b frozen contract: a request id alone never reveals the requester's meetings.

Source: AI& panel on ptc4 (DeepSeek PP-1, Gemma PP-1, 2026-10-24): owners see
request ids in their pending list, so "request ids are bearer secrets" does not
protect meeting memory. Rule: every HTTP call that computes routes uses the
requester's own meeting edges only when that same call carries the requester's
valid X-Owner-Token (and the request was created with it).
"""
import copy
import json
import threading
import urllib.error
import urllib.request


def _serve(store, **kwargs):
    from warmopen.app import make_server

    server = make_server(store, "127.0.0.1", 0, **kwargs)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:%d" % server.server_address[1]


def _call(base, method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Owner-Token"] = token
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def _no_repo(store, seed):
    from warmopen.seed import load_seed

    data = copy.deepcopy(seed)
    data["edges"] = [e for e in data["edges"] if not (e["type"] == "CONTRIBUTED_TO" and e["from"] == "me")]
    load_seed(store, data)
    return store


def _has_met(body):
    return any(e["category"] == "met" for r in body.get("routes", []) for e in r["edges"])


class PickPublic1:
    def __call__(self, payload):
        return {"answers": {
            "fit": {"choice": "high", "confidence": 0.8,
                    "probabilities": {"high": 0.7, "medium": 0.2, "low": 0.05, "INSUFFICIENT_EVIDENCE": 0.05}},
            "introducer": {"choice": "public_1", "confidence": 0.9, "probabilities": {"public_1": 0.9}},
        }}


def test_request_view_needs_the_requester_token_for_meetings(store, seed):
    from warmopen.memory import log_meeting

    s = _no_repo(store, seed)
    log_meeting(s, "me", "tok-me", "owner_a")
    server, base = _serve(s)
    try:
        st, created = _call(base, "POST", "/api/requests", {"requester": "me", "target": "vc_kay", "goal": "invest"},
                            token="tok-me")
        assert st == 200 and _has_met(created)
        rid = created["request_id"]
        st, anon = _call(base, "GET", f"/api/requests/{rid}")
        assert st == 200 and not _has_met(anon)
        st, owner = _call(base, "GET", f"/api/requests/{rid}", token="tok-b")
        assert st == 200 and not _has_met(owner)
        st, mine = _call(base, "GET", f"/api/requests/{rid}", token="tok-me")
        assert st == 200 and _has_met(mine)
        assert "owner_a" not in json.dumps(anon.get("people", {})) or not _has_met(anon)
    finally:
        server.shutdown()


def test_scoring_without_the_token_never_names_the_met_person(store, seed):
    from warmopen.memory import log_meeting

    s = _no_repo(store, seed)
    log_meeting(s, "me", "tok-me", "owner_a")
    server, base = _serve(s, jev=PickPublic1())
    try:
        st, created = _call(base, "POST", "/api/requests", {"requester": "me", "target": "vc_kay", "goal": "invest"},
                            token="tok-me")
        rid = created["request_id"]
        st, anon = _call(base, "POST", f"/api/requests/{rid}/score")
        assert st == 200
        assert anon["introducer"] is None or anon["introducer"].get("via") != "owner_a"
        st, mine = _call(base, "POST", f"/api/requests/{rid}/score", token="tok-me")
        assert st == 200 and mine["introducer"] == {"route_id": "public_1", "via": "owner_a"}
    finally:
        server.shutdown()


def test_owner_pending_list_carries_no_meeting_routes(store, seed):
    from warmopen.memory import log_meeting

    s = _no_repo(store, seed)
    log_meeting(s, "me", "tok-me", "owner_a")
    server, base = _serve(s)
    try:
        st, created = _call(base, "POST", "/api/requests", {"requester": "me", "target": "vc_kay", "goal": "invest"},
                            token="tok-me")
        rid = created["request_id"]
        _call(base, "POST", f"/api/requests/{rid}/reachability", {"owner": "owner_b"})
        st, pending = _call(base, "GET", "/api/owner/owner_b/pending", token="tok-b")
        assert st == 200 and "met" not in json.dumps(pending)
    finally:
        server.shutdown()
