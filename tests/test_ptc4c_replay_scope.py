"""ptc4c frozen contract: recordings and replay respect requester-private memory.

Source: Astra re-review of ptc4b, 2026-10-24 (P1): recording saved
authenticated, memory-aware responses unchanged, and replay served them to any
caller, including the sticky request view. Rule: a recorded response computed
with the requester's own memory carries only sha256(token) as "auth_sha256";
replay serves it only to a caller whose X-Owner-Token hashes to the same value,
else 404 "not in recording". Recordings never contain a raw token.
"""
import copy
import hashlib
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path


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


def _has_met(body):
    return any(e["category"] == "met" for r in body.get("routes", []) for e in r["edges"])


def _record_session(store, seed, rec_dir):
    from warmopen.memory import log_meeting
    from warmopen.seed import load_seed

    data = copy.deepcopy(seed)
    data["edges"] = [e for e in data["edges"] if not (e["type"] == "CONTRIBUTED_TO" and e["from"] == "me")]
    load_seed(store, data)
    log_meeting(store, "me", "tok-me", "owner_a")
    server, base = _serve(store, record_dir=rec_dir)
    try:
        st, created = _call(base, "POST", "/api/requests", {"requester": "me", "target": "vc_kay", "goal": "invest"},
                            token="tok-me")
        assert st == 200 and _has_met(created)
        rid = created["request_id"]
        st, view = _call(base, "GET", f"/api/requests/{rid}", token="tok-me")
        assert st == 200 and _has_met(view)
        st, targets = _call(base, "GET", "/api/targets")
        assert st == 200
    finally:
        server.shutdown()
    return rid


def test_recordings_hold_a_token_hash_never_the_token(store, seed, tmp_path):
    rec = tmp_path / "rec"
    _record_session(store, seed, rec)
    files = sorted(rec.glob("*.json"))
    assert files
    digest = hashlib.sha256(b"tok-me").hexdigest()
    marked = 0
    for f in files:
        text = f.read_text()
        assert "tok-me" not in text
        rec_obj = json.loads(text)
        if _has_met(rec_obj["body"]):
            assert rec_obj.get("auth_sha256") == digest
            marked += 1
    assert marked >= 2


def test_replay_serves_memory_only_to_the_matching_token(store, seed, tmp_path):
    from warmopen.app import make_server

    rec = tmp_path / "rec"
    rid = _record_session(store, seed, rec)

    def replay_once(token):
        server = make_server(None, "127.0.0.1", 0, mode="recorded", recordings_dir=rec)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_address[1]
        try:
            out = {}
            out["create"] = _call(base, "POST", "/api/requests",
                                  {"requester": "me", "target": "vc_kay", "goal": "invest"}, token=token)
            out["view"] = _call(base, "GET", f"/api/requests/{rid}", token=token)
            out["view_again"] = _call(base, "GET", f"/api/requests/{rid}", token=token)
            out["targets"] = _call(base, "GET", "/api/targets")
            return out
        finally:
            server.shutdown()

    anon = replay_once(None)
    assert anon["create"][0] == 404 and anon["create"][1]["error"] == "not in recording"
    assert anon["view"][0] == 404 and anon["view_again"][0] == 404
    assert anon["targets"][0] == 200 and anon["targets"][1]["mode"] == "recorded"

    other = replay_once("tok-b")
    assert other["create"][0] == 404 and other["view"][0] == 404

    mine = replay_once("tok-me")
    assert mine["create"][0] == 200 and _has_met(mine["create"][1])
    assert mine["view"][0] == 200 and _has_met(mine["view"][1])
    assert mine["view_again"][0] == 200 and _has_met(mine["view_again"][1])  # sticky for the right caller


def test_replay_module_stays_stdlib_only():
    src = (Path(__file__).resolve().parents[1] / "warmopen" / "app.py").read_text()
    assert "import falkordb" not in src.split("def _live")[0]
