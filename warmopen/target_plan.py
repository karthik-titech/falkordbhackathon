"""Target-centered conference journeys from cited attendance and warm links."""

from collections import defaultdict
from datetime import datetime, timezone
import math
from urllib.parse import urlsplit

from .paths import OWN_LINKS_CYPHER

MAX_HOPS = 6
MAX_EXPANSIONS = 5000
MAX_ROUTES = 12
_PRIVATE_CATEGORIES = {"colleague", "coauthor", "friend", "met"}
_CITED_LINKS = (
    "MATCH (a:Person)-[r:COAUTHORED]-(b:Person) "
    "RETURN a.id AS source, b.id AS destination, 'coauthor' AS category, "
    "r.evidence_id AS evidence, r.evidence_id AS other_evidence UNION "
    "MATCH (a:Person)-[r:CONTRIBUTED_TO|MAINTAINS]->(:Repo)"
    "<-[s:CONTRIBUTED_TO|MAINTAINS]-(b:Person) WHERE a.id <> b.id "
    "RETURN a.id AS source, b.id AS destination, 'shared_work' AS category, "
    "r.evidence_id AS evidence, s.evidence_id AS other_evidence UNION "
    "MATCH (a:Person)-[r:SPEAKS_AT]->(:Talk)<-[s:SPEAKS_AT]-(b:Person) "
    "WHERE a.id <> b.id RETURN a.id AS source, b.id AS destination, "
    "'co_speaker' AS category, r.evidence_id AS evidence, s.evidence_id AS other_evidence"
)


def _valid_evidence(item):
    if not isinstance(item, dict) or item.get("visibility") != "public":
        return False
    url, claim = item.get("url"), item.get("claim")
    if not isinstance(url, str) or not url.strip() or not isinstance(claim, str) or not claim.strip():
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _evidence(store, ids):
    ids = sorted({item for item in ids if isinstance(item, str) and item})
    if not ids:
        return {}
    rows = store.query(store.event(),
                       "MATCH (e:Evidence) WHERE e.id IN $ids RETURN properties(e)",
                       {"ids": ids}).result_set
    return {row[0]["id"]: row[0] for row in rows if row and _valid_evidence(row[0])}


def _attendance(store, conference_id):
    rows = store.query(store.event(),
                       "MATCH (p:Person)-[r:ATTENDS]->(:Conference {id: $conference}), (e:Evidence) "
                       "WHERE r.confirmed = true AND e.id = r.evidence_id "
                       "AND e.visibility = 'public' "
                       "RETURN p.id, e.id", {"conference": conference_id}).result_set
    evidence = _evidence(store, [row[1] for row in rows])
    return {pid: eid for pid, eid in rows if eid in evidence}


def _talk_at(store, person, conference_id):
    rows = store.query(store.event(),
                       "MATCH (:Person {id: $person})-[r:SPEAKS_AT]->(t:Talk) "
                       "WHERE t.conference = $conference RETURN r.evidence_id",
                       {"person": person, "conference": conference_id}).result_set
    evidence = _evidence(store, [row[0] for row in rows if row[0]])
    return next((row[0] for row in rows if row[0] in evidence), None)


def _as_date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _timing(conference, today=None):
    today = today or datetime.now(timezone.utc).date()
    starts, ends = _as_date(conference.get("starts")), _as_date(conference.get("ends"))
    if starts and starts > today:
        return "future"
    if starts and starts <= today <= (ends or starts):
        return "current"
    return "past_or_unknown"


