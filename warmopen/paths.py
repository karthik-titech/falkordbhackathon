"""Warm public links from graph facts, excluding topic overlap."""

from collections import defaultdict

from .requests import _person


def public_paths(store, requester, target, max_hops=3, k=3, include_own=False) -> list[dict]:
    _person(store, requester)
    _person(store, target)
    if max_hops < 1 or k < 1 or requester == target:
        return []
    # The graph derives person-to-person links from their supporting public facts.
    links = store.query(store.event(),
                        "MATCH (a:Person)-[r:COAUTHORED]-(b:Person) "
                        "RETURN a.id AS source, b.id AS destination, "
                        "'coauthor' AS category, r.evidence_id AS evidence "
                        "UNION "
                        "MATCH (a:Person)-[r:CONTRIBUTED_TO|MAINTAINS]->(work:Repo)"
                        "<-[:CONTRIBUTED_TO|MAINTAINS]-(b:Person) WHERE a.id <> b.id "
                        "RETURN a.id AS source, b.id AS destination, "
                        "'shared_work' AS category, r.evidence_id AS evidence "
                        "UNION "
                        "MATCH (a:Person)-[r:SPEAKS_AT]->(talk:Talk)<-[:SPEAKS_AT]-(b:Person) "
                        "WHERE a.id <> b.id "
                        "RETURN a.id AS source, b.id AS destination, "
                        "'co_speaker' AS category, r.evidence_id AS evidence").result_set
    adjacency = defaultdict(list)
    best_links = {}
    for source, destination, category, evidence in links:
        rank = (evidence is None, category, evidence or "")
        pair = source, destination
        if pair not in best_links or rank < best_links[pair]:
            best_links[pair] = rank
    for (source, destination), (_, category, evidence) in sorted(best_links.items()):
        adjacency[source].append({"from": source, "to": destination,
                                  "category": category, "evidence_id": evidence or None})
    first_hops = list(adjacency[requester])
    if include_own:
        public_ids = {row[0] for row in store.query(
            store.event(), "MATCH (p:Person) WHERE p.kind IS NOT NULL RETURN p.id",
        ).result_set}
        own = store.query(store.private(requester),
                          "MATCH (:Person {id: $requester})-[r:KNOWS]->(b:Person) "
                          "RETURN b.id, r.category", {"requester": requester}).result_set
        destinations = {edge["to"] for edge in first_hops}
        for destination, category in sorted(set(map(tuple, own))):
            if destination in public_ids and destination not in destinations:
                first_hops.append({"from": requester, "to": destination,
                                   "category": category, "evidence_id": None})
                destinations.add(destination)
    routes = []
    frontier = [([requester], [])]
    for _ in range(max_hops):
        next_frontier = []
        for persons, edges in frontier:
            for edge in first_hops if len(persons) == 1 else adjacency[persons[-1]]:
                destination = edge["to"]
                if destination in persons:
                    continue
                next_persons, next_edges = persons + [destination], edges + [edge]
                if destination == target:
                    routes.append({"hops": len(next_edges), "persons": next_persons,
                                   "edges": next_edges})
                else:
                    next_frontier.append((next_persons, next_edges))
        # All routes at this depth have been found, so longer ones cannot rank first.
        if len(routes) >= k:
            break
        frontier = next_frontier
        if not frontier:
            break
    routes.sort(key=lambda route: (
        route["hops"], -sum(edge["evidence_id"] is not None for edge in route["edges"]),
        route["persons"],
        [(edge["category"], edge["evidence_id"] or "") for edge in route["edges"]],
    ))
    return [dict(route_id=f"public_{number}", **route)
            for number, route in enumerate(routes[:k], 1)]
