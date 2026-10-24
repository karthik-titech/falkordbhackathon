"""Read-only public profile exploration helpers."""

from .target_plan import _adjacency, _evidence, _valid_evidence, public_try_paths

_GENERIC = (
    "What are you hoping to learn at this conference?",
    "Which session has been most useful to you?",
    "What problem is your team exploring next?",
)


def _template(evidence, number):
    if evidence is None:
        return {"text": _GENERIC[number], "evidence_id": None, "url": None, "source": "template"}
    claim = " ".join(evidence["claim"].split()).rstrip(".,;:!? ")
    ending = "What would you add?"
    limit = min(245, 280 - len("I read: . ") - len(ending))
    excerpt = claim if len(claim) <= limit else claim[:limit - 1].rstrip(".,;:!? ") + "…"
    return {"text": "I read: " + excerpt + ". " + ending,
            "evidence_id": evidence["id"], "url": evidence["url"], "source": "template"}


def public_people(store):
    rows = store.query(store.event(),
                       "MATCH (p:Person) WHERE p.kind IS NOT NULL AND p.name IS NOT NULL "
                       "RETURN p.id, p.name ORDER BY p.name, p.id").result_set
    return [{"id": person_id, "name": name} for person_id, name in rows]


def public_example(store, people=None):
    """Choose a directly cited public co-speaker or shared-work pair, if any."""
    person_ids = {item["id"] for item in (people if people is not None else public_people(store))}
    adjacency = _adjacency(store, "", False)
    candidates = [(0 if edge["category"] == "co_speaker" else 1,
                   source, edge["to"])
                  for source, edges in adjacency.items() for edge in edges
                  if edge["category"] in ("co_speaker", "shared_work")
                  and source in person_ids and edge["to"] in person_ids and source != edge["to"]]
    if not candidates:
        return None
    _rank, source, target = min(candidates)
    return {"source": source, "target": target}


def explore_public(store, source, target, action):
    """Return cited public paths or three evidence-backed/generic opener templates."""
    if action not in ("paths", "openers"):
        raise ValueError("Unknown public exploration action")
    if not isinstance(source, str) or not isinstance(target, str) or source == target:
        raise ValueError("Choose two different public people")
    available = {item["id"] for item in public_people(store)}
    if source not in available or target not in available:
        from .errors import NotFound

        raise NotFound("Unknown public person")

    routes, truncated = public_try_paths(store, source, target)
    result = {"routes": routes, "truncated": truncated}
    if action == "paths":
        return result

    public_ids = [edge["evidence_id"] for route in routes for edge in route["edges"]
                  if edge.get("evidence_id")]
    public_ids.extend(edge["other_evidence_id"] for route in routes for edge in route["edges"]
                      if edge.get("other_evidence_id"))
    facts = store.query(
        store.event(),
        "MATCH (:Person {id: $target})-[r:SPEAKS_AT|PARTNER_AT|WORKS_AT]->(fact) "
        "RETURN r.evidence_id AS evidence_id UNION "
        "MATCH (:Person {id: $target})-[:SPEAKS_AT|PARTNER_AT|WORKS_AT]->(fact)"
        "-[:SUPPORTED_BY]->(e:Evidence) RETURN e.id AS evidence_id",
        {"target": target},
    ).result_set
    public_ids.extend(row[0] for row in facts if row[0])
    public_map = _evidence(store, public_ids)
    public = [public_map[eid] for eid in dict.fromkeys(public_ids) if eid in public_map]
    allowed, seen = [], set()
    for item in public:
        if item.get("id") in seen or not _valid_evidence(item):
            continue
        seen.add(item["id"])
        allowed.append(item)
    result["openers"] = [
        _template(allowed[index] if index < len(allowed) else None, index)
        for index in range(3)
    ]
    return result
