"""ptc1b frozen contract: fixes from the ptc1 build review.

Source: Astra build review 2026-10-23 (P0 clock outside lock, P1 reload keeps
reclassified evidence, P1 non-atomic reveal) and AI& panel cards (plain-text
owner token, unvalidated owner id in graph names).
"""
import json
import threading
import time

import pytest


def _dump(store, graph):
    return json.dumps(store.dump(graph), sort_keys=True, default=str)


# P0: the grant check uses the clock at check time, inside the lock

def test_queued_reachability_sees_grant_expiry(loaded, monkeypatch):
    from warmopen.broker import reachability
    from warmopen.consent import grant
    from warmopen.requests import create_request

    clock = {"t": 1000.0}
    monkeypatch.setattr(time, "time", lambda: clock["t"])
    rid = create_request(loaded, "me", "eng_lee", "sales")
    grant(loaded, "owner_b", "tok-b", "me", rid, "reachability", ttl_s=10)
    result = {}
    with loaded.lock:
        worker = threading.Thread(target=lambda: result.update(reachability(loaded, "owner_b", rid)))
        worker.start()
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            pass
        clock["t"] = 2000.0
    worker.join(5)
    assert result["status"] == "no_consent"


# P1: a reload that reclassifies evidence as private removes the public copy

def test_reload_removes_evidence_reclassified_private(store, seed):
    from warmopen.seed import load_seed

    load_seed(store, seed)
    assert "https://example.org/aie/kay" in _dump(store, "event")
    for item in seed["evidence"]:
        if item["id"] == "ev_talk_kay":
            item["visibility"] = "private"
    load_seed(store, seed)
    text = _dump(store, "event")
    assert "https://example.org/aie/kay" not in text
    assert "ev_talk_kay" not in text


# P1: a reveal that fails part way leaves no saved route without approval

def test_failed_reveal_is_atomic(loaded, monkeypatch):
    import warmopen.broker as broker
    from warmopen.consent import grant
    from warmopen.requests import create_request, get_request

    rid = create_request(loaded, "me", "eng_lee", "sales")
    grant(loaded, "owner_b", "tok-b", "me", rid, "reachability")
    offer = broker.reachability(loaded, "owner_b", rid)["offer_id"]
    grant(loaded, "owner_b", "tok-b", "me", rid, "reveal")

    def boom(*args, **kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(broker, "_advance_locked", boom, raising=False)
    try:
        broker.reveal(loaded, "owner_b", rid, offer)
    except RuntimeError:
        pass
    req = get_request(loaded, rid)
    assert (req["state"] == "approved") == bool(req.get("revealed_offer_id"))
    monkeypatch.undo()
    route = broker.reveal(loaded, "owner_b", rid, offer)
    assert route["persons"] == ["owner_b", "carol_hidden", "eng_lee"]
    assert get_request(loaded, rid)["state"] == "approved"


# Panel: owner tokens are not stored in plain text anywhere

def test_owner_token_not_stored_in_plain_text(loaded):
    from warmopen.consent import grant
    from warmopen.requests import create_request

    for owner, token in (("owner_a", "tok-a"), ("owner_b", "tok-b"), ("me", "tok-me")):
        assert token not in _dump(loaded, loaded.private(owner).name)
    rid = create_request(loaded, "me", "eng_lee", "sales")
    assert grant(loaded, "owner_b", "tok-b", "me", rid, "reachability")
    with pytest.raises(PermissionError):
        grant(loaded, "owner_b", "tok-a", "me", rid, "reachability")


# Panel: owner ids used in graph names are validated

@pytest.mark.parametrize("bad", ["", "a/b", "../event", "a b", "x:y", "A" * 65])
def test_private_graph_rejects_bad_owner_ids(store, bad):
    with pytest.raises(ValueError):
        store.private(bad)
