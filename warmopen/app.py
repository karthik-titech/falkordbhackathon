"""Single-process HTTP API, static pages, and offline response replay."""

import copy
import hashlib
import json
import math
import mimetypes
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

_STATIC = Path(__file__).with_name("static")
_REQUEST = re.compile(r"/api/requests/([^/]+)(?:/([^/]+))?\Z")
_CONFERENCE_PEOPLE = re.compile(r"/api/conferences/([A-Za-z0-9_.-]+)/people\Z")


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def _json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def _presentation(store, payload, routes=(), citations=()):
    """Return only route names and public citations, including after disclosure."""
    payload = copy.deepcopy(payload)
    ids = {person for route in routes for person in route["persons"]}
    evidence_ids = {edge.get("evidence_id") for route in routes for edge in route["edges"]}
    evidence_ids.update(item.get("evidence_id") for item in citations)
    names = store.query(store.event(),
                        "MATCH (p:Person) WHERE p.id IN $ids RETURN p.id, p.name",
                        {"ids": sorted(ids)}).result_set if ids else []
    evidence = store.query(store.event(),
                           "MATCH (e:Evidence) WHERE e.id IN $ids AND e.visibility = 'public' "
                           "RETURN e.id, e.url, e.claim",
                           {"ids": sorted(evidence_ids - {None})}).result_set if evidence_ids - {None} else []
    payload["people"] = dict(names)
    payload["evidence"] = {eid: {"url": url, "claim": claim} for eid, url, claim in evidence}

    def redact(value):
        if isinstance(value, dict):
            if "evidence_id" in value and value["evidence_id"] not in payload["evidence"]:
                value["evidence_id"] = None
            for item in value.values():
                redact(item)
        elif isinstance(value, list):
            for item in value:
                redact(item)

    redact(payload)
    return payload


def own_allowed(store, request, token, recording=None):
    """Use requester memory only with opt-in and this caller's credential."""
    from .consent import _authenticate

    if not request.get("use_own_memory", False) or not token:
        return False
    try:
        _authenticate(store, request["requester"], token)
    except PermissionError:
        return False
    if recording is not None:
        recording["auth_sha256"] = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return True


def _request_view(store, request_id, token=None, recording=None):
    from .agentlog import events
    from .broker import revealed_route
    from .paths import public_paths
    from .requests import get_request

    request = get_request(store, request_id)
    routes = public_paths(store, request["requester"], request["target"],
                          include_own=own_allowed(store, request, token, recording))
    revealed = revealed_route(store, request_id)
    # The stored snapshot also contains private evidence ids. Expose the filtered route below.
    public_request = {key: request[key] for key in
                      ("id", "requester", "target", "goal", "state", "created_at", "use_own_memory") if key in request}
    return _presentation(store, {"request": public_request, "routes": routes,
                                "revealed_route": revealed, "events": events(store, request_id)},
                         routes + ([revealed] if revealed else []))


