"""Idempotent conference loading with evidence partitioned by visibility."""

import hashlib

from .ties import tie_strength

_NODES = {
    "people": ("Person", ("id", "name", "handle", "kind", "consented")),
    "talks": ("Talk", ("id", "title", "conference", "starts", "room")),
    "topics": ("Topic", ("id", "name")),
    "repos": ("Repo", ("id", "full_name")),
    "companies": ("Company", ("id", "name", "needs", "sectors", "topics")),
    "interests": ("Interest", ("id", "name")),
    "funds": ("Fund", ("id", "name", "stages", "sectors")),
    "startups": ("Startup", ("id", "name", "stage", "sectors", "product_category", "seeking")),
}
_FACTS = {
    "SPEAKS_AT": ("Person", "Talk"), "ABOUT": ("Talk", "Topic"),
    "INTERESTED_IN": ("Person", "Topic"), "CONTRIBUTED_TO": ("Person", "Repo"),
    "MAINTAINS": ("Person", "Repo"), "COAUTHORED": ("Person", "Person"),
    "WORKS_AT": ("Person", "Company"), "PARTNER_AT": ("Person", "Fund"),
    "FOUNDED": ("Person", "Startup"),
    "INVESTED_IN": ("Fund", "Company"), "ENJOYS": ("Person", "Interest"),
}
_EVIDENCE_FIELDS = ("id", "url", "claim", "observed_at", "visibility")
_CATEGORIES = ("colleague", "coauthor", "friend", "met")


def _evidence_id(record):
    return record.get("evidence_id", record.get("evidence"))


def _node(store, graph, label, properties):
    store.query(graph, f"MERGE (n:{label} {{id: $id}}) SET n += $properties",
                {"id": properties["id"], "properties": properties})


def _edge(store, graph, kind, source_label, source, target_label, target, properties=None):
    store.query(graph,
                f"MATCH (a:{source_label} {{id: $source}}), (b:{target_label} {{id: $target}}) "
                f"MERGE (a)-[r:{kind}]->(b) SET r += $properties",
                {"source": source, "target": target, "properties": properties or {}})


