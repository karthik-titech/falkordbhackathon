"""ptc3c frozen contract: polish found in the headless-Firefox demo run.

Source: gate-seat browser run 2026-10-23 on the demo seed (Marionette, Firefox
158): sales openers repeated one claim three times when only one public
evidence item existed; the owner page showed raw ids ("me -> garry_tan"); the
fit card showed a raw reason code ("Abstained: jev_unavailable"); the revealed
path left the requester node unconnected.
"""
import copy
import json
import threading
import urllib.request
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "warmopen" / "static"


def test_sparse_evidence_never_repeats_an_opener(store, seed):
    from warmopen.openers import generate_openers
    from warmopen.requests import create_request
    from warmopen.seed import load_seed

    sparse = copy.deepcopy(seed)
    for company in sparse["companies"]:
        company["evidence"] = None
    load_seed(store, sparse)
    rid = create_request(store, "me", "eng_lee", "sales")
    out = generate_openers(store, rid, None)
    assert len(out) == 3
    texts = [o["text"] for o in out]
    assert len(set(texts)) == 3
    cited = [o["evidence_id"] for o in out if o["evidence_id"] is not None]
    assert cited == ["ev_lee_role"]
    for o in out:
        assert set(o) == {"text", "evidence_id", "url", "source"}
        if o["evidence_id"] is None:
            assert o["url"] is None and o["source"] == "template"


def test_owner_pending_carries_display_names(loaded):
    from warmopen.app import make_server
    from warmopen.broker import reachability
    from warmopen.requests import create_request

    server = make_server(loaded, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        rid = create_request(loaded, "me", "eng_lee", "sales")
        reachability(loaded, "owner_b", rid)
        req = urllib.request.Request("http://127.0.0.1:%d/api/owner/owner_b/pending" % server.server_address[1],
                                     headers={"X-Owner-Token": "tok-b"})
        with urllib.request.urlopen(req, timeout=10) as r:
            items = json.load(r)["items"]
        item = next(i for i in items if i["request_id"] == rid)
        assert item["requester_name"] == "Requester Me"
        assert item["target_name"] == "Lee Buyer"
    finally:
        server.shutdown()
    owner_js = (STATIC / "owner.js").read_text()
    assert "requester_name" in owner_js and "target_name" in owner_js


def test_fit_card_explains_abstention_in_words():
    app_js = (STATIC / "app.js").read_text()
    for phrase in ("Not enough public evidence to score.",
                   "The decision model was not confident enough to score.",
                   "Scoring service unavailable. Showing graph reasons only."):
        assert phrase in app_js
    assert "Abstained: ${fit.reason}" not in app_js


def test_revealed_path_connects_requester_with_a_dashed_ask_edge():
    app_js = (STATIC / "app.js").read_text()
    assert "stroke-dasharray" in app_js
    assert "asked" in app_js