def _live(store, method, path, body, token, jev, llm, recording=None):
    from . import broker, consent
    from .agentlog import _log_locked
    from .errors import NotFound
    from .openers import generate_openers
    from .requests import _advance_locked, create_request, get_request
    from .scoring import score_fit, suggested_move

    if body is not None and not isinstance(body, dict):
        raise ValueError("JSON body must be an object")
    body = body or {}

    def fields(*names):
        values = [body.get(name) for name in names]
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("Required string fields: " + ", ".join(names))
        return values

    if method == "GET" and urlsplit(path).path == "/api/meet":
        from .meet import who_to_meet

        query = parse_qs(urlsplit(path).query, keep_blank_values=True)
        if any(len(query.get(key, [])) != 1 or not query[key][0].strip()
               for key in ("requester", "goal")):
            raise ValueError("Required query fields: requester, goal")
        requester, goal = query["requester"][0], query["goal"][0]
        with store.lock:
            if token is not None:
                consent._authenticate(store, requester, token)
            return {"items": who_to_meet(store, requester, goal, include_own=token is not None)}
    if method == "GET" and path == "/api/targets":
        rows = store.query(store.event(),
                           "MATCH (p:Person) WHERE p.kind = 'speaker' RETURN p.id, p.name").result_set
        targets = {pid: {"id": pid, "name": name, "talks": []} for pid, name in rows}
        talks = store.query(store.event(),
                            "MATCH (p:Person)-[:SPEAKS_AT]->(t:Talk) "
                            "RETURN p.id, p.name, t.title, t.conference, t.starts ORDER BY t.starts, t.title").result_set
        for pid, name, title, conference, starts in talks:
            target = targets.setdefault(pid, {"id": pid, "name": name, "talks": []})
            target["talks"].append({"title": title, "conference": conference, "starts": starts})
        return {"items": sorted(targets.values(), key=lambda item: (item["name"] or "", item["id"]))}
    if method == "GET" and path == "/api/try/people":
        from .tryflow import public_example, public_people

        items = public_people(store)
        return {"items": items, "example": public_example(store, items)}
    if method == "GET" and path == "/api/conferences":
        from .directory import list_conferences

        items = list_conferences(store)
        citations = [{"evidence_id": eid} for item in items for eid in item.get("evidence_ids", [])]
        return _presentation(store, {"items": items}, citations=citations)
    if method == "GET" and _CONFERENCE_PEOPLE.fullmatch(path):
        from .directory import conference_people

        conference_id = _CONFERENCE_PEOPLE.fullmatch(path)[1]
        result = conference_people(store, conference_id)
        citations = [{"evidence_id": eid}
                     for collection in ("confirmed_attendees", "scheduled_speakers")
                     for person in result[collection] for eid in person.get("evidence_ids", [])]
        return _presentation(store, result, citations=citations)
    if method == "POST" and path == "/api/try":
        from .tryflow import explore_public

        if set(body) != {"source", "target", "action"}:
            raise ValueError("Expected source, target, and action fields")
        source, target, action = fields("source", "target", "action")
        result = explore_public(store, source, target, action)
        citations = list(result.get("openers", []))
        citations.extend({"evidence_id": edge["other_evidence_id"]}
                         for route in result["routes"] for edge in route["edges"]
                         if edge.get("other_evidence_id"))
        return _presentation(store, result, result["routes"], citations)
    if method == "GET" and path == "/api/people":
        rows = store.query(store.event(),
                           "MATCH (p:Person) WHERE p.consented = true AND p.kind = 'attendee' "
                           "RETURN p.id, p.name ORDER BY p.name, p.id").result_set
        return {"items": [{"id": pid, "name": name} for pid, name in rows]}
    if method == "POST" and path == "/api/requests":
        rid = create_request(store, *fields("requester", "target", "goal"), requester_token=token)
        view = _request_view(store, rid, token, recording)
        return {"request_id": rid, "state": view["request"]["state"],
                "use_own_memory": view["request"].get("use_own_memory", False),
                **{key: view[key] for key in ("routes", "people", "evidence")}}
    if method == "POST" and path == "/api/meetings":
        from .memory import log_meeting

        requester, person = fields("requester", "person")
        return log_meeting(store, requester, token, person)
    if method == "POST" and path == "/api/grants":
        if not token:
            raise PermissionError("Invalid owner token")
        owner, requester, rid, scope = fields("owner", "requester", "request_id", "scope")
        return {"grant_id": consent.grant(store, owner, token, requester, rid, scope)}
    owner_match = re.fullmatch(r"/api/owner/([^/]+)/pending", path)
    if method == "GET" and owner_match:
        owner = owner_match[1]
        if not token:
            raise PermissionError("Invalid owner token")
        with store.lock:
            consent._authenticate(store, owner, token)
            rows = store.query(store.event(),
                               "MATCH (a:Ask {owner: $owner}), (r:Request), "
                               "(requester:Person), (target:Person) "
                               "WHERE a.request_id = r.id AND requester.id = r.requester "
                               "AND target.id = r.target "
                               "RETURN properties(r), requester.name, target.name ORDER BY r.created_at",
                               {"owner": owner}).result_set
            items = []
            for request, requester_name, target_name in rows:
                rid, requester = request["id"], request["requester"]
                items.append({"request_id": rid, "requester": requester,
                              "requester_name": requester_name, "target_name": target_name,
                              "target": request["target"], "goal": request["goal"], "asked": True,
                              "reachability_granted": consent.has_grant(store, owner, requester, rid, "reachability"),
                              "reveal_granted": consent.has_grant(store, owner, requester, rid, "reveal")})
        return {"items": items}
    match = _REQUEST.fullmatch(path)
    if match:
        rid, action = match.groups()
        if method == "GET" and action is None:
            return _request_view(store, rid, token, recording)
        if method == "POST":
            if action == "reachability":
                return broker.reachability(store, fields("owner")[0], rid)
            if action == "reveal":
                owner, offer = fields("owner", "offer_id")
                route = broker.reveal(store, owner, rid, offer)
                return _presentation(store, route, [route])
            if action == "score":
                include_own = own_allowed(store, get_request(store, rid), token, recording)
                result = score_fit(store, rid, jev, include_own=include_own)
                result["move"] = suggested_move(store, rid, include_own=include_own)
                view = _request_view(store, rid, token, recording)
                routes = view["routes"] + ([view["revealed_route"]] if view["revealed_route"] else [])
                return _presentation(store, result, routes, result["supports"])
            if action == "openers":
                include_own = own_allowed(store, get_request(store, rid), token, recording)
                items = generate_openers(store, rid, llm, include_own=include_own)
                return _presentation(store, {"items": items}, citations=items)
            if action == "plan":
                from .target_plan import conference_options, future_conferences, plan_conference

                request = get_request(store, rid)
                include_own = own_allowed(store, request, token, recording)
                nearby = body.get("nearby", False)
                could_not_connect = body.get("could_not_connect", False)
                if type(nearby) is not bool or type(could_not_connect) is not bool:
                    raise ValueError("Journey flags must be booleans")
                options = conference_options(store, request["target"], timing_filter="current")
                conference_id = body.get("conference_id")
                if conference_id is not None and (not isinstance(conference_id, str) or not conference_id.strip()):
                    raise ValueError("Invalid conference id")
                if conference_id and not any(item["id"] == conference_id for item in options):
                    raise ValueError("Conference is not a current target appearance")
                plan = (plan_conference(store, request, conference_id, jev=jev, include_own=include_own)
                        if conference_id and not nearby and not could_not_connect else None)
                future = (future_conferences(store, request, include_own=include_own)
                          if could_not_connect and not nearby else [])
                openers = (generate_openers(store, rid, llm, include_own=include_own) if nearby else [])
                routes = (plan["routes"] if plan else []) + [route for item in future for route in item["routes"]]
                citations = list(options)
                if plan and plan.get("conference"):
                    citations.append(plan["conference"])
                for item in future:
                    if item.get("conference"):
                        citations.append(item["conference"])
                for route in routes:
                    citations.extend(route.get("intermediaries", []))
                    citations.extend({"evidence_id": edge["other_evidence_id"]}
                                     for edge in route["edges"] if edge.get("other_evidence_id"))
                citations.extend(openers)
                return _presentation(store, {"conferences": options, "plan": plan,
                                             "future": future, "nearby": nearby,
                                             "could_not_connect": could_not_connect,
                                             "openers": openers}, routes, citations)
            if action == "send":
                with store.lock:
                    request = get_request(store, rid)
                    request = _advance_locked(store, rid, request["state"], "requested")
                    _log_locked(store, rid, "seeker", "intro_requested")
                    return {"state": request["state"]}
    raise NotFound("Unknown route")


