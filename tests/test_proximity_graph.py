"""Conference proximity graph is bounded, public, cited, and read-only."""

import copy

import pytest


def _chain_seed(seed, length=7):
    data = copy.deepcopy(seed)
    conference = "proximity_conference"
    data["conferences"] = [{"id": conference, "name": "Proximity Conference"}]
    people = [f"proximity_{number}" for number in range(length + 1)]
    data["people"].extend({"id": person, "name": f"Proximity Person {number}",
                          "handle": person, "kind": "attendee", "consented": False}
                         for number, person in enumerate(people))
    evidence, edges = [], []
    for number, person in enumerate(people):
        eid = f"proximity_attendance_{number}"
        evidence.append({"id": eid, "url": f"https://example.org/proximity/attend-{number}",
                         "claim": f"Person {number} confirmed attendance", "observed_at": "2030-05-01",
                         "visibility": "public"})
        edges.append({"type": "ATTENDS", "from": person, "to": conference,
                      "confirmed": True, "evidence": eid})
    for number, (left, right) in enumerate(zip(people, people[1:])):
        eid = f"proximity_link_{number}"
        evidence.append({"id": eid, "url": f"https://example.org/proximity/link-{number}",
                         "claim": f"People {number} and {number + 1} coauthored work",
                         "observed_at": "2030-05-01", "visibility": "public"})
        edges.append({"type": "COAUTHORED", "from": left, "to": right, "evidence": eid})
    data["evidence"].extend(evidence)
    data["edges"].extend(edges)
    return data, people


def test_graph_endpoint_uses_only_cited_edges_between_conference_people(store, seed, monkeypatch):
    from warmopen.app import _live
    from warmopen.seed import load_seed

    data, _ = _chain_seed(seed, length=2)
    load_seed(store, data)
    monkeypatch.setattr(store, "private", lambda *_: pytest.fail("proximity graph opened a private graph"))
    before = store.dump("event")
    result = _live(store, "POST", "/api/conferences/proximity_conference/graph",
                   {"focus": "proximity_0", "limit": 48}, "ignored-token",
                   lambda _: pytest.fail("proximity graph called a model"),
                   lambda _: pytest.fail("proximity graph called a writer"))
    assert store.dump("event") == before
    assert result["center_id"] == "proximity_0"
    assert [(item["id"], item["distance"]) for item in result["nodes"]] == [
        ("proximity_0", 0), ("proximity_1", 1), ("proximity_2", 2)]
    assert all(item["roles"] == ["confirmed_attendee"] for item in result["nodes"])
    assert {(edge["source"], edge["target"], edge["category"]) for edge in result["edges"]} == {
        ("proximity_0", "proximity_1", "coauthor"),
        ("proximity_1", "proximity_2", "coauthor"),
    }
    assert all(edge["evidence_ids"] for edge in result["edges"])
    assert all(evidence_id in result["evidence"] for edge in result["edges"]
               for evidence_id in edge["evidence_ids"])


def test_default_focus_uses_highest_degree_and_distances_stop_at_six_hops(store, seed):
    from warmopen.proximity import conference_graph
    from warmopen.seed import load_seed

    data, people = _chain_seed(seed, length=7)
    load_seed(store, data)
    result = conference_graph(store, "proximity_conference")
    assert result["center_id"] == people[1]
    bounded = conference_graph(store, "proximity_conference", focus=people[0])
    by_id = {item["id"]: item for item in bounded["nodes"]}
    assert by_id[people[6]]["distance"] == 6
    assert by_id[people[7]]["distance"] is None


def test_name_filter_preserves_focus_and_limit_sets_truncated(store, seed):
    from warmopen.proximity import conference_graph
    from warmopen.seed import load_seed

    data, people = _chain_seed(seed, length=4)
    load_seed(store, data)
    filtered = conference_graph(store, "proximity_conference", focus=people[0], query="person 4")
    assert {item["id"] for item in filtered["nodes"]} == {people[0], people[4]}
    assert filtered["total_count"] == 2
    limited = conference_graph(store, "proximity_conference", focus=people[0], limit=2)
    assert [item["id"] for item in limited["nodes"]] == people[:2]
    assert limited["total_count"] == 5
    assert limited["truncated"] is True


def test_own_topics_do_not_inherit_routes_from_an_unselected_demo_profile(loaded):
    from warmopen.app import _live

    result = _live(loaded, "POST", "/api/conferences/ghu/graph",
                   {"interest_topic_ids": ["graphs"]}, None, None, None)
    assert result["comparison_source"] is None
    assert result["nodes"]
    assert all(node["connection_type"] == "mirror" for node in result["nodes"])


def test_graph_endpoint_rejects_unknown_focus_extra_fields_and_bad_limits(loaded):
    from warmopen.app import _live

    path = "/api/conferences/ghu/graph"
    with pytest.raises(ValueError, match="Unexpected conference graph fields"):
        _live(loaded, "POST", path, {"focus": "owner_a", "other": "ignored"}, None, None, None)
    with pytest.raises(ValueError, match="Focus profile"):
        _live(loaded, "POST", path, {"focus": "not-in-conference"}, None, None, None)
    with pytest.raises(ValueError, match="Limit"):
        _live(loaded, "POST", path, {"limit": True}, None, None, None)
