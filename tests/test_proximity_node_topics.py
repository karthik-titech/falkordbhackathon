"""Conference map topic badges require citations on public professional facts."""

import copy


def test_graph_nodes_include_only_cited_professional_topics_and_sources(store, seed):
    from warmopen.app import _live
    from warmopen.seed import load_seed

    data = copy.deepcopy(seed)
    data["conferences"] = [{"id": "ghu", "name": "Graph Gathering"}]
    data["evidence"].append({"id": "me_conference_attendance",
                             "url": "https://example.org/ghu/me-attending",
                             "claim": "Requester Me confirmed attendance", "observed_at": "2026-10-20",
                             "visibility": "public"})
    data["edges"].append({"type": "ATTENDS", "from": "me", "to": "ghu",
                          "confirmed": True, "evidence": "me_conference_attendance"})
    load_seed(store, data)

    result = _live(store, "POST", "/api/conferences/ghu/graph",
                   {"focus": "vc_kay", "limit": 48}, None, None, None)
    nodes = {node["id"]: node for node in result["nodes"]}
    assert nodes["me"]["topics"] == []
    assert nodes["owner_a"]["topics"] == [{
        "id": "graphs", "name": "Graph databases", "evidence_ids": ["ev_talk_pair"]}]
    assert nodes["vc_kay"]["topics"] == [
        {"id": "agents", "name": "Agents", "evidence_ids": ["ev_talk_kay"]},
        {"id": "graphs", "name": "Graph databases", "evidence_ids": ["ev_talk_pair"]},
    ]
    for evidence_id in ("ev_talk_kay", "ev_talk_pair"):
        assert evidence_id in result["evidence"]
