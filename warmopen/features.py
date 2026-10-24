"""Abstract graph features and an ordered public evidence allowlist."""

from .broker import revealed_route
from .paths import public_paths
from .requests import get_request


def _public_evidence(store, request, routes):
    # Route edges take priority. Never include evidence from a revealed route.
    ids = [edge["evidence_id"] for route in routes for edge in route["edges"]
           if edge.get("evidence_id")]
    facts = store.query(
        store.event(),
        "MATCH (:Person {id: $target})-[r:SPEAKS_AT|PARTNER_AT|WORKS_AT]->(fact) "
        "RETURN r.evidence_id",
        {"target": request["target"]},
    ).result_set
    supported = store.query(
        store.event(),
        "MATCH (:Person {id: $target})-[:SPEAKS_AT|PARTNER_AT|WORKS_AT]->(fact)"
        "-[:SUPPORTED_BY]->(e:Evidence) RETURN e.id",
        {"target": request["target"]},
    ).result_set
    ids.extend(sorted({row[0] for row in facts + supported if row[0]}))
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []
    rows = store.query(
        store.event(),
        "MATCH (e:Evidence) WHERE e.id IN $ids AND e.visibility = 'public' "
        "RETURN properties(e)", {"ids": ids},
    ).result_set
    evidence = {row[0]["id"]: row[0] for row in rows}
    return [evidence[eid] for eid in ids if eid in evidence]


def _topics(store, person):
    rows = store.query(
        store.event(),
        "MATCH (:Person {id: $id})-[:INTERESTED_IN]->(t:Topic) RETURN t.id "
        "UNION MATCH (:Person {id: $id})-[:SPEAKS_AT]->(:Talk)-[:ABOUT]->(t:Topic) "
        "RETURN t.id", {"id": person},
    ).result_set
    return {row[0] for row in rows}


def _gaps(features):
    result = []
    if features["goal"] == "invest":
        if features["stage_match"] is not True:
            result.append({"id": "gap_stage", "text": "No confirmed startup-stage match with the fund."})
        if not features["sector_overlap_count"]:
            result.append({"id": "gap_sector", "text": "No confirmed sector overlap with the fund."})
    elif features["category_match"] is not True:
        result.append({"id": "gap_category", "text": "No confirmed product-category match with company needs."})
    if not features["public_route_count"] and not features["revealed"]:
        result.append({"id": "gap_no_warm_route", "text": "No public or approved warm route is available."})
    return result


def extract_features(store, request_id, include_own=False):
    """Return only numbers, flags, nulls, and fixed goal/route labels."""
    request = get_request(store, request_id)
    public = public_paths(store, request["requester"], request["target"],
                          include_own=include_own)
    revealed = revealed_route(store, request_id)
    startups = [row[0] for row in store.query(
        store.event(),
        "MATCH (:Person {id: $id})-[:FOUNDED]->(s:Startup) RETURN properties(s)",
        {"id": request["requester"]},
    ).result_set]
    stage_match = sector_overlap = category_match = None
    if request["goal"] == "invest":
        funds = [row[0] for row in store.query(
            store.event(),
            "MATCH (:Person {id: $id})-[:PARTNER_AT]->(f:Fund) RETURN properties(f)",
            {"id": request["target"]},
        ).result_set]
        stages = {stage for fund in funds for stage in fund.get("stages", [])}
        startup_stages = {s["stage"] for s in startups if s.get("stage")}
        if stages and startup_stages:
            stage_match = bool(stages & startup_stages)
        sectors = {sector for fund in funds for sector in fund.get("sectors", [])}
        startup_sectors = {sector for s in startups for sector in s.get("sectors", [])}
        if any("sectors" in s for s in startups) and any("sectors" in f for f in funds):
            sector_overlap = len(sectors & startup_sectors)
    else:
        companies = [row[0] for row in store.query(
            store.event(),
            "MATCH (:Person {id: $id})-[:WORKS_AT]->(c:Company) RETURN properties(c)",
            {"id": request["target"]},
        ).result_set]
        needs = {need for company in companies for need in company.get("needs", [])}
        categories = {s["product_category"] for s in startups if s.get("product_category")}
        if categories and any("needs" in c for c in companies):
            category_match = bool(categories & needs)
    links = {(edge["category"], tuple(sorted((edge["from"], edge["to"]))))
             for route in public for edge in route["edges"]}
    min_tie = min(edge["tie"] for edge in revealed["edges"]) if revealed else None
    routes = [{"route_id": route["route_id"], "hops": route["hops"],
               "min_tie": None, "kind": "public"} for route in public]
    if revealed:
        routes.append({"route_id": revealed["route_id"], "hops": revealed["hops"],
                       "min_tie": min_tie, "kind": "revealed"})
    features = {
        "goal": request["goal"], "public_route_count": len(public),
        "best_public_hops": min((r["hops"] for r in public), default=None),
        "revealed": revealed is not None,
        "revealed_hops": revealed["hops"] if revealed else None,
        "revealed_min_tie": min_tie,
        "shared_work_links": sum(kind == "shared_work" for kind, _ in links),
        "co_speaker_links": sum(kind == "co_speaker" for kind, _ in links),
        "coauthor_links": sum(kind == "coauthor" for kind, _ in links),
        "topic_overlap_count": len(_topics(store, request["requester"]) &
                                   _topics(store, request["target"])),
        "stage_match": stage_match, "sector_overlap_count": sector_overlap,
        "category_match": category_match,
        "evidence_count": len(_public_evidence(store, request, public)),
        "gaps_count": 0, "routes": routes,
    }
    features["gaps_count"] = len(_gaps(features))
    return features


def gaps(store, request_id, include_own=False):
    """List missing or unmatched fit facts, then a missing warm route."""
    return _gaps(extract_features(store, request_id, include_own=include_own))