class _Replay:
    def __init__(self, directory):
        paths = sorted((p for p in Path(directory).glob("*.json") if p.stem.isdigit()),
                       key=lambda p: int(p.stem))
        self.remaining = [json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant,
                                     parse_float=_json_float)
                          for path in paths]
        self.last = {}

    def response(self, method, path, body, token=None):
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else None

        def authorized(record):
            return "auth_sha256" not in record or (digest is not None and record["auth_sha256"] == digest)

        for index, record in enumerate(self.remaining):
            if ((record["method"], record["path"], record["request_body"]) == (method, path, body)
                    and authorized(record)):
                self.remaining.pop(index)
                if method == "GET" and re.fullmatch(r"/api/requests/[^/?]+", path):
                    self.last[path] = record
                return record["status"], dict(record["body"], mode="recorded")
        if (method == "GET" and path in self.last and body == self.last[path]["request_body"]
                and authorized(self.last[path])):
            record = self.last[path]
            return record["status"], dict(record["body"], mode="recorded")
        return 404, {"error": "not in recording", "mode": "recorded"}


def make_server(store, host="127.0.0.1", port=0, mode="live", jev=None, llm=None,
                record_dir=None, recordings_dir=None, public_landing=False) -> ThreadingHTTPServer:
    """Build a server without starting its loop; replay never consults the store."""
    if mode not in ("live", "recorded"):
        raise ValueError("Unknown server mode")
    if mode == "live" and store is None:
        raise ValueError("Live mode needs a GraphStore")
    if mode == "recorded" and not recordings_dir:
        raise ValueError("Recorded mode needs recordings_dir")
    replay = _Replay(recordings_dir) if mode == "recorded" else None
    directory = Path(record_dir) if record_dir and mode == "live" else None
    counter = 0
    if directory:
        directory.mkdir(parents=True, exist_ok=True)
        counter = max((int(p.stem) for p in directory.glob("*.json") if p.stem.isdigit()), default=0)
    lock = threading.Lock()
    response_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send(self, status, data, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _api(self, path):
            nonlocal counter
            body = None
            recording = {} if directory else None
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 1_048_576:
                    raise ValueError("Invalid body length")
                if length:
                    body = json.loads(self.rfile.read(length).decode("utf-8"),
                                      parse_constant=_reject_constant, parse_float=_json_float)
                if replay:
                    with lock:
                        status, result = replay.response(self.command, self.path, body,
                                                         self.headers.get("X-Owner-Token"))
                else:
                    from .consent import _auth_recording

                    # Capture every successful authentication, even if later work fails.
                    context = _auth_recording.set(recording)
                    try:
                        result = _live(store, self.command, self.path if path == "/api/meet" else path, body,
                                       self.headers.get("X-Owner-Token"), jev, llm, recording)
                    finally:
                        _auth_recording.reset(context)
                    status = 200
            except Exception as exc:
                status = 400 if isinstance(exc, (ValueError, UnicodeError)) else 500
                if not replay:
                    # StateError and NotFound both inherit ValueError.
                    from .errors import NotFound
                    from .requests import StateError

                    if isinstance(exc, StateError):
                        status = 409
                    elif isinstance(exc, PermissionError):
                        status = 403
                    elif isinstance(exc, NotFound):
                        status = 404
                result = {"error": str(exc) if status != 500 else "Internal server error"}
                token = self.headers.get("X-Owner-Token")
                if token and path in ("/api/meet", "/api/meetings", "/api/requests"):
                    result["error"] = result["error"].replace(token, "[redacted]")
            result["mode"] = mode
            data = json.dumps(result, allow_nan=False).encode("utf-8")
            if directory:
                record = {"method": self.command, "path": self.path,
                          "request_body": body, "status": status, "body": result, **recording}
                # Serialize delivery so recording counters match response order.
                with response_lock:
                    with lock:
                        counter += 1
                        (directory / f"{counter:04d}.json").write_text(
                            json.dumps(record, allow_nan=False), encoding="utf-8")
                    self._send(status, data, "application/json; charset=utf-8")
            else:
                self._send(status, data, "application/json; charset=utf-8")

        def _handle(self):
            path = unquote(urlsplit(self.path).path)
            if path.startswith("/api/"):
                return self._api(path)
            name = {"/": "conferences.html" if public_landing else "index.html",
                    "/workspace": "index.html", "/owner": "owner.html", "/try": "conferences.html",
                    "/explore": "try.html", "/start": "start.html"}.get(path)
            if path.startswith("/static/"):
                name = path[len("/static/"):]
            if self.command == "GET" and name and ".." not in Path(name).parts:
                asset = (_STATIC / name).resolve()
                if asset.is_relative_to(_STATIC.resolve()) and asset.is_file():
                    content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                    return self._send(200, asset.read_bytes(), content_type + "; charset=utf-8")
            self._send(404, b"Not found", "text/plain; charset=utf-8")

        do_GET = _handle
        do_POST = _handle
        do_PUT = _handle
        do_DELETE = _handle
        do_PATCH = _handle

    return ThreadingHTTPServer((host, port), Handler)
