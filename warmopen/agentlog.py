"""Ordered agent events linked to their introduction request."""

import time

from .requests import get_request

AGENTS = ("seeker", "broker", "scorer", "writer")


def _log_locked(store, request_id, agent, action):
    if agent not in AGENTS:
        raise ValueError("Unknown agent")
    get_request(store, request_id)
    store.query(store.event(),
                "MATCH (r:Request {id: $id}) "
                "OPTIONAL MATCH (r)-[:HAS_EVENT]->(previous:AgentEvent) "
                "WITH r, coalesce(max(previous.seq), 0) + 1 AS seq "
                "CREATE (r)-[:HAS_EVENT]->(:AgentEvent {seq: seq, agent: $agent, "
                "action: $action, request_id: $id, at: $at})",
                {"id": request_id, "agent": agent, "action": action, "at": time.time()})


def log(store, request_id, agent, action):
    with store.lock:
        _log_locked(store, request_id, agent, action)


def events(store, request_id):
    get_request(store, request_id)
    rows = store.query(store.event(),
                       "MATCH (:Request {id: $id})-[:HAS_EVENT]->(e:AgentEvent) "
                       "RETURN e.seq, e.agent, e.action ORDER BY e.seq",
                       {"id": request_id}).result_set
    return [{"seq": seq, "agent": agent, "action": action} for seq, agent, action in rows]
