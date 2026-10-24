"""Conference people connected by directly cited public graph facts."""

from collections import defaultdict, deque

from .conversation import (_person_topics, _source_seeking, _topic_names, conference_topics,
                          public_pair_context, related_topic_pairs, validate_topic_ids)
from .directory import conference_people
from .target_plan import _adjacency
from .tryflow import public_people

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


def _shortest_path(source, target, roster_ids, neighbors, grouped):
    empty = {"persons": [], "hops": None, "edges": []}
    if source is None:
        return {"status": "needs_source", **empty}
    if source not in roster_ids:
        return {"status": "source_not_in_roster", **empty}
    if target is None or target not in roster_ids:
        return {"status": "no_supported_path", **empty}
    if source == target:
        return {"status": "ok", "persons": [source], "hops": 0, "edges": []}

    previous = {source: None}
    depths = {source: 0}
    frontier = deque([source])
    while frontier:
        person_id = frontier.popleft()
        if depths[person_id] >= MAX_HOPS:
            continue
        for neighbor in sorted(neighbors[person_id]):
            if neighbor in previous:
                continue
            previous[neighbor] = person_id
            depths[neighbor] = depths[person_id] + 1
            if neighbor == target:
                frontier.clear()
                break
            frontier.append(neighbor)
    if target not in previous:
        return {"status": "no_supported_path", **empty}

    persons = [target]
    while persons[-1] != source:
        persons.append(previous[persons[-1]])
    persons.reverse()
    path_edges = []
    for left, right in zip(persons, persons[1:]):
        pair_edges = [edge for edge in grouped.values()
                      if {edge["source"], edge["target"]} == {left, right}]
        pair_edges.sort(key=lambda edge: (edge["category"], sorted(edge["evidence_ids"])))
        if not pair_edges:
            return {"status": "no_supported_path", **empty}
        edge = pair_edges[0]
        path_edges.append({"source": edge["source"], "target": edge["target"],
                           "category": edge["category"],
                           "evidence_ids": sorted(edge["evidence_ids"])})
    return {"status": "ok", "persons": persons, "hops": len(path_edges), "edges": path_edges}


