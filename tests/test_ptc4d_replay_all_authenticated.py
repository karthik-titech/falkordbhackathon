"""ptc4d frozen contract: every authenticated response is replayed only to its token.

Source: Astra re-review of ptc4c, 2026-10-24 (P1): a recorded POST /api/meetings
replayed to anonymous and other-owner callers, confirming guessed meeting pairs.
General rule (spec author, to close the class): any recorded response for a
call whose X-Owner-Token authenticated (requester or owner) carries
auth_sha256 = sha256(token); replay serves it only to a caller presenting the
same token. Unauthenticated calls replay as before.
"""
import hashlib
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


MEETING = {"requester": "me", "person": "eng_lee"}


def _record(loaded, rec):
    server, base = _serve(loaded, record_dir=rec)
    try:
        st, created = _call(base, "POST", "/api/requests", {"requester": "me", "target": "eng_lee", "goal": "sales"})
        rid = created["request_id"]
        assert _call(base, "POST", "/api/meetings", MEETING, token="tok-me")[0] == 200
        _call(base, "POST", f"/api/requests/{rid}/reachability", {"owner": "owner_b"})
        assert _call(base, "GET", "/api/owner/owner_b/pending", token="tok-b")[0] == 200
        grant = {"owner": "owner_b", "requester": "me", "request_id": rid, "scope": "reachability"}
        assert _call(base, "POST", "/api/grants", grant, token="tok-b")[0] == 200
    finally:
        server.shutdown()
    return rid, grant


def test_authenticated_recordings_are_tagged(loaded, tmp_path):
    rec = tmp_path / "rec"
    _record(loaded, rec)
    by_path = {}
    for f in sorted(rec.glob("*.json")):
        text = f.read_text()
        assert "tok-me" not in text and "tok-b" not in text
        r = json.loads(text)
        by_path.setdefault(r["path"], []).append(r)
    assert by_path["/api/meetings"][0]["auth_sha256"] == hashlib.sha256(b"tok-me").hexdigest()
    assert by_path["/api/owner/owner_b/pending"][0]["auth_sha256"] == hashlib.sha256(b"tok-b").hexdigest()
    assert by_path["/api/grants"][0]["auth_sha256"] == hashlib.sha256(b"tok-b").hexdigest()
    assert "auth_sha256" not in by_path["/api/requests"][0]


def test_replay_of_authenticated_calls_needs_the_same_token(loaded, tmp_path):
    from warmopen.app import make_server

    rec = tmp_path / "rec"
    rid, grant = _record(loaded, rec)

    def run(meeting_token, owner_token):
        server = make_server(None, "127.0.0.1", 0, mode="recorded", recordings_dir=rec)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_address[1]
        try:
            return {
                "meeting": _call(base, "POST", "/api/meetings", MEETING, token=meeting_token)[0],
                "pending": _call(base, "GET", "/api/owner/owner_b/pending", token=owner_token)[0],
                "grant": _call(base, "POST", "/api/grants", grant, token=owner_token)[0],
            }
        finally:
            server.shutdown()

    assert run(None, None) == {"meeting": 404, "pending": 404, "grant": 404}
    assert run("tok-b", "tok-me") == {"meeting": 404, "pending": 404, "grant": 404}
    digest = hashlib.sha256(b"tok-me").hexdigest()
    assert run(digest, digest)["meeting"] == 404  # the hash itself is not a token
    assert run("tok-me", "tok-b") == {"meeting": 200, "pending": 200, "grant": 200}
