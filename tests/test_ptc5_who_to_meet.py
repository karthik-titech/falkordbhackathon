"""ptc5 frozen contract: "Who should I meet?" in four graph-defined categories,
each showing the Cypher that produced it.

Source: Karthik 2026-10-24: categories 1 the mirror, 2 the missing piece,
3 the unexpected connection (from the ChatGPT brainstorm), plus 4 the intended
target (angel/VC for invest, sales prospect for sales); idea B "show the
Cypher" folded in. Each person appears in at most one category, priority:
target > missing_piece > mirror > unexpected. Only event-graph people are ever
listed; the requester's own meetings count only for that requester.

AMENDMENT 2026-10-24 (ptc4 Astra plan review): own memory is opt-in
(include_own=True); over HTTP only with the requester's valid X-Owner-Token.
"""
import copy
import json
import threading
import urllib.request

import pytest

from conftest import HIDDEN_TEXT

ORDER = ["mirror", "missing_piece", "unexpected", "target"]
LABELS = ["The mirror", "The missing piece", "The unexpected connection", "The intended target"]


@pytest.fixture
def seeking(store, seed):
    from warmopen.seed import load_seed

    data = copy.deepcopy(seed)
    data["startups"][0]["seeking"] = ["graphs"]
    load_seed(store, data)
    return store


def _by_id(result):
    return {c["id"]: c for c in result}


def _ids(category):
    return [item["person"] for item in category["items"]]


def test_four_categories_in_order_with_labels(seeking):
    from warmopen.meet import who_to_meet

    result = who_to_meet(seeking, "me", "invest")
    assert [c["id"] for c in result] == ORDER
    assert [c["label"] for c in result] == LABELS
    for c in result:
        assert set(c) == {"id", "label", "items", "cypher", "params"}
        for item in c["items"]:
            assert set(item) == {"person", "name", "reason", "evidence_id", "url"}
            assert item["reason"]


def test_invest_categories_follow_the_graph(seeking):
    from warmopen.meet import who_to_meet

    cats = _by_id(who_to_meet(seeking, "me", "invest"))
    assert _ids(cats["target"]) == ["vc_kay"]
    assert cats["target"]["items"][0]["evidence_id"] == "ev_fund_thesis"
    assert cats["target"]["items"][0]["url"] == "https://example.org/kay/thesis"
    assert _ids(cats["missing_piece"]) == ["owner_a"]
    assert "Graph databases" in cats["missing_piece"]["items"][0]["reason"]
    assert _ids(cats["mirror"]) == ["topic_twin"]
    assert "Agents" in cats["mirror"]["items"][0]["reason"]
    assert _ids(cats["unexpected"]) == []


def test_sales_target_is_the_buyer(seeking):
    from warmopen.meet import who_to_meet

    cats = _by_id(who_to_meet(seeking, "me", "sales"))
    assert _ids(cats["target"]) == ["eng_lee"]
    assert cats["target"]["items"][0]["evidence_id"] == "ev_company_needs"
    everyone = [p for c in cats.values() for p in _ids(c)]
    assert len(everyone) == len(set(everyone))


def test_a_logged_meeting_creates_an_unexpected_connection(seeking):
    from warmopen.meet import who_to_meet
    from warmopen.memory import log_meeting

    log_meeting(seeking, "me", "tok-me", "eng_lee")
    assert _ids(_by_id(who_to_meet(seeking, "me", "invest"))["unexpected"]) == []  # opt-in
    cats = _by_id(who_to_meet(seeking, "me", "invest", include_own=True))
    assert _ids(cats["unexpected"]) == ["eng_lee"]
    assert "met" in cats["unexpected"]["items"][0]["reason"]
    other = _by_id(who_to_meet(seeking, "topic_twin", "invest", include_own=True))
    assert "eng_lee" not in _ids(other["unexpected"])


def test_shown_cypher_is_the_cypher_that_ran(seeking):
    from warmopen.meet import who_to_meet

    ran = []
    original = seeking.query

    def spy(graph, cypher, params=None):
        ran.append(cypher)
        return original(graph, cypher, params)

    seeking.query = spy
    try:
        result = who_to_meet(seeking, "me", "invest")
    finally:
        seeking.query = original
    for c in result:
        assert c["cypher"] in ran, c["id"]
        assert "me" == c["params"].get("requester")


def test_no_private_people_or_text(seeking):
    from warmopen.meet import who_to_meet

    blob = json.dumps(who_to_meet(seeking, "me", "invest")) + json.dumps(who_to_meet(seeking, "owner_b", "sales"))
    for hidden in HIDDEN_TEXT:
        assert hidden not in blob
    assert "tok-" not in blob


def test_rejects_unknown_requester_or_goal(seeking):
    from warmopen.meet import who_to_meet

    with pytest.raises(ValueError):
        who_to_meet(seeking, "nobody", "invest")
    with pytest.raises(ValueError):
        who_to_meet(seeking, "me", "friendship")


def test_meet_api_and_page(seeking):
    from pathlib import Path

    from warmopen.app import make_server

    server = make_server(seeking, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = "http://127.0.0.1:%d/api/meet?requester=me&goal=invest" % server.server_address[1]
        with urllib.request.urlopen(url, timeout=10) as r:
            body = json.load(r)
        assert body["mode"] == "live"
        assert [c["id"] for c in body["items"]] == ORDER
    finally:
        server.shutdown()
    static = Path(__file__).resolve().parents[1] / "warmopen" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")
    assert 'id="meet-view"' in html
    assert "/api/meet" in js and "details" in js
