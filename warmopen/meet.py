"""Graph-derived people to meet, with the queries used to find them."""

from .paths import OWN_LINKS_CYPHER, WARM_LINKS_CYPHER, public_paths
from .requests import GOALS, _person

_REQUESTER_TOPICS = (
    "MATCH (requester:Person {id: $requester}) "
    "OPTIONAL MATCH (requester)-[:INTERESTED_IN|SPEAKS_AT|ABOUT*1..2]->(own:Topic) "
    "WITH collect(DISTINCT own.id) AS requester_topics "
)
MIRROR_CYPHER = (
    "MATCH (requester:Person {id: $requester})-[:INTERESTED_IN|SPEAKS_AT|ABOUT*1..2]->(t:Topic) "
    "WITH DISTINCT t "
    "MATCH (p:Person)-[:INTERESTED_IN|SPEAKS_AT|ABOUT*1..2]->(t:Topic) "
    "WHERE p.kind IS NOT NULL AND p.id <> $requester AND NOT p.id IN $excluded "
    "OPTIONAL MATCH (p)-[:SPEAKS_AT]->(talk:Talk)-[:ABOUT]->(t) "
    "OPTIONAL MATCH (talk)-[:SUPPORTED_BY]->(e:Evidence {visibility: 'public'}) "
    "RETURN DISTINCT p.id, p.name, t.id, t.name, e.id, e.url "
    "ORDER BY p.name, p.id, t.name, e.id"
)
MISSING_PIECE_CYPHER = (
    _REQUESTER_TOPICS +
    "MATCH (:Person {id: $requester})-[:FOUNDED]->(s:Startup) "
    "WITH requester_topics, s "
    "MATCH (p:Person)-[:SPEAKS_AT]->(talk:Talk)-[:ABOUT]->(t:Topic) "
    "WHERE p.kind IS NOT NULL AND p.id <> $requester AND NOT p.id IN $excluded "
    "AND t.id IN coalesce(s.seeking, []) "
    "OPTIONAL MATCH (p)-[:INTERESTED_IN|SPEAKS_AT|ABOUT*1..2]->(other:Topic) "
    "WHERE other.id IN requester_topics "
    "WITH p, talk, t, count(other) AS shared_topics "
    "WHERE shared_topics = 0 "
    "OPTIONAL MATCH (talk)-[:SUPPORTED_BY]->(e:Evidence {visibility: 'public'}) "
    "RETURN DISTINCT p.id, p.name, t.id, t.name, e.id, e.url "
    "ORDER BY p.name, p.id, t.name, e.id"
)
TARGET_INVEST_CYPHER = (
    "MATCH (:Person {id: $requester})-[:FOUNDED]->(s:Startup), "
    "(p:Person)-[:PARTNER_AT]->(f:Fund) "
    "WHERE p.kind IS NOT NULL AND p.id <> $requester "
    "AND (s.stage IN coalesce(f.stages, []) OR "
    "any(sector IN coalesce(s.sectors, []) WHERE sector IN coalesce(f.sectors, []))) "
    "OPTIONAL MATCH (f)-[:SUPPORTED_BY]->(e:Evidence {visibility: 'public'}) "
    "RETURN p.id, p.name, f.name, s.stage, s.sectors, f.stages, f.sectors, e.id, e.url "
    "ORDER BY p.name, p.id, f.id, e.id"
)
TARGET_SALES_CYPHER = (
    "MATCH (:Person {id: $requester})-[:FOUNDED]->(s:Startup), "
    "(p:Person)-[:WORKS_AT]->(c:Company) "
    "WHERE p.kind IS NOT NULL AND p.id <> $requester "
    "AND s.product_category IN coalesce(c.needs, []) "
    "OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence {visibility: 'public'}) "
    "RETURN p.id, p.name, c.name, s.product_category, e.id, e.url "
    "ORDER BY p.name, p.id, c.id, e.id"
)


def _item(person, name, reason, evidence_id=None, url=None):
    return {"person": person, "name": name, "reason": reason,
            "evidence_id": evidence_id, "url": url}


