"""Read-only public profile exploration API and template contracts."""

import json
from pathlib import Path

import pytest


def test_public_profile_list_includes_public_people_without_consent_filter(loaded):
    from warmopen.app import _live

    response = _live(loaded, "GET", "/api/try/people", None, None, None, None)
    people = response["items"]
    assert {item["id"] for item in people} >= {"me", "vc_kay", "eng_lee"}
    assert all(item["name"] for item in people)
    assert response["example"] and response["example"]["source"] != response["example"]["target"]
    pair = response["example"]
    route = _live(loaded, "POST", "/api/try", {**pair, "action": "paths"}, None, None, None)["routes"][0]
    assert route["hops"] == 1
    assert route["edges"][0]["category"] in ("co_speaker", "shared_work")


def test_paths_are_public_cited_bounded_and_read_only(loaded, monkeypatch):
    from warmopen.app import _live

    monkeypatch.setattr(loaded, "private", lambda *_: pytest.fail("public exploration touched private graph"))
    before = (
        loaded.query(loaded.event(), "MATCH (n) RETURN count(n)").result_set[0][0],
        loaded.query(loaded.event(), "MATCH ()-[r]->() RETURN count(r)").result_set[0][0],
    )
    result = _live(loaded, "POST", "/api/try",
                   {"source": "me", "target": "vc_kay", "action": "paths"},
                   "ignored-token", lambda _: pytest.fail("public exploration called provider"),
                   lambda _: pytest.fail("public exploration called writer"))
    after = (
        loaded.query(loaded.event(), "MATCH (n) RETURN count(n)").result_set[0][0],
        loaded.query(loaded.event(), "MATCH ()-[r]->() RETURN count(r)").result_set[0][0],
    )
    assert before == after
    assert result["routes"]
    route = result["routes"][0]
    assert route["hops"] <= 6
    assert route["persons"][0] == "me" and route["persons"][-1] == "vc_kay"
    assert all(edge["evidence_id"] in result["evidence"] for edge in route["edges"])
    assert result["people"]["owner_a"] == "Owner A"


def test_public_search_limit_is_reported_even_when_no_route_is_found(loaded, monkeypatch):
    from warmopen import target_plan
    from warmopen.app import _live

    monkeypatch.setattr(target_plan, "MAX_EXPANSIONS", 0)
    result = _live(loaded, "POST", "/api/try",
                   {"source": "me", "target": "vc_kay", "action": "paths"}, None, None, None)
    assert result["routes"] == []
    assert result["truncated"] is True


def test_openers_are_three_public_source_templates_without_requests_or_provider(loaded, monkeypatch):
    from warmopen.app import _live

    monkeypatch.setattr(loaded, "private", lambda *_: pytest.fail("public exploration touched private graph"))
    before = (loaded.query(loaded.event(), "MATCH (n) RETURN count(n)").result_set[0][0],
              loaded.query(loaded.event(), "MATCH ()-[r]->() RETURN count(r)").result_set[0][0])
    result = _live(loaded, "POST", "/api/try",
                   {"source": "me", "target": "vc_kay", "action": "openers"},
                   None, lambda _: pytest.fail("public opener action called provider"),
                   lambda _: pytest.fail("public opener action called model"))
    after = (loaded.query(loaded.event(), "MATCH (n) RETURN count(n)").result_set[0][0],
             loaded.query(loaded.event(), "MATCH ()-[r]->() RETURN count(r)").result_set[0][0])
    assert before == after
    assert len(result["openers"]) == 3
    assert all(item["text"] and len(item["text"]) <= 280 for item in result["openers"])
    assert all(item["evidence_id"] is None or item["evidence_id"] in result["evidence"]
               for item in result["openers"])
    encoded = json.dumps(result)
    for hidden in ("Carol Hidden", "carol_hidden", "ev_private_b", "worked with Carol"):
        assert hidden not in encoded


def test_explore_api_rejects_extra_fields_and_same_profile(loaded):
    from warmopen.app import _live

    with pytest.raises(ValueError, match="Expected source"):
        _live(loaded, "POST", "/api/try",
             {"source": "me", "target": "vc_kay", "action": "paths", "requester_token": "x"},
             None, None, None)
    with pytest.raises(ValueError, match="two different"):
        _live(loaded, "POST", "/api/try",
             {"source": "me", "target": "me", "action": "paths"}, None, None, None)


def test_public_try_page_is_separate_and_uses_safe_dom_rendering():
    static = Path(__file__).resolve().parents[1] / "warmopen" / "static"
    html = (static / "try.html").read_text(encoding="utf-8")
    js = (static / "try.js").read_text(encoding="utf-8")
    assert "Explore public profile connections" in html
    assert "does not" in html and "physical presence" in html
    assert "innerHTML" not in js
    for secret_control in ("requester-token", "X-Owner-Token", "localStorage"):
        assert secret_control not in js
    for private_profile_input in ("warmopen_profile_links", "profile-linkedin", "profile-x"):
        assert private_profile_input not in js
    assert 'fetch("/api/profile/enrich"' not in js
    assert "Explore public connections" in (static / "index.html").read_text(encoding="utf-8")
