"""ptc3 frozen contract: HTTP API, owner token check, record and replay label, static pages.

Source: specs.ptc/ptc3-app-ui-replay.spec.txt; joint debate fold-ins 2026-10-23
(second-browser approval, labeled recorded fallback).
"""
import json
import threading
import urllib.error
import urllib.request

import pytest


def _start(**kwargs):
    from warmopen.app import make_server

    srv = make_server(**kwargs)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _call(base, method, path, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if path.startswith("/api/") else raw)
    except urllib.error.HTTPError as err:
        raw = err.read().decode()
        return err.code, (json.loads(raw) if path.startswith("/api/") else raw)


@pytest.fixture
def live(loaded):
    srv, base = _start(store=loaded)
    yield base
    srv.shutdown()
    srv.server_close()


def test_full_api_loop_with_owner_approval(live):
    st, body = _call(live, "POST", "/api/requests", {"requester": "me", "target": "eng_lee", "goal": "sales"})
    assert st == 200 and body["mode"] == "live"
    rid = body["request_id"]

    st, body = _call(live, "POST", f"/api/requests/{rid}/reachability", {"owner": "owner_b"})
    assert st == 200 and body["status"] == "no_consent"

    grant = {"owner": "owner_b", "requester": "me", "request_id": rid, "scope": "reachability"}
    st, body = _call(live, "POST", "/api/grants", grant)
    assert st == 403
    st, body = _call(live, "POST", "/api/grants", grant, {"X-Owner-Token": "wrong"})
    assert st == 403
    st, body = _call(live, "POST", "/api/grants", grant, {"X-Owner-Token": "tok-b"})
    assert st == 200 and body["grant_id"] and "tok-b" not in json.dumps(body)

    st, body = _call(live, "POST", f"/api/requests/{rid}/reachability", {"owner": "owner_b"})
    assert body["status"] == "reachable" and "carol_hidden" not in json.dumps(body)
    offer = body["offer_id"]

    st, body = _call(live, "POST", f"/api/requests/{rid}/reveal", {"owner": "owner_b", "offer_id": offer})
    assert st == 403
    _call(live, "POST", "/api/grants", {**grant, "scope": "reveal"}, {"X-Owner-Token": "tok-b"})
    st, body = _call(live, "POST", f"/api/requests/{rid}/reveal", {"owner": "owner_b", "offer_id": offer})
    assert st == 200 and body["route_id"] == "revealed_1"

    st, body = _call(live, "POST", f"/api/requests/{rid}/score")
    assert st == 200 and body["label"] == "uncalibrated fit"
    assert body["abstained"] is True and body["reason"] == "jev_unavailable"

    st, body = _call(live, "POST", f"/api/requests/{rid}/openers")
    assert st == 200 and len(body["items"]) == 3

    st, body = _call(live, "POST", f"/api/requests/{rid}/send")
    assert st == 200 and body["state"] == "requested"

    st, body = _call(live, "GET", f"/api/requests/{rid}")
    agents = [e["agent"] for e in body["events"]]
    assert {"seeker", "broker", "scorer", "writer"} <= set(agents)


def test_error_codes(live):
    st, body = _call(live, "POST", "/api/requests", {"requester": "me", "target": "vc_kay", "goal": "friendship"})
    assert st == 400 and body["mode"] == "live" and body["error"]
    st, _ = _call(live, "GET", "/api/requests/does-not-exist")
    assert st == 404
    st, body = _call(live, "POST", "/api/requests", {"requester": "me", "target": "vc_kay", "goal": "invest"})
    rid = body["request_id"]
    assert _call(live, "POST", f"/api/requests/{rid}/send")[1]["state"] == "requested"
    st, _ = _call(live, "POST", f"/api/requests/{rid}/send")
    assert st == 409


def test_owner_pending_needs_token_and_hides_it(live):
    st, body = _call(live, "POST", "/api/requests", {"requester": "me", "target": "eng_lee", "goal": "sales"})
    rid = body["request_id"]
    _call(live, "POST", f"/api/requests/{rid}/reachability", {"owner": "owner_b"})
    st, _ = _call(live, "GET", "/api/owner/owner_b/pending")
    assert st == 403
    st, body = _call(live, "GET", "/api/owner/owner_b/pending", headers={"X-Owner-Token": "tok-b"})
    assert st == 200 and any(i["request_id"] == rid for i in body["items"])
    assert "tok-b" not in json.dumps(body)


def test_targets_are_speakers(live):
    st, body = _call(live, "GET", "/api/targets")
    ids = {t["id"] for t in body["items"]}
    assert {"vc_kay", "eng_lee"} <= ids and "me" not in ids


def test_record_then_replay_is_labeled(loaded, tmp_path):
    rec = tmp_path / "rec"
    srv, base = _start(store=loaded, record_dir=str(rec))
    st, live_body = _call(base, "GET", "/api/targets")
    srv.shutdown()
    srv.server_close()
    files = sorted(rec.glob("*.json"))
    assert len(files) == 1
    saved = json.loads(files[0].read_text())
    assert saved["method"] == "GET" and saved["path"] == "/api/targets"

    srv, base = _start(store=None, mode="recorded", recordings_dir=str(rec))
    try:
        st, body = _call(base, "GET", "/api/targets")
        assert st == 200 and body["mode"] == "recorded"
        assert body["items"] == live_body["items"]
        st, body = _call(base, "GET", "/api/targets")
        assert st == 404 and body["error"] == "not in recording"
    finally:
        srv.shutdown()
        srv.server_close()


def test_pages_are_self_contained(live):
    st, html = _call(live, "GET", "/")
    assert st == 200
    assert 'id="path-view"' in html and 'id="agent-timeline"' in html and 'id="mode-banner"' in html
    assert "Recorded run" in html and "uncalibrated fit" in html
    assert 'src="http' not in html and 'href="http' not in html
    st, html = _call(live, "GET", "/owner")
    assert st == 200 and "Approve reachability" in html and "Approve reveal" in html
    st, _ = _call(live, "GET", "/static/../app.py")
    assert st == 404