def conference_options(store, target, timing_filter=None):
    """List current target appearances and future confirmed target attendance."""
    rows = store.query(store.event(), "MATCH (c:Conference) RETURN properties(c)").result_set
    options = []
    for row in rows:
        conference = row[0]
        timing = _timing(conference)
        if timing_filter is not None and timing != timing_filter:
            continue
        if timing == "current":
            target_source = _attendance(store, conference["id"]).get(target)
            if not target_source:
                target_source = _talk_at(store, target, conference["id"])
        elif timing == "future":
            target_source = _attendance(store, conference["id"]).get(target)
        else:
            continue
        if target_source:
            options.append({"id": conference["id"], "name": conference.get("name") or conference["id"],
                            "starts": conference.get("starts"), "ends": conference.get("ends"),
                            "timing": timing, "evidence_id": target_source})
    return sorted(options, key=lambda item: (item["starts"] or "", item["name"], item["id"]))


def _adjacency(store, requester, include_own, attendees=None):
    rows = store.query(store.event(), _CITED_LINKS, {}).result_set
    evidence = _evidence(store, [eid for row in rows for eid in row[3:] if eid])
    adjacency = defaultdict(list)
    for source, destination, category, eid, other_eid in rows:
        if eid in evidence and other_eid in evidence:
            adjacency[source].append({"from": source, "to": destination,
                                      "category": category, "evidence_id": eid,
                                      "other_evidence_id": other_eid})
    if include_own and attendees is not None:
        public_ids = {row[0] for row in store.query(
            store.event(), "MATCH (p:Person) WHERE p.kind IS NOT NULL RETURN p.id").result_set}
        own = store.query(store.private(requester), OWN_LINKS_CYPHER,
                          {"requester": requester}).result_set
        first_hops = {edge["to"] for edge in adjacency[requester]}
        for destination, category in sorted(set(map(tuple, own))):
            if (destination in public_ids and destination in attendees and destination not in first_hops
                    and category in _PRIVATE_CATEGORIES):
                adjacency[requester].append({"from": requester, "to": destination,
                                             "category": category, "evidence_id": None})
                first_hops.add(destination)
    for edges in adjacency.values():
        edges.sort(key=lambda edge: (edge["to"], edge["category"], edge["evidence_id"] or ""))
    return adjacency


def _rank_routes(routes, attendance, require_attendance=True):
    routes.sort(key=lambda route: (
        route["hops"], -sum(edge["evidence_id"] is not None for edge in route["edges"]),
        -(len(route["persons"]) > 2 and route["persons"][1] in attendance), route["persons"],
        [(edge["category"], edge["evidence_id"] or "") for edge in route["edges"]],
    ))
    output = []
    for number, route in enumerate(routes[:MAX_ROUTES], 1):
        first_intermediary = route["persons"][1] if len(route["persons"]) > 2 else None
        intermediaries = ([{"person": first_intermediary,
                           "evidence_id": attendance[first_intermediary]}]
                          if require_attendance and first_intermediary in attendance else [])
        output.append({"route_id": f"route_{number}", **route, "intermediaries": intermediaries})
    return output


def _journey_routes(store, requester, target, conference_id=None, include_own=False,
                    require_attendance=True):
    attendance = _attendance(store, conference_id) if require_attendance else {}
    if require_attendance:
        target_source = attendance.get(target) or _talk_at(store, target, conference_id)
        if not target_source:
            return [], attendance, False
    adjacency = _adjacency(store, requester, include_own,
                           set(attendance) if require_attendance else None)
    routes, expansions, truncated = [], 0, False
    frontier = [([requester], [])]
    for depth in range(1, MAX_HOPS + 1):
        next_frontier = []
        for persons, edges in frontier:
            for edge in adjacency[persons[-1]]:
                expansions += 1
                if expansions > MAX_EXPANSIONS:
                    truncated = True
                    return _rank_routes(routes, attendance, require_attendance), attendance, truncated
                destination = edge["to"]
                if destination in persons:
                    continue
                if (require_attendance and depth == 1
                        and (destination == target or destination not in attendance)):
                    continue
                next_persons, next_edges = persons + [destination], edges + [edge]
                if destination == target:
                    if depth >= (2 if require_attendance else 1):
                        routes.append({"hops": depth, "persons": next_persons, "edges": next_edges})
                    if len(routes) >= MAX_ROUTES * 4:
                        truncated = True
                        return _rank_routes(routes, attendance, require_attendance), attendance, truncated
                elif depth < MAX_HOPS:
                    next_frontier.append((next_persons, next_edges))
        if not next_frontier:
            break
        frontier = next_frontier
    return _rank_routes(routes, attendance, require_attendance), attendance, truncated


