"""Private reachability offers and separately authorized route disclosure."""

import json
import secrets

from .agentlog import _log_locked
from .consent import _check_owner, _time, has_grant
from .errors import NotFound
from .requests import StateError, _advance_locked, get_request


def _answer(status, hops=None, tie=None, offer_id=None):
    return {"status": status, "hops": hops, "tie": tie, "offer_id": offer_id}


def _copy_people(store, people):
    for person in people:
        store.query(store.event(),
                    "MERGE (p:Person {id: $id}) ON CREATE SET p.name = $name",
                    {"id": person["id"], "name": person["name"]})


def revealed_route(store, request_id):
    """Read only the snapshot committed with this request's approval."""
    request = get_request(store, request_id)
    if request["state"] not in ("approved", "requested"):
        return None
    route = request.get("revealed_route")
    return json.loads(route) if route else None


def reachability(store, owner, request_id, now=None):
    with store.lock:
        request = get_request(store, request_id)
        _check_owner(store, owner)
        at = _time(now)
        granted = has_grant(store, owner, request["requester"], request_id, "reachability", now=at)
        store.query(store.event(),
                    "MERGE (a:Ask {request_id: $id, owner: $owner}) SET a.at = $at",
                    {"id": request_id, "owner": owner, "at": at})
        _log_locked(store, request_id, "broker", "reachability_asked")
        if not granted:
            _log_locked(store, request_id, "broker", "reachability_answered")
            return _answer("no_consent")
        rows = store.query(store.private(owner),
                           "MATCH p = (:Person {id: $owner})-[:KNOWS*1..2]->"
                           "(:Person {id: $target}) "
                           "RETURN [n IN nodes(p) | properties(n)], "
                           "[r IN relationships(p) | properties(r)]",
                           {"owner": owner, "target": request["target"]}).result_set
        candidates = []
        for people, relationships in rows:
            persons = [person["id"] for person in people]
            if len(set(persons)) != len(persons):
                continue
            tie = min(edge["strength"] for edge in relationships)
            candidates.append((people, relationships, tie))
        if not candidates:
            _log_locked(store, request_id, "broker", "reachability_answered")
            return _answer("unavailable")
        people, relationships, tie = min(candidates, key=lambda item: (
            len(item[1]), -item[2], [person["id"] for person in item[0]],
            json.dumps(item[1], sort_keys=True),
        ))
        persons = [person["id"] for person in people]
        edges = [{"from": persons[i], "to": persons[i + 1], "category": edge["category"],
                  "evidence_id": edge.get("evidence_id"), "tie": edge["strength"]}
                 for i, edge in enumerate(relationships)]
        route = {"route_id": "revealed_1", "hops": len(edges), "persons": persons, "edges": edges}
        offer_id = secrets.token_urlsafe(16)
        # No route data, evidence, private ids, or names are written to the shared offer.
        store.query(store.private(owner),
                    "CREATE (:OfferRoute {id: $offer, route: $route, people: $people})",
                    {"offer": offer_id, "route": json.dumps(route, sort_keys=True),
                     "people": json.dumps(people, sort_keys=True)})
        store.query(store.event(),
                    "MATCH (r:Request {id: $id}) "
                    "CREATE (r)-[:HAS_OFFER]->(:Offer {id: $offer, request_id: $id, "
                    "owner: $owner, hops: $hops, tie: $tie})",
                    {"id": request_id, "offer": offer_id, "owner": owner,
                     "hops": len(edges), "tie": tie})
        if request["state"] == "draft":
            _advance_locked(store, request_id, "draft", "awaiting_approval")
        _log_locked(store, request_id, "broker", "reachability_answered")
        return _answer("reachable", len(edges), tie, offer_id)


def reveal(store, owner, request_id, offer_id, now=None):
    with store.lock:
        offers = store.query(store.event(),
                             "MATCH (o:Offer {id: $offer, owner: $owner, request_id: $id}) "
                             "RETURN o.id",
                             {"offer": offer_id, "owner": owner, "id": request_id}).result_set
        if not offers:
            raise NotFound("Unknown offer for this owner and request")
        request = get_request(store, request_id)
        # An existing disclosure survives expiry or revocation of its original grant.
        if request.get("revealed_offer_id") == offer_id:
            if request["state"] not in ("approved", "requested"):
                raise StateError("This request has no approved route")
            rows = store.query(store.private(owner),
                               "MATCH (p:OfferRoute {id: $offer}) RETURN p.people",
                               {"offer": offer_id}).result_set
            if not rows:
                raise NotFound("Unknown private offer route")
            _copy_people(store, json.loads(rows[0][0]))
            _log_locked(store, request_id, "broker", "route_revealed")
            return json.loads(request["revealed_route"])
        at = _time(now)
        if not has_grant(store, owner, request["requester"], request_id, "reveal", now=at):
            raise PermissionError("Route reveal requires a separate owner grant")
        if request["state"] != "awaiting_approval" or request.get("revealed_offer_id"):
            raise StateError("This request cannot reveal another route")
        rows = store.query(store.private(owner),
                           "MATCH (p:OfferRoute {id: $offer}) RETURN p.route, p.people",
                           {"offer": offer_id}).result_set
        if not rows:
            raise NotFound("Unknown private offer route")
        route = json.loads(rows[0][0])
        people = json.loads(rows[0][1])
        committed = store.query(store.event(),
                                "MATCH (r:Request {id: $id}) "
                                "WHERE r.state = 'awaiting_approval' "
                                "AND r.revealed_offer_id IS NULL "
                                "SET r.revealed_offer_id = $offer, r.revealed_route = $route, "
                                "r.state = 'approved' RETURN r.id",
                                {"id": request_id, "offer": offer_id,
                                 "route": rows[0][0]}).result_set
        if not committed:
            raise StateError("This request cannot reveal another route")
        # Only this approved snapshot is copied into the shared graph.
        _copy_people(store, people)
        _log_locked(store, request_id, "broker", "route_revealed")
        return route