def conference_graph(store, conference_id, focus=None, query="", limit=DEFAULT_LIMIT,
                    source=None, interest_topic_ids=None, seeking_topic_ids=None):
    """Return a bounded public graph whose nodes are listed for this conference."""
    if focus is not None:
        if not isinstance(focus, str) or not focus.strip():
            raise ValueError("Invalid focus profile")
        focus = focus.strip()
    if source is not None:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Invalid source profile")
        source = source.strip()
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

    person_topics = _person_topics(store, roster_ids)

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

    shortest_path = _shortest_path(source, focus, roster_ids, neighbors, grouped)
    valid_source = source if source in roster_ids else None

    filter_text = query.strip().casefold()
    matching_by_id = {person["id"]: person for person in roster.values()
                      if not filter_text or filter_text in (person["name"] or "").casefold()}
    for required_id in (focus, valid_source):
        if required_id is not None:
            matching_by_id.setdefault(required_id, roster[required_id])
    if shortest_path["status"] == "ok":
        for required_id in shortest_path["persons"]:
            matching_by_id.setdefault(required_id, roster[required_id])
    matching = list(matching_by_id.values())

    def order(person):
        person_id = person["id"]
        distance = distances.get(person_id)
        return (0 if person_id == focus else 1,
                distance if distance is not None else MAX_HOPS + 1,
                (person["name"] or "").casefold(), person_id)

    ordered = sorted(matching, key=order)
    required_ids = {person_id for person_id in (focus, valid_source) if person_id is not None}
    if shortest_path["status"] == "ok":
        required_ids.update(shortest_path["persons"])
    required_people = [person for person in ordered if person["id"] in required_ids]
    optional_people = [person for person in ordered if person["id"] not in required_ids]
    shown = required_people + optional_people[:max(0, limit - len(required_people))]
    shown_ids = {person["id"] for person in shown}
    edges = [{**edge, "evidence_ids": sorted(edge["evidence_ids"])}
             for edge in grouped.values()
             if edge["source"] in shown_ids and edge["target"] in shown_ids]
    edges.sort(key=lambda edge: (
        min(distances.get(edge["source"], MAX_HOPS + 1),
            distances.get(edge["target"], MAX_HOPS + 1)),
        edge["source"], edge["target"], edge["category"]))
    total_edge_count = len(edges)
    path_edge_keys = {(edge["source"], edge["target"], edge["category"])
                      for edge in shortest_path["edges"]}
    path_edges = [edge for edge in edges
                  if (edge["source"], edge["target"], edge["category"]) in path_edge_keys]
    other_edges = [edge for edge in edges
                   if (edge["source"], edge["target"], edge["category"]) not in path_edge_keys]
    edges = path_edges + other_edges[:max(0, MAX_EDGES - len(path_edges))]
    nodes = []
    for person in shown:
        topics = person_topics.get(person["id"], {})
        nodes.append({
            "id": person["id"], "name": person["name"],
            "roles": sorted(person["roles"]), "distance": distances.get(person["id"]),
            "topics": [{"id": topic_id, "name": topic.get("name") or topic_id,
                        "evidence_ids": sorted(topic["evidence_ids"])}
                       for topic_id, topic in sorted(
                           topics.items(), key=lambda row: ((row[1].get("name") or row[0]).casefold(), row[0]))],
        })

    declared_names = _topic_names(store, interest_topic_ids) if interest_topic_ids else {}
    source_topics = person_topics.get(valid_source, {}) if valid_source else {}
    related_sources = dict(source_topics)
    related_sources.update({topic_id: {"name": declared_names.get(topic_id, topic_id)}
                            for topic_id in interest_topic_ids if topic_id not in related_sources})
    sought_topics, seeking_evidence = _source_seeking(store, valid_source)
    route_evidence = _routes_from_source(store, valid_source, roster_ids)
    compare_nodes = valid_source is not None or interest_topic_ids or seeking_topic_ids
    source_evidence = {eid for topic in source_topics.values() for eid in topic["evidence_ids"]}
    for node in nodes:
        if not compare_nodes or valid_source == node["id"]:
            node.update({"connection_type": None, "reason_code": "needs_context",
                         "reason": "Select a profile or conference topics to compare.",
                         "context_evidence_ids": []})
            continue
        target_topics = person_topics.get(node["id"], {})
        sought = (sought_topics | set(seeking_topic_ids)) & set(target_topics)
        shared = (set(source_topics) | set(interest_topic_ids)) & set(target_topics)
        related = related_topic_pairs(related_sources, target_topics)
        if sought:
            category, code, reason = "missing_piece", "desired_capability_overlap", "Cited work covers a capability you are looking for."
        elif shared:
            category, code, reason = "mirror", "shared_public_topics", "Cited work matches your selected interests or comparison profile."
        elif related:
            category, code, reason = "unexpected_connection", "related_professional_topics", "Related expertise offers a different angle on your professional interests."
        elif route_evidence.get(node["id"]):
            category, code, reason = "unexpected_connection", "cited_warm_route", "A cited public-work path connects these profiles."
        else:
            category, code, reason = None, "no_supported_basis", "No shared or related professional topic is supported yet."
        evidence_ids = source_evidence | seeking_evidence | set(route_evidence.get(node["id"], []))
        evidence_ids.update(eid for topic in target_topics.values() for eid in topic["evidence_ids"])
        node.update({"connection_type": category, "reason_code": code, "reason": reason,
                     "context_evidence_ids": sorted(evidence_ids)})

    return {
        "conference_id": conference_id,
        "center_id": focus,
        "shortest_path": shortest_path,
        "nodes": nodes,
        "edges": edges,
        "total_count": len(matching),
        "roster_count": len(roster),
        "total_edge_count": total_edge_count,
        "truncated": len(shown) < len(matching) or total_edge_count > MAX_EDGES,
        "comparison_source": valid_source,
        "interest_topic_ids": interest_topic_ids,
        "seeking_topic_ids": seeking_topic_ids,
    }


def _routes_from_source(store, source, targets):
    """Find deterministic cited paths once for all conference targets."""
    if source is None or not targets:
        return {}
    grouped = {}
    for edge_source, links in _adjacency(store, "", False).items():
        for link in links:
            left, right = sorted((edge_source, link["to"]))
            key = left, right, link["category"]
            edge = grouped.setdefault(key, {"source": left, "target": right,
                                             "category": link["category"], "evidence_ids": set()})
            edge["evidence_ids"].update(eid for eid in
                                        (link.get("evidence_id"), link.get("other_evidence_id")) if eid)
    neighbors = defaultdict(list)
    for edge in grouped.values():
        neighbors[edge["source"]].append((edge["target"], edge))
        neighbors[edge["target"]].append((edge["source"], edge))
    for links in neighbors.values():
        links.sort(key=lambda row: (row[0], row[1]["category"], sorted(row[1]["evidence_ids"])))
    previous, previous_edge, depths = {source: None}, {}, {source: 0}
    frontier = deque([source])
    expansions = 0
    while frontier and expansions < 5000:
        person_id = frontier.popleft()
        if depths[person_id] >= MAX_HOPS:
            continue
        for neighbor, edge in neighbors[person_id]:
            expansions += 1
            if expansions > 5000:
                break
            if neighbor in previous:
                continue
            previous[neighbor] = person_id
            previous_edge[neighbor] = edge
            depths[neighbor] = depths[person_id] + 1
            frontier.append(neighbor)
    paths = {}
    for target in targets:
        if target == source or target not in previous:
            continue
        evidence_ids = set()
        cursor = target
        while cursor != source:
            evidence_ids.update(previous_edge[cursor]["evidence_ids"])
            cursor = previous[cursor]
        if evidence_ids:
            paths[target] = evidence_ids
    return paths


