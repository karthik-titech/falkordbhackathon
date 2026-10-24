"""Separate, expiring owner grants for reachability and reveal."""

import hashlib
import math
import secrets
import time
from contextvars import ContextVar

from .errors import NotFound
from .requests import _person, get_request

SCOPES = ("reachability", "reveal")
_auth_recording = ContextVar("auth_recording", default=None)


def _time(now):
    value = time.time() if now is None else float(now)
    if not math.isfinite(value):
        raise ValueError("Time must be finite")
    return value


def _check_owner(store, owner):
    if not _person(store, owner).get("consented", False):
        raise PermissionError("Owner has not consented")


def _authenticate(store, owner, token):
    _check_owner(store, owner)
    rows = store.query(store.private(owner),
                       "MATCH (c:OwnerCredential {id: $owner}) RETURN c.token_sha256",
                       {"owner": owner}).result_set
    if (not rows or not isinstance(rows[0][0], str) or not isinstance(token, str)
            or not secrets.compare_digest(rows[0][0], hashlib.sha256(token.encode("utf-8")).hexdigest())):
        raise PermissionError("Invalid owner token")
    recording = _auth_recording.get()
    if recording is not None:
        recording["auth_sha256"] = hashlib.sha256(token.encode("utf-8")).hexdigest()


def grant(store, owner, owner_token, requester, request_id, scope, ttl_s=900, now=None):
    if scope not in SCOPES:
        raise ValueError("Unknown grant scope")
    at = _time(now)
    expires_at = at + float(ttl_s)
    if not math.isfinite(expires_at):
        raise ValueError("Expiry must be finite")
    with store.lock:
        _authenticate(store, owner, owner_token)
        request = get_request(store, request_id)
        _person(store, requester)
        if requester != request["requester"]:
            raise ValueError("Requester does not match the request")
        grant_id = secrets.token_urlsafe(16)
        store.query(store.event(),
                    "MATCH (r:Request {id: $request_id}) "
                    "CREATE (r)-[:HAS_GRANT]->(:Grant {id: $id, owner: $owner, "
                    "requester: $requester, request_id: $request_id, scope: $scope, "
                    "expires_at: $expires_at, revoked: false})",
                    {"id": grant_id, "owner": owner, "requester": requester,
                     "request_id": request_id, "scope": scope, "expires_at": expires_at})
        return grant_id


def has_grant(store, owner, requester, request_id, scope, now=None):
    at = _time(now)
    get_request(store, request_id)
    _person(store, owner)
    _person(store, requester)
    if scope not in SCOPES:
        return False
    rows = store.query(store.event(),
                       "MATCH (g:Grant {owner: $owner, requester: $requester, "
                       "request_id: $request_id, scope: $scope}) "
                       "WHERE g.revoked = false AND g.expires_at > $at RETURN g.id LIMIT 1",
                       {"owner": owner, "requester": requester, "request_id": request_id,
                        "scope": scope, "at": at}).result_set
    return bool(rows)


def revoke(store, owner, owner_token, grant_id):
    with store.lock:
        _authenticate(store, owner, owner_token)
        rows = store.query(store.event(), "MATCH (g:Grant {id: $id}) RETURN g.owner",
                           {"id": grant_id}).result_set
        if not rows:
            raise NotFound("Unknown grant")
        if rows[0][0] != owner:
            raise PermissionError("Grant belongs to another owner")
        store.query(store.event(), "MATCH (g:Grant {id: $id}) SET g.revoked = true",
                    {"id": grant_id})