def public_try_paths(store, source, target):
    """Bounded public cited paths for the read-only profile exploration page."""
    if source == target:
        return [], False
    routes, _attendance_facts, truncated = _journey_routes(
        store, source, target, require_attendance=False)
    return routes, truncated


def _model_choice(jev, goal, timing, target_confirmed, routes, attendance):
    abstain = {"choice": None, "abstained": True, "source": "deterministic"}
    if jev is None or not routes:
        return abstain
    features = {
        "goal": goal, "conference_timing": timing, "target_confirmed": bool(target_confirmed),
        "route_count": len(routes),
        "routes": [{"route_id": route["route_id"], "hops": route["hops"],
                    "supported_edge_count": sum(edge["evidence_id"] is not None for edge in route["edges"]),
                    "confirmed_attendance_count": int(route["persons"][1] in attendance)}
                   for route in routes],
    }
    criteria = {route["route_id"]: "Choose this supported route using fewer hops and confirmed attendance."
                for route in routes}
    criteria.update({"APPROACH_DIRECTLY": "Use no route.",
                     "INSUFFICIENT_EVIDENCE": "Abstain from choosing a route."})
    payload = {"model": "jev-latest", "state": features,
               "questions": {"route": {"type": "choice",
                   "instructions": "Select one fixed route label, APPROACH_DIRECTLY, or INSUFFICIENT_EVIDENCE.",
                   "criteria": criteria}}}
    try:
        decision = jev(payload)["answers"]["route"]
        choice, confidence = decision["choice"], decision["confidence"]
    except Exception:
        return abstain
    if (not isinstance(choice, str) or choice not in criteria
            or type(confidence) not in (int, float) or not math.isfinite(confidence)
            or not 0 <= confidence <= 1 or confidence < 0.6):
        return abstain
    if choice == "INSUFFICIENT_EVIDENCE":
        return {"choice": None, "abstained": True, "source": "model"}
    return {"choice": choice, "abstained": False, "source": "model"}


def plan_conference(store, request, conference_id, jev=None, include_own=False):
    rows = store.query(store.event(), "MATCH (c:Conference {id: $id}) RETURN properties(c)",
                       {"id": conference_id}).result_set
    if not rows:
        raise ValueError("Unknown conference")
    option = next((item for item in conference_options(store, request["target"])
                   if item["id"] == conference_id), None)
    if not option:
        return {"conference": None, "routes": [], "intermediaries": [],
                "decision": {"choice": None, "abstained": True, "source": "deterministic"},
                "reason": "No cited target attendance or current conference appearance."}
    routes, attendance, truncated = _journey_routes(
        store, request["requester"], request["target"], conference_id, include_own=include_own)
    decision = _model_choice(jev, request["goal"], option["timing"], request["target"] in attendance,
                             routes, attendance)
    if decision["choice"] and decision["choice"].startswith("route_"):
        routes.sort(key=lambda route: route["route_id"] != decision["choice"])
    intermediaries, seen = [], set()
    for route in routes:
        for item in route["intermediaries"]:
            if item["person"] not in seen:
                seen.add(item["person"])
                intermediaries.append(item)
    return {"conference": option, "routes": routes, "intermediaries": intermediaries,
            "decision": decision, "truncated": truncated,
            "reason": None if routes else "No cited attending connection reaches this target."}


def future_conferences(store, request, jev=None, include_own=False):
    results = []
    for conference in conference_options(store, request["target"], timing_filter="future"):
        plan = plan_conference(store, request, conference["id"], jev=jev, include_own=include_own)
        if plan["routes"]:
            results.append(plan)
    return results
