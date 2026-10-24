"""ptc3b frozen contract: demo polish and server lock scope.

Source: gate-seat HTTP walk-through 2026-10-23 (template opener read
"...observability What would you add?"; no event for a no_consent answer or
for send) and AI& panel card (server lock held across slow JEV/LLM calls,
stalling the owner page's polling).
"""
import json
import re
import threading
import time
import urllib.request


def _serve(store, **kwargs):
    from warmopen.app import make_server

    server = make_server(store, "127.0.0.1", 0, **kwargs)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:%d" % server.server_address[1]


def _post(base, path, body=None):
    req = urllib.request.Request(base + path, method="POST",
                                 data=json.dumps(body or {}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def test_template_openers_read_as_sentences(loaded):
    from warmopen.openers import generate_openers
    from warmopen.requests import create_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    out = generate_openers(loaded, rid, None)
    assert len(out) == 3
    for cue in out:
        text = cue["text"]
        assert len(text) <= 280
        assert re.fullmatch(r"[A-Z].*[.?!]", text), text
        # A claim never runs into the next sentence without punctuation.
        assert not re.search(r"[a-z0-9] [A-Z][a-z]+ (would|you|what)\b", text), text
        assert "  " not in text


def test_no_consent_and_send_are_on_the_timeline(loaded):
    from warmopen.agentlog import events
    from warmopen.broker import reachability
    from warmopen.requests import create_request

    server, base = _serve(loaded)
    try:
        rid = create_request(loaded, "me", "vc_kay", "invest")
        assert reachability(loaded, "owner_b", rid)["status"] == "no_consent"
        actions = [(e["agent"], e["action"]) for e in events(loaded, rid)]
        assert actions.count(("broker", "reachability_answered")) == 1
        assert _post(base, f"/api/requests/{rid}/send")["state"] == "requested"
        actions = [(e["agent"], e["action"]) for e in events(loaded, rid)]
        assert actions[-1] == ("seeker", "intro_requested")
    finally:
        server.shutdown()


def test_slow_scoring_does_not_block_other_requests(loaded):
    from warmopen.requests import create_request

    def slow_jev(payload):
        time.sleep(2.0)
        raise RuntimeError("unavailable")

    server, base = _serve(loaded, jev=slow_jev)
    try:
        rid = create_request(loaded, "me", "vc_kay", "invest")
        worker = threading.Thread(target=_post, args=(base, f"/api/requests/{rid}/score"))
        worker.start()
        time.sleep(0.3)
        started = time.monotonic()
        with urllib.request.urlopen(base + "/api/targets", timeout=20) as r:
            assert r.status == 200
        assert time.monotonic() - started < 1.0
        worker.join(10)
    finally:
        server.shutdown()
