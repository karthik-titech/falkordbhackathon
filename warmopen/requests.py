"""Introduction requests and compare-and-set state transitions."""

import secrets
import time

from .errors import NotFound

GOALS = ("invest", "sales")
_TRANSITIONS = {("draft", "awaiting_approval"), ("awaiting_approval", "approved"),
                ("awaiting_approval", "declined"), ("approved", "requested"),
                ("draft", "requested")}


class StateError(ValueError):
    """A transition is invalid or its expected state is stale."""


def _person(store, person_id):
    rows = store.query(store.event(),
                       "MATCH (p:Person {id: $id}) RETURN properties(p)",
                       {"id": person_id}).result_set
    if not rows:
        raise NotFound("Unknown person")
    return rows[0][0]


def create_request(store, requester, target, goal, requester_token=None):
    if goal not in GOALS:
        raise ValueError("Unknown goal")
    with store.lock:
        use_own_memory = requester_token is not None
        if use_own_memory:
            from .consent import _authenticate

            _authenticate(store, requester, requester_token)
        _person(store, requester)
        _person(store, target)
        request_id = secrets.token_urlsafe(16)
        store.query(store.event(),
                    "CREATE (:Request {id: $id, requester: $requester, target: $target, "
                    "goal: $goal, state: 'draft', created_at: $at, use_own_memory: $use_own_memory})",
                    {"id": request_id, "requester": requester, "target": target,
                     "goal": goal, "at": time.time(), "use_own_memory": use_own_memory})
        from .agentlog import _log_locked

        _log_locked(store, request_id, "seeker", "request_created")
        return request_id


def get_request(store, request_id):
    rows = store.query(store.event(),
                       "MATCH (r:Request {id: $id}) RETURN properties(r)",
                       {"id": request_id}).result_set
    if not rows:
        raise NotFound("Unknown request")
    return rows[0][0]


def _advance_locked(store, request_id, expected_state, new_state):
    request = get_request(store, request_id)
    if request["state"] != expected_state or (expected_state, new_state) not in _TRANSITIONS:
        raise StateError("Invalid or stale request transition")
    store.query(store.event(), "MATCH (r:Request {id: $id}) SET r.state = $state",
                {"id": request_id, "state": new_state})
    return get_request(store, request_id)


def advance(store, request_id, expected_state, new_state):
    with store.lock:
        return _advance_locked(store, request_id, expected_state, new_state)