def conference_matches(store, conference_id, source=None, interest_topic_ids=None,
                       seeking_topic_ids=None):
    """Classify the full conference roster from cited topics and public routes."""
    if source is not None:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Invalid source profile")
        source = source.strip()
        public_ids = {item["id"] for item in public_people(store)}
        if source not in public_ids:
            raise ValueError("Source profile must be a listed public person")

    interest_topic_ids = validate_topic_ids(
        store, conference_id, [] if interest_topic_ids is None else interest_topic_ids,
        "interest_topic_ids")
    seeking_topic_ids = validate_topic_ids(
        store, conference_id, [] if seeking_topic_ids is None else seeking_topic_ids,
        "seeking_topic_ids")
    catalog = {topic["id"]: topic for topic in conference_topics(store, conference_id)}
    directory = conference_people(store, conference_id)
    roster = {}
    for role in ("confirmed_attendees", "scheduled_speakers"):
        for person in directory[role]:
            roster[person["id"]] = {"id": person["id"], "name": person["name"]}

    people_ids = set(roster)
    if source is not None:
        people_ids.add(source)
    topic_data = _person_topics(store, people_ids)
    source_topics = topic_data.get(source, {}) if source else {}
    source_seeking, seeking_evidence = _source_seeking(store, source)
    declared_interest = {
        topic_id: {"name": catalog[topic_id]["name"], "evidence_ids": set()}
        for topic_id in interest_topic_ids if topic_id in catalog}
    related_sources = dict(source_topics)
    related_sources.update({key: value for key, value in declared_interest.items()
                            if key not in related_sources})
    declared_seeking = set(seeking_topic_ids)
    names = _topic_names(store, set(source_seeking) | declared_seeking)
    seeking_names = {topic_id: {"name": names.get(topic_id, catalog.get(topic_id, {}).get("name", topic_id)),
                                "evidence_ids": set(seeking_evidence)}
                     for topic_id in source_seeking | declared_seeking}

    route_evidence = _routes_from_source(store, source, roster)
    totals = {name: 0 for name in ("missing_piece", "mirror", "unexpected_connection", "unclassified")}
    items = []
    for person_id, person in sorted(roster.items(), key=lambda row: (
            (row[1]["name"] or "").casefold(), row[0])):
        target_topics = {topic_id: topic for topic_id, topic in topic_data.get(person_id, {}).items()
                         if topic_id in catalog}
        evidence_ids = set()
        pairs = []
        category, reason = "unclassified", "No matching cited topic or supported public route was found."
        if person_id == source:
            reason = "This is the selected public comparison profile."
        else:
            sought_ids = (source_seeking | declared_seeking) & set(target_topics)
            shared_ids = (set(source_topics) | set(interest_topic_ids)) & set(target_topics)
            if sought_ids:
                category = "missing_piece"
                reason = "The target has cited work on a capability being sought."
                for topic_id in sorted(sought_ids):
                    target_topic = target_topics[topic_id]
                    source_topic = seeking_names[topic_id]
                    pairs.append({"source": {"id": topic_id, "name": source_topic["name"]},
                                  "target": {"id": topic_id, "name": target_topic["name"]},
                                  "relation": "seeking"})
                    evidence_ids.update(source_topic["evidence_ids"])
                    evidence_ids.update(target_topic["evidence_ids"])
            elif shared_ids:
                category = "mirror"
                reason = "The target has cited work matching a shared professional topic."
                for topic_id in sorted(shared_ids):
                    target_topic = target_topics[topic_id]
                    source_topic = related_sources.get(topic_id, target_topic)
                    pairs.append({"source": {"id": topic_id, "name": source_topic["name"]},
                                  "target": {"id": topic_id, "name": target_topic["name"]},
                                  "relation": "shared"})
                    evidence_ids.update(source_topic["evidence_ids"])
                    evidence_ids.update(target_topic["evidence_ids"])
            else:
                related = related_topic_pairs(related_sources, target_topics)
                if related:
                    category = "unexpected_connection"
                    reason = "The cited professional topics are adjacent."
                    pairs = related
                    for pair in related:
                        evidence_ids.update(related_sources[pair["source"]["id"]]["evidence_ids"])
                        evidence_ids.update(target_topics[pair["target"]["id"]]["evidence_ids"])
                elif route_evidence.get(person_id):
                    category = "unexpected_connection"
                    reason = "A cited public route connects the profiles."
                    evidence_ids.update(route_evidence[person_id])
        totals[category] += 1
        items.append({"id": person_id, "name": person["name"], "category": category,
                      "reason": reason, "topics": pairs,
                      "evidence_ids": sorted(evidence_ids)})
    return {"conference_id": conference_id, "source": source,
            "total_count": len(items), "unclassified_count": totals["unclassified"],
            "totals": totals, "items": items}