def _topic_items(rows, missing=False):
    people = {}
    for person, name, topic, topic_name, evidence_id, url in rows:
        entry = people.setdefault(person, {"name": name, "topics": {}, "citation": (None, None)})
        entry["topics"][topic] = topic_name or topic
        if evidence_id and entry["citation"][0] is None:
            entry["citation"] = evidence_id, url
    ordered = sorted(people, key=lambda person: (
        0 if missing else -len(people[person]["topics"]), people[person]["name"] or "", person))
    items = []
    for person in ordered:
        entry = people[person]
        topics = ", ".join(sorted(entry["topics"].values()))
        reason = (f"Speaks on {topics}, which you are looking for." if missing
                  else f"Also works on {topics}.")
        items.append(_item(person, entry["name"], reason, *entry["citation"]))
    return items


def who_to_meet(store, requester, goal, k=3, include_own=False):
    """Assign each public person once, before limiting each column to k items."""
    if goal not in GOALS:
        raise ValueError("Unknown goal")
    _person(store, requester)
    target_query = TARGET_INVEST_CYPHER if goal == "invest" else TARGET_SALES_CYPHER
    target_params = {"requester": requester}
    target_rows = store.query(store.event(), target_query, target_params).result_set
    targets = {}
    for row in target_rows:
        person, name, organization = row[:3]
        if goal == "invest":
            stage, sectors, stages, fund_sectors, evidence_id, url = row[3:]
            matches = []
            if stage and stage in (stages or []):
                matches.append("stage " + stage)
            overlap = sorted(set(sectors or []) & set(fund_sectors or []))
            if overlap:
                matches.append("sectors " + ", ".join(overlap))
            reason = f"{organization} invests in {' and '.join(matches)}."
        else:
            need, evidence_id, url = row[3:]
            reason = f"{organization} needs {need}."
        item = _item(person, name, reason, evidence_id, url)
        if person not in targets or (evidence_id and not targets[person]["evidence_id"]):
            targets[person] = item

    missing_params = {"requester": requester, "excluded": sorted(targets)}
    missing = _topic_items(store.query(
        store.event(), MISSING_PIECE_CYPHER, missing_params).result_set, missing=True)
    reserved = set(targets) | {item["person"] for item in missing}
    mirror_params = {"requester": requester, "excluded": sorted(reserved)}
    mirrors = _topic_items(store.query(store.event(), MIRROR_CYPHER, mirror_params).result_set)
    reserved.update(item["person"] for item in mirrors)

    # Show the same warm-link or requester-own-edge query used by public_paths.
    unexpected_query = OWN_LINKS_CYPHER if include_own else WARM_LINKS_CYPHER
    unexpected_params = {"requester": requester}
    store.query(store.private(requester) if include_own else store.event(),
                unexpected_query, unexpected_params)
    people = dict(store.query(
        store.event(), "MATCH (p:Person) WHERE p.kind IS NOT NULL RETURN p.id, p.name",
    ).result_set)
    unexpected = []
    for person in sorted(people, key=lambda pid: (people[pid] or "", pid)):
        if person == requester or person in reserved or len(unexpected) >= max(0, k):
            continue
        routes = public_paths(store, requester, person, max_hops=3, include_own=include_own)
        if not routes:
            continue
        route = routes[0]
        first = route["edges"][0]
        reason = ("You met them." if route["hops"] == 1 and first["category"] == "met"
                  else f"via {people.get(first['to']) or first['to']} ({first['category']})")
        evidence_id = next((edge["evidence_id"] for edge in route["edges"]
                            if edge.get("evidence_id")), None)
        citation = store.query(
            store.event(), "MATCH (e:Evidence {id: $id, visibility: 'public'}) RETURN e.id, e.url",
            {"id": evidence_id},
        ).result_set if evidence_id else []
        unexpected.append(_item(person, people[person], reason, *(citation[0] if citation else (None, None))))

    limit = max(0, k)
    return [{"id": category, "label": label, "items": items[:limit], "cypher": query, "params": params}
            for category, label, items, query, params in (
                ("mirror", "The mirror", mirrors, MIRROR_CYPHER, mirror_params),
                ("missing_piece", "The missing piece", missing, MISSING_PIECE_CYPHER, missing_params),
                ("unexpected", "The unexpected connection", unexpected, unexpected_query, unexpected_params),
                ("target", "The intended target", list(targets.values()), target_query, target_params),
            )]
