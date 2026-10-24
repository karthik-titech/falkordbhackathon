"""Preflighted, source-scoped imports of one conference attendance snapshot."""

import hashlib
import ipaddress
import json
import re
from datetime import date
from urllib.parse import parse_qsl, urlsplit


_IMPORT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_GRAPH_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_EMAIL = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Z]{2,}")
_SECRET = re.compile(
    r"(?i)(?:sk-[A-Za-z0-9_-]{16,}|bearer\s+[A-Za-z0-9._~-]{8,}|"
    r"(?:api[_-]?key|owner[_-]?token|access[_-]?token)\s*[:=]|"
    r"-----BEGIN (?:RSA )?PRIVATE KEY-----)"
)
_PRIVATE_WORD = re.compile(r"(?i)\b(?:owner_token|owner_strength|knows|private_graph|api_key|secret)\b")
_SOCIAL_HOSTS = ("linkedin.com", "facebook.com", "x.com", "twitter.com", "instagram.com",
                 "tiktok.com", "threads.net", "snapchat.com")


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest field")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("Invalid manifest number")


def read_manifest(path):
    """Read JSON without accepting duplicate keys or non-finite numbers."""
    try:
        raw = path.read_text(encoding="utf-8")
        manifest = json.loads(raw, object_pairs_hook=_pairs_no_duplicates,
                              parse_constant=_reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot read attendance manifest") from exc
    return validate_manifest(manifest)


def _keys(value, required, allowed):
    if not isinstance(value, dict) or not set(required) <= set(value) or not set(value) <= set(allowed):
        raise ValueError("Invalid manifest shape")


def _safe_text(value, maximum, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("Invalid manifest text")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError("Invalid manifest text")
    if _EMAIL.search(value) or _SECRET.search(value) or _PRIVATE_WORD.search(value):
        raise ValueError("Manifest contains disallowed private or secret material")
    return value.strip()


def _date_text(value, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError("Dates must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Dates must use YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise ValueError("Dates must use YYYY-MM-DD")
    return value


def _source_url(value):
    url = _safe_text(value, 2048)
    if any(char.isspace() or ord(char) < 32 for char in url):
        raise ValueError("Invalid source URL")
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        _port = parsed.port
        query = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=100)
    except ValueError:
        raise ValueError("Invalid source URL") from None
    if (parsed.scheme.lower() not in ("http", "https") or not host
            or parsed.username is not None or parsed.password is not None or parsed.fragment):
        raise ValueError("Source URLs must be public HTTP(S) links")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Source URL must be public")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Source URL must be public")
    if any(host == domain or host.endswith("." + domain) for domain in _SOCIAL_HOSTS):
        raise ValueError("Personal social-profile sources are not accepted")
    if any(key.lower().replace("-", "_") in {"token", "access_token", "api_key", "key", "auth",
                                                   "password", "secret", "session"}
           for key, _value in query):
        raise ValueError("Source URL contains a credential parameter")
    return url


def validate_manifest(manifest):
    """Validate the allowlisted schema and return normalized input data."""
    _keys(manifest, ("schema_version", "import_id", "conference", "attendees"),
          ("schema_version", "import_id", "conference", "attendees"))
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("Unsupported attendance manifest version")
    import_id = manifest["import_id"]
    if not isinstance(import_id, str) or not _IMPORT_ID.fullmatch(import_id):
        raise ValueError("Invalid import id")
    conference = manifest["conference"]
    _keys(conference, ("id", "name", "starts"), ("id", "name", "starts", "ends"))
    conference_id = conference["id"]
    if not isinstance(conference_id, str) or not _GRAPH_ID.fullmatch(conference_id):
        raise ValueError("Invalid conference id")
    conference_name = _safe_text(conference["name"], 160)
    starts = _date_text(conference["starts"])
    ends = _date_text(conference.get("ends"), optional=True)
    if ends and ends < starts:
        raise ValueError("Conference end date precedes its start")
    attendees = manifest["attendees"]
    if not isinstance(attendees, list):
        raise ValueError("Attendees must be a list")
    normalized, seen = [], set()
    for item in attendees:
        _keys(item, ("person_id", "basis", "confirmed", "source"),
              ("person_id", "name", "basis", "confirmed", "source"))
        person_id = item["person_id"]
        if not isinstance(person_id, str) or not _GRAPH_ID.fullmatch(person_id) or person_id in seen:
            raise ValueError("Invalid or duplicate attendee id")
        seen.add(person_id)
        name = _safe_text(item.get("name"), 160, required=False)
        basis = item["basis"]
        if basis not in ("public_professional", "opted_in"):
            raise ValueError("Invalid attendance basis")
        if type(item["confirmed"]) is not bool:
            raise ValueError("Attendance confirmation must be boolean")
        source = item["source"]
        _keys(source, ("url", "claim", "observed_at"), ("url", "claim", "observed_at"))
        normalized.append({
            "person_id": person_id,
            "name": name,
            "basis": basis,
            "confirmed": item["confirmed"],
            "source": {"url": _source_url(source["url"]),
                       "claim": _safe_text(source["claim"], 1000),
                       "observed_at": _date_text(source["observed_at"])},
        })
    return {"schema_version": 1, "import_id": import_id,
            "conference": {"id": conference_id, "name": conference_name,
                           "starts": starts, "ends": ends},
            "attendees": normalized}


def _evidence_id(import_id, conference_id, person_id):
    key = "\0".join((import_id, conference_id, person_id)).encode("utf-8")
    return "import-attendance:" + hashlib.sha256(key).hexdigest()


def _existing(store, query, params=None):
    return store.query(store.event(), query, params or {}).result_set


def _preflight(store, manifest):
    conference = manifest["conference"]
    conference_id, import_id = conference["id"], manifest["import_id"]
    attendees = manifest["attendees"]
    people_ids = [item["person_id"] for item in attendees]
    person_rows = (_existing(store, "MATCH (p:Person) WHERE p.id IN $ids RETURN properties(p)",
                             {"ids": people_ids}) if people_ids else [])
    if len(person_rows) != len({row[0]["id"] for row in person_rows}):
        raise ValueError("Duplicate person ids exist in the graph")
    people = {row[0]["id"]: row[0] for row in person_rows}
    for item in attendees:
        person = people.get(item["person_id"])
        if person:
            if not isinstance(person.get("name"), str) or not person["name"].strip():
                raise ValueError("Existing attendee has no public name")
            if not isinstance(person.get("kind"), str) or not person["kind"].strip():
                raise ValueError("Existing attendee has no public kind")
            if item["name"] is not None and person.get("name") != item["name"]:
                raise ValueError("Attendee name conflicts with the existing graph")
        elif item["name"] is None:
            raise ValueError("New attendees require a name")

    conference_rows = _existing(
        store, "MATCH (c:Conference {id: $id}) RETURN properties(c)", {"id": conference_id})
    if len(conference_rows) > 1:
        raise ValueError("Duplicate conference ids exist in the graph")
    existing_conference = conference_rows[0][0] if conference_rows else None
    if existing_conference:
        if existing_conference.get("name") not in (None, conference["name"]):
            raise ValueError("Conference name conflicts with the existing graph")
        for field in ("starts", "ends"):
            incoming = conference[field]
            existing = existing_conference.get(field)
            if incoming is not None and existing not in (None, incoming):
                raise ValueError("Conference dates conflict with the existing graph")

    evidence_ids = {_evidence_id(import_id, conference_id, item["person_id"]): item
                    for item in attendees}
    attendance_rows = _existing(
        store,
        "MATCH (p:Person)-[r:ATTENDS]->(c:Conference {id: $conference}) "
        "RETURN p.id, r.import_id, r.evidence_id, r.confirmed, r.basis",
        {"conference": conference_id})
    evidence_refs = set(evidence_ids)
    evidence_refs.update(eid for person_id, _owner, eid, _confirmed, _basis in attendance_rows
                         if person_id in people_ids and eid)
    evidence_rows = (_existing(store,
                               "MATCH (e:Evidence) WHERE e.id IN $ids RETURN properties(e)",
                               {"ids": sorted(evidence_refs)}) if evidence_refs else [])
    if len(evidence_rows) != len({row[0]["id"] for row in evidence_rows}):
        raise ValueError("Duplicate evidence ids exist in the graph")
    evidence_by_id = {row[0]["id"]: row[0] for row in evidence_rows}
    owned = {}
    unowned_exact = set()
    records = {item["person_id"]: item for item in attendees}
    rows_by_person = {}
    for person_id, owner, eid, confirmed, basis in attendance_rows:
        if person_id in people_ids:
            rows_by_person.setdefault(person_id, []).append((owner, eid, confirmed, basis))
        if owner == import_id:
            if person_id in owned:
                raise ValueError("Duplicate attendance ownership in graph")
            expected_eid = _evidence_id(import_id, conference_id, person_id)
            if eid not in (None, expected_eid):
                raise ValueError("Attendance evidence belongs to another source")
            owned[person_id] = {"evidence_id": eid, "confirmed": confirmed}
    for person_id, rows in rows_by_person.items():
        foreign = [row for row in rows if row[0] != import_id]
        if not foreign:
            continue
        if len(rows) != 1 or foreign[0][0] is not None:
            raise ValueError("Attendance is owned by another source")
        _owner, eid, confirmed, basis = foreign[0]
        item = records[person_id]
        source = item["source"]
        cited = evidence_by_id.get(eid)
        exact = (item["confirmed"] and confirmed is True and cited is not None
                 and cited.get("visibility") == "public"
                 and cited.get("url") == source["url"]
                 and cited.get("claim") == source["claim"]
                 and cited.get("observed_at") == source["observed_at"]
                 and basis in (None, item["basis"]))
        if not exact:
            raise ValueError("Attendance conflicts with an existing source")
        unowned_exact.add(person_id)

    for eid, item in evidence_ids.items():
        old = evidence_by_id.get(eid)
        if not old:
            continue
        if old.get("import_id") == import_id and old.get("conference_id") == conference_id:
            if old.get("visibility") != "public":
                raise ValueError("Attendance evidence is not public")
            continue
        person_id = item["person_id"]
        if (person_id in unowned_exact and old.get("import_id") is None
                and old.get("visibility") == "public"
                and old.get("url") == item["source"]["url"]
                and old.get("claim") == item["source"]["claim"]
                and old.get("observed_at") == item["source"]["observed_at"]):
            continue
        raise ValueError("Evidence id belongs to another source")

    support_rows = _existing(
        store,
        "MATCH (p:Person)-[:SUPPORTED_BY]->(e:Evidence) "
        "WHERE e.import_id = $import_id AND e.conference_id = $conference RETURN p.id, e.id",
        {"import_id": import_id, "conference": conference_id})
    legacy_supports = [(person_id, eid) for person_id, eid in support_rows
                       if eid == _evidence_id(import_id, conference_id, person_id)]

    active = {item["person_id"] for item in attendees if item["confirmed"]}
    retract = set(owned) - active
    counts = {
        "new_conference": int(existing_conference is None),
        "new_people": sum(item["person_id"] not in people for item in attendees),
        "new_evidence": sum(eid not in evidence_by_id and item["person_id"] not in unowned_exact
                             for eid, item in evidence_ids.items()),
        "new_attendance": sum(pid not in owned and pid not in unowned_exact for pid in active),
        "updated_attendance": sum(pid in owned and not owned[pid]["confirmed"] for pid in active),
        "retracted_attendance": len(retract),
        "active_attendance": len(active),
    }
    return {"conference": conference, "existing_conference": existing_conference,
            "people": people, "evidence_ids": evidence_ids, "evidence_by_id": evidence_by_id,
            "owned": owned, "unowned_exact": unowned_exact, "active": active,
            "legacy_supports": legacy_supports,
            "counts": counts}


def import_attendees(store, manifest, check=False):
    """Preflight then upsert a complete snapshot for one import source and event."""
    data = validate_manifest(manifest)
    with store.lock:
        plan = _preflight(store, data)
        if check:
            return dict(plan["counts"])

        conference = plan["conference"]
        conference_id, import_id = conference["id"], data["import_id"]
        for person_id, eid in plan["legacy_supports"]:
            store.query(store.event(),
                        "MATCH (:Person {id: $person})-[s:SUPPORTED_BY]->"
                        "(:Evidence {id: $evidence, import_id: $import_id, conference_id: $conference}) "
                        "DELETE s", {"person": person_id, "evidence": eid,
                                     "import_id": import_id, "conference": conference_id})
        store.query(store.event(),
                    "MERGE (c:Conference {id: $id}) "
                    "SET c.name = coalesce(c.name, $name), c.starts = coalesce(c.starts, $starts), "
                    "c.ends = coalesce(c.ends, $ends)",
                    {"id": conference_id, "name": conference["name"],
                     "starts": conference["starts"], "ends": conference["ends"]})

        for item in data["attendees"]:
            person_id = item["person_id"]
            if person_id in plan["unowned_exact"]:
                continue
            if person_id not in plan["people"]:
                store.query(store.event(),
                            "CREATE (:Person {id: $id, name: $name, kind: 'attendee', consented: false})",
                            {"id": person_id, "name": item["name"]})
            eid = _evidence_id(import_id, conference_id, person_id)
            source = item["source"]
            store.query(store.event(),
                        "MERGE (e:Evidence {id: $id}) "
                        "SET e.url = $url, e.claim = $claim, e.observed_at = $observed_at, "
                        "e.visibility = 'public', e.import_id = $import_id, e.conference_id = $conference",
                        {"id": eid, "url": source["url"], "claim": source["claim"],
                         "observed_at": source["observed_at"], "import_id": import_id,
                         "conference": conference_id})
        store.query(store.event(),
                    "MATCH (p:Person)-[r:ATTENDS]->(c:Conference {id: $conference}) "
                    "WHERE r.import_id = $import_id AND NOT p.id IN $active DELETE r",
                    {"conference": conference_id, "import_id": import_id,
                     "active": sorted(plan["active"])})
        for item in data["attendees"]:
            if not item["confirmed"] or item["person_id"] in plan["unowned_exact"]:
                continue
            person_id = item["person_id"]
            eid = _evidence_id(import_id, conference_id, person_id)
            store.query(store.event(),
                        "MATCH (p:Person {id: $person}), (c:Conference {id: $conference}) "
                        "MERGE (p)-[r:ATTENDS {import_id: $import_id}]->(c) "
                        "SET r.confirmed = true, r.basis = $basis, r.evidence_id = $evidence",
                        {"person": person_id, "conference": conference_id,
                         "import_id": import_id, "basis": item["basis"], "evidence": eid})
        return dict(plan["counts"])
