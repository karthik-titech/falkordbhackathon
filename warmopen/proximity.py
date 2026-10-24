"""Conference people connected by directly cited public graph facts."""

from collections import defaultdict, deque

from .conversation import public_pair_context, validate_topic_ids
from .directory import conference_people
from .target_plan import _adjacency

MAX_PEOPLE = 72
MAX_EDGES = 600
MAX_HOPS = 6
DEFAULT_LIMIT = 48
_LINK_CATEGORIES = {"co_speaker", "shared_work", "coauthor"}


def _roster(store, conference_id):
    people = {}
    directory = conference_people(store, conference_id)
    for item in directory["confirmed_attendees"]:
        people[item["id"]] = {"id": item["id"], "name": item["name"],
                              "roles": {"confirmed_attendee"}}
    for item in directory["scheduled_speakers"]:
        person = people.setdefault(item["id"], {
            "id": item["id"], "name": item["name"], "roles": set()})
        person["roles"].add("scheduled_speaker")
    return people


def conference_graph(store, conference_id, focus=None, query="", limit=DEFAULT_LIMIT,
                    source=None, interest_topic_ids=None, seeking_topic_ids=None):
    """Return a bounded public graph whose nodes are listed for this conference."""
    if focus is not None:
        if not isinstance(focus, str) or not focus.strip():
            raise ValueError("Invalid focus profile")
        focus = focus.strip()
    if not isinstance(query, str) or len(query) > 120:
        raise ValueError("Invalid name filter")
    if type(limit) is not int or not 1 <= limit <= MAX_PEOPLE:
        raise ValueError("Limit must be between 1 and 72")
    interest_topic_ids = validate_topic_ids(store, conference_id,
                                             [] if interest_topic_ids is None else interest_topic_ids,
                                             "interest_topic_ids")
    seeking_topic_ids = validate_topic_ids(store, conference_id,
                                            [] if seeking_topic_ids is None else seeking_topic_ids,
                                            "seeking_topic_ids")

    roster = _roster(store, conference_id)
    if focus is not None and focus not in roster:
        raise ValueError("Focus profile must be listed for this conference")

    # _adjacency keeps only links with valid public evidence on each side and never
    # opens an owner graph when include_own is false.
    adjacency = _adjacency(store, "", False)
    roster_ids = set(roster)
    grouped = {}
    for edge_source, links in adjacency.items():
        if edge_source not in roster_ids:
            continue
        for link in links:
            destination, category = link["to"], link["category"]
            if destination not in roster_ids or category not in _LINK_CATEGORIES:
                continue
            left, right = sorted((edge_source, destination))
            key = left, right, category
            edge = grouped.setdefault(key, {"source": left, "target": right,
                                             "category": category, "evidence_ids": set()})
            for evidence_id in (link.get("evidence_id"), link.get("other_evidence_id")):
                if evidence_id:
                    edge["evidence_ids"].add(evidence_id)

    neighbors = defaultdict(set)
    for edge in grouped.values():
        neighbors[edge["source"]].add(edge["target"])
        neighbors[edge["target"]].add(edge["source"])

    if focus is None and roster:
        focus = min(roster, key=lambda person_id: (
            -len(neighbors[person_id]), (roster[person_id]["name"] or "").casefold(), person_id))

    distances = {}
    if focus is not None:
        distances[focus] = 0
        frontier = deque([focus])
        while frontier:
            person_id = frontier.popleft()
            distance = distances[person_id]
            if distance >= MAX_HOPS:
                continue
            for neighbor in sorted(neighbors[person_id]):
                if neighbor not in distances:
                    distances[neighbor] = distance + 1
                    frontier.append(neighbor)

    filter_text = query.strip().casefold()
    matching = [person for person in roster.values()
                if not filter_text or filter_text in (person["name"] or "").casefold()]
    if focus is not None and focus not in {person["id"] for person in matching}:
        matching.append(roster[focus])

    def order(person):
        person_id = person["id"]
        distance = distances.get(person_id)
        return (0 if person_id == focus else 1,
                distance if distance is not None else MAX_HOPS + 1,
                (person["name"] or "").casefold(), person_id)

    ordered = sorted(matching, key=order)
    shown = ordered[:limit]
    shown_ids = {person["id"] for person in shown}
    edges = [{**edge, "evidence_ids": sorted(edge["evidence_ids"])}
             for edge in grouped.values()
             if edge["source"] in shown_ids and edge["target"] in shown_ids]
    edges.sort(key=lambda edge: (
        min(distances.get(edge["source"], MAX_HOPS + 1),
            distances.get(edge["target"], MAX_HOPS + 1)),
        edge["source"], edge["target"], edge["category"]))
    total_edge_count = len(edges)
    edges = edges[:MAX_EDGES]
    nodes = [{"id": person["id"], "name": person["name"],
              "roles": sorted(person["roles"]), "distance": distances.get(person["id"])}
             for person in shown]

    compare_nodes = source is not None or interest_topic_ids or seeking_topic_ids
    for node in nodes:
        if not compare_nodes or source == node["id"]:
            node.update({"connection_type": None, "reason_code": "needs_context",
                         "reason": "Select a profile or conference topics to compare.",
                         "context_evidence_ids": []})
            continue
        context = public_pair_context(store, source, node["id"],
                                      interest_topic_ids=interest_topic_ids,
                                      seeking_topic_ids=seeking_topic_ids)
        node.update({"connection_type": (None if context["connection_type"] == "unknown"
                                         else context["connection_type"]),
                     "reason_code": context["reason_code"],
                     "reason": context["reason"],
                     "context_evidence_ids": context["evidence_ids"]})

    return {
        "conference_id": conference_id,
        "center_id": focus,
        "nodes": nodes,
        "edges": edges,
        "total_count": len(matching),
        "roster_count": len(roster),
        "total_edge_count": total_edge_count,
        "truncated": len(shown) < len(matching) or total_edge_count > MAX_EDGES,
        "comparison_source": source,
        "interest_topic_ids": interest_topic_ids,
        "seeking_topic_ids": seeking_topic_ids,
    }