def _counts(store, graph):
    nodes = store.query(graph, "MATCH (n) RETURN count(n)").result_set[0][0]
    edges = store.query(graph, "MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    return nodes, edges


def load_seed(store, seed: dict) -> dict:
    public_refs = {_evidence_id(record)
                   for section in (*_NODES, "edges") for record in seed.get(section, [])}
    private = seed.get("private", {})
    evidence = {item["id"]: item for item in seed.get("evidence", [])}
    private_refs = {}
    for owner, section in private.items():
        local_evidence = section.get("evidence", [])
        refs = {_evidence_id(item) for item in section.get("knows", [])}
        refs.update(item["id"] for item in local_evidence)
        private_refs[owner] = refs - {None}
    private_only = set().union(*private_refs.values()) - public_refs if private_refs else set()
    excluded = private_only | {eid for eid, item in evidence.items()
                               if item.get("visibility") == "private"}
    # Owner-local evidence stays private even if it is absent from the top-level list.
    excluded.update(item["id"] for section in private.values()
                    for item in section.get("evidence", []))
    public_evidence = set(evidence) - excluded
    people = {person["id"]: person for person in seed.get("people", [])}
    owners = {pid for pid, person in people.items()
              if person.get("consented") and person.get("owner_token") is not None} | set(private)

    # Validate relationship types and strengths before starting the import.
    for fact in seed.get("edges", []):
        if fact["type"] not in _FACTS:
            raise ValueError("Unknown public fact type")
        if fact["type"] in ("INVESTED_IN", "ENJOYS") and _evidence_id(fact) not in evidence:
            raise ValueError("Hook facts require evidence")
    for owner, section in private.items():
        if owner not in people or not people[owner].get("consented"):
            raise ValueError("Private graph owner must be a consenting public person")
        for fact in section.get("knows", []):
            if fact["category"] not in _CATEGORIES:
                raise ValueError("Unknown private relationship category")
            tie_strength(fact.get("features", {}), fact.get("owner_strength"))

    with store.lock:
        event = store.event()
        store.query(event,
                    "MATCH (e:Evidence) WHERE e.id IN $excluded DETACH DELETE e",
                    {"excluded": sorted(excluded)})
        store.query(event,
                    "MATCH ()-[r]->() WHERE r.evidence_id IN $excluded REMOVE r.evidence_id",
                    {"excluded": sorted(excluded)})

        def support(label, node_id, eid):
            if eid in public_evidence:
                _edge(store, event, "SUPPORTED_BY", label, node_id, "Evidence", eid)

        for section, (label, fields) in _NODES.items():
            for item in seed.get(section, []):
                _node(store, event, label, {key: item[key] for key in fields if key in item})
        for eid in sorted(public_evidence):
            item = evidence[eid]
            _node(store, event, "Evidence",
                  {key: item[key] for key in _EVIDENCE_FIELDS if key in item})
        for section, (label, _) in _NODES.items():
            for item in seed.get(section, []):
                support(label, item["id"], _evidence_id(item))

        def fact(kind, source, target, eid=None, properties=None):
            source_label, target_label = _FACTS[kind]
            props = dict(properties or {})
            props["evidence_id"] = eid if eid not in excluded else None
            _edge(store, event, kind, source_label, source, target_label, target, props)
            support(source_label, source, eid)

        for talk in seed.get("talks", []):
            for speaker in talk.get("speakers", []):
                fact("SPEAKS_AT", speaker, talk["id"], _evidence_id(talk))
            for topic in talk.get("topics", []):
                fact("ABOUT", talk["id"], topic, _evidence_id(talk))
        for startup in seed.get("startups", []):
            for founder in startup.get("founders", []):
                fact("FOUNDED", founder, startup["id"], _evidence_id(startup))
        for company in seed.get("companies", []):
            for topic in company.get("topics", []):
                _edge(store, event, "ABOUT", "Company", company["id"], "Topic", topic)
        for item in seed.get("edges", []):
            if item["type"] in ("INVESTED_IN", "ENJOYS"):
                source = evidence[_evidence_id(item)]
                if (_evidence_id(item) not in public_evidence or source.get("visibility") != "public"
                        or not isinstance(source.get("url"), str) or not source["url"].strip()
                        or not isinstance(source.get("claim"), str) or not source["claim"].strip()):
                    continue
            props = {key: item[key] for key in ("role", "round", "lead") if key in item}
            fact(item["type"], item["from"], item["to"], _evidence_id(item), props)

        private_nodes = private_edges = 0
        for owner in sorted(owners):
            graph = store.private(owner)
            section = private.get(owner, {})
            owner_person = people[owner]
            if owner_person.get("owner_token") is not None:
                store.query(graph,
                            "MERGE (c:OwnerCredential {id: $id}) "
                            "SET c.token_sha256 = $digest REMOVE c.token",
                            {"id": owner, "digest": hashlib.sha256(
                                owner_person["owner_token"].encode("utf-8")).hexdigest()})
            names = {item["id"]: item.get("name", item["id"])
                     for item in section.get("people", [])}
            ids = {owner} | set(names)
            for item in section.get("knows", []):
                ids.update((item["from"], item["to"]))
            for pid in sorted(ids):
                name = names.get(pid, people.get(pid, {}).get("name", pid))
                _node(store, graph, "Person", {"id": pid, "name": name, "owner": pid == owner})
            owner_evidence = dict(evidence)
            owner_evidence.update((item["id"], item) for item in section.get("evidence", []))
            for eid in sorted(private_refs.get(owner, ())):
                if eid in owner_evidence:
                    item = owner_evidence[eid]
                    _node(store, graph, "Evidence",
                          {key: item[key] for key in _EVIDENCE_FIELDS if key in item})
            for item in section.get("knows", []):
                strength, source = tie_strength(item.get("features", {}), item.get("owner_strength"))
                eid = _evidence_id(item)
                _edge(store, graph, "KNOWS", "Person", item["from"], "Person", item["to"],
                      {"category": item["category"], "strength": strength,
                       "strength_source": source, "evidence_id": eid})
                if eid in owner_evidence:
                    _edge(store, graph, "SUPPORTED_BY", "Person", item["from"], "Evidence", eid)
            node_count, edge_count = _counts(store, graph)
            private_nodes += node_count
            private_edges += edge_count
        event_nodes, event_edges = _counts(store, event)
        return {"event_nodes": event_nodes, "event_edges": event_edges,
                "private_graphs": len(owners), "private_nodes": private_nodes,
                "private_edges": private_edges}
