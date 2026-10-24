"""Shortest paths in a conference map use bounded cited public edges only."""

import copy


def _path_seed(seed):
    data = copy.deepcopy(seed)
    event = "shortest_event"
    data["conferences"] = [{"id": event, "name": "Shortest Event"}]
    people = ["path_source", "path_middle", "path_target", "path_extra"]
    data["people"].extend({"id": person, "name": person.replace("_", " ").title(),
                           "kind": "attendee", "consented": False} for person in people)
    evidence, edges = [], []
    for number, person in enumerate(people):
        evidence_id = f"shortest_attendance_{number}"
        evidence.append({"id": evidence_id, "url": f"https://example.org/shortest/attendance-{number}",
                         "claim": f"{person} confirmed attendance", "observed_at": "2026-10-20",
                         "visibility": "public"})
        edges.append({"type": "ATTENDS", "from": person, "to": event,
                      "confirmed": True, "evidence": evidence_id})
    for number, (left, right) in enumerate(((people[0], people[1]), (people[1], people[2]))):
        evidence_id = f"shortest_link_{number}"
        evidence.append({"id": evidence_id, "url": f"https://example.org/shortest/link-{number}",
                         "claim": f"{left} and {right} published work together",
                         "observed_at": "2026-10-20", "visibility": "public"})
        edges.append({"type": "COAUTHORED", "from": left, "to": right, "evidence": evidence_id})
    data["evidence"].extend(evidence)
    data["edges"].extend(edges)
    return data


def test_shortest_path_forces_cited_route_nodes_and_edges_into_bounded_graph(store, seed):
    from warmopen.app import _live
    from warmopen.seed import load_seed

    load_seed(store, _path_seed(seed))
    result = _live(store, "POST", "/api/conferences/shortest_event/graph",
                   {"focus": "path_target", "source": "path_source", "limit": 1,
                    "query": "Target"}, None, None, None)
    path = result["shortest_path"]
    assert path["status"] == "ok"
    assert path["persons"] == ["path_source", "path_middle", "path_target"]
    assert path["hops"] == 2
    assert len(path["edges"]) == 2
    assert {item["id"] for item in result["nodes"]} >= set(path["persons"])
    assert {item["id"] for item in result["nodes"]} <= {
        "path_source", "path_middle", "path_target", "path_extra"}
    for edge in path["edges"]:
        assert edge in result["edges"]
        assert edge["evidence_ids"]
        assert set(edge["evidence_ids"]) <= set(result["evidence"])


def test_shortest_path_statuses_cover_missing_invalid_same_and_disconnected_sources(store, seed):
    from warmopen.proximity import conference_graph
    from warmopen.seed import load_seed

    load_seed(store, _path_seed(seed))

    no_source = conference_graph(store, "shortest_event", focus="path_target")
    assert no_source["shortest_path"] == {
        "status": "needs_source", "persons": [], "hops": None, "edges": []}

    invalid = conference_graph(store, "shortest_event", focus="path_target", source="not-listed")
    assert invalid["shortest_path"]["status"] == "source_not_in_roster"

    same = conference_graph(store, "shortest_event", focus="path_target", source="path_target")
    assert same["shortest_path"] == {
        "status": "ok", "persons": ["path_target"], "hops": 0, "edges": []}

    disconnected = conference_graph(store, "shortest_event", focus="path_target", source="path_extra")
    assert disconnected["shortest_path"]["status"] == "no_supported_path"
