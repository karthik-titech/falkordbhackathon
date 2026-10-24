"""Read-only public conference directory backed by cited graph facts."""

from collections import defaultdict
import ipaddress
from urllib.parse import parse_qsl, urlsplit


def _valid_public_evidence(item):
    if not isinstance(item, dict) or item.get("visibility") != "public":
        return False
    url, claim = item.get("url"), item.get("claim")
    if (not isinstance(url, str) or not url.strip() or not isinstance(claim, str)
            or not claim.strip() or any(ord(char) < 32 or char.isspace() for char in url)):
        return False
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        _ = parsed.port
        if (parsed.scheme not in ("https", "http") or not parsed.netloc or not host
                or parsed.username or parsed.password or host.lower() == "localhost"
                or host.lower().endswith((".local", ".internal"))):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            if host.replace(".", "").isdigit():
                return False
        if any(key.lower() in {"token", "access_token", "api_key", "apikey", "password", "secret", "auth"}
               for key, _value in parse_qsl(parsed.query, keep_blank_values=True)):
            return False
    except ValueError:
        return False
    return True


_CATALOG = {
    "github_universe_2026": {
        "id": "github_universe_2026",
        "name": "GitHub Universe 2026",
        "starts": "2026-10-28",
        "ends": "2026-10-29",
        "official_url": "https://githubuniverse.com",
        "official_claim": "GitHub Universe 2026 is scheduled for October 28–29, 2026.",
        "catalog_only": True,
    }
}
_KNOWN_NAMES = {
    "github_universe_2026": "GitHub Universe 2026",
    "aie_worldsfair_2026": "AI Engineer World's Fair 2026",
}


def _evidence(store, evidence_ids):
    ids = sorted({item for item in evidence_ids if isinstance(item, str) and item})
    if not ids:
        return {}
    rows = store.query(store.event(),
                       "MATCH (e:Evidence) WHERE e.id IN $ids RETURN properties(e)",
                       {"ids": ids}).result_set
    return {row[0]["id"]: row[0] for row in rows
            if row and isinstance(row[0], dict) and _valid_public_evidence(row[0])}


def _name(conference_id):
    if conference_id in _KNOWN_NAMES:
        return _KNOWN_NAMES[conference_id]
    return conference_id.replace("_", " ").strip().title()


def conference_people(store, conference_id):
    """Return distinct confirmed attendees and scheduled speakers separately."""
    attendee_rows = store.query(
        store.event(),
        "MATCH (p:Person)-[r:ATTENDS]->(:Conference {id: $conference}) "
        "RETURN p.id, p.name, r.confirmed, r.evidence_id ORDER BY p.name, p.id",
        {"conference": conference_id}).result_set
    attendance_evidence = _evidence(store, [row[3] for row in attendee_rows if row[2] is True])
    attendees = {}
    for pid, name, confirmed, eid in attendee_rows:
        if confirmed is True and eid in attendance_evidence:
            attendees.setdefault(pid, {"id": pid, "name": name, "evidence_ids": [eid]})

    speaker_rows = store.query(
        store.event(),
        "MATCH (p:Person)-[r:SPEAKS_AT]->(t:Talk) "
        "WHERE t.conference = $conference "
        "RETURN p.id, p.name, t.id, t.title, t.starts, r.evidence_id ORDER BY p.name, t.starts, t.title",
        {"conference": conference_id}).result_set
    source_ids = [row[5] for row in speaker_rows if row[5]]
    valid_speaking_sources = _evidence(store, source_ids)
    speakers = {}
    for pid, name, talk_id, title, starts, relation_eid in speaker_rows:
        if relation_eid not in valid_speaking_sources:
            continue
        sources = [relation_eid]
        speaker = speakers.setdefault(pid, {"id": pid, "name": name, "talks": [], "evidence_ids": []})
        talk = {"id": talk_id, "title": title}
        if starts:
            talk["starts"] = starts
        if talk not in speaker["talks"]:
            speaker["talks"].append(talk)
        speaker["evidence_ids"] = sorted(set(speaker["evidence_ids"]) | set(sources))

    overlap_ids = sorted(set(attendees) & set(speakers))
    for item in attendees.values():
        item["overlap"] = item["id"] in overlap_ids
    for item in speakers.values():
        item["overlap"] = item["id"] in overlap_ids
        item["talks"].sort(key=lambda talk: (talk.get("starts", ""), talk.get("title", ""), talk["id"]))
    return {
        "conference_id": conference_id,
        "confirmed_attendees": sorted(attendees.values(), key=lambda item: (item["name"] or "", item["id"])),
        "scheduled_speakers": sorted(speakers.values(), key=lambda item: (item["name"] or "", item["id"])),
        "overlap_person_ids": overlap_ids,
    }


def list_conferences(store):
    """List graph conferences and legacy Talk.conference values with sourced dates."""
    rows = store.query(store.event(), "MATCH (c:Conference) RETURN properties(c)").result_set
    conferences = {}
    props_by_id = {}
    for row in rows:
        props = row[0]
        if not isinstance(props, dict) or not isinstance(props.get("id"), str):
            continue
        props_by_id[props["id"]] = props
        conferences[props["id"]] = {
            "id": props["id"], "name": props.get("name") or _name(props["id"]),
            "starts": None, "ends": None, "official_url": None,
            "catalog_only": False, "evidence_ids": [],
        }

    talk_rows = store.query(
        store.event(), "MATCH (t:Talk) WHERE t.conference IS NOT NULL "
        "RETURN DISTINCT t.conference").result_set
    for (conference_id,) in talk_rows:
        if isinstance(conference_id, str) and conference_id.strip():
            conferences.setdefault(conference_id, {
                "id": conference_id, "name": _name(conference_id),
                "starts": None, "ends": None, "official_url": None,
                "catalog_only": False, "evidence_ids": [],
            })

    support_rows = store.query(
        store.event(),
        "MATCH (c:Conference)-[:SUPPORTED_BY]->(e:Evidence) RETURN c.id, e.id").result_set
    supported = defaultdict(list)
    for conference_id, evidence_id in support_rows:
        supported[conference_id].append(evidence_id)
    evidence = _evidence(store, [eid for ids in supported.values() for eid in ids])
    for conference_id, item in conferences.items():
        valid_ids = sorted(eid for eid in supported[conference_id] if eid in evidence)
        item["evidence_ids"] = valid_ids
        if valid_ids:
            item["starts"] = props_by_id.get(conference_id, {}).get("starts")
            item["ends"] = props_by_id.get(conference_id, {}).get("ends")

    for conference_id, catalog_item in _CATALOG.items():
        current = conferences.get(conference_id)
        if current is None:
            conferences[conference_id] = dict(catalog_item, evidence_ids=[])
        else:
            current.update({key: catalog_item[key] for key in
                            ("name", "starts", "ends", "official_url", "official_claim")})

    items = []
    for conference_id in sorted(conferences):
        item = conferences[conference_id]
        people = conference_people(store, conference_id)
        item["confirmed_attendees_count"] = len(people["confirmed_attendees"])
        item["scheduled_speakers_count"] = len(people["scheduled_speakers"])
        items.append(item)
    return items
