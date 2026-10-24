"""Private, token-authenticated graph storage for consented own profiles."""

from datetime import datetime, timezone
import hashlib
import secrets
import re


_SESSION_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_SESSION_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
_MAX_INTERESTS = 256
_MAX_SOURCES = 2


def _safe_session_graph(store, session_id):
    if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
        raise PermissionError("Invalid profile session")
    try:
        return store.private(session_id)
    except (TypeError, ValueError):
        raise PermissionError("Invalid profile session") from None


def _interests(topic_sources):
    if not isinstance(topic_sources, (list, tuple)) or len(topic_sources) > _MAX_INTERESTS:
        raise ValueError("Invalid profile interests")
    parsed = []
    for topic in topic_sources:
        if (not isinstance(topic, dict) or not isinstance(topic.get("id"), str)
                or not topic["id"] or not isinstance(topic.get("name"), str)
                or not topic["name"].strip()):
            raise ValueError("Invalid profile interest")
        sources = topic.get("sources", [])
        if not isinstance(sources, (list, tuple)) or len(sources) > _MAX_SOURCES:
            raise ValueError("Invalid profile evidence sources")
        valid_sources = []
        seen = set()
        for source in sources:
            if (not isinstance(source, dict) or source.get("platform") not in {"linkedin", "x"}
                    or not isinstance(source.get("url"), str) or not source["url"]):
                raise ValueError("Invalid profile evidence source")
            if source["url"] not in seen:
                seen.add(source["url"])
                valid_sources.append({"url": source["url"], "platform": source["platform"]})
        parsed.append({"id": topic["id"], "name": topic["name"].strip(), "sources": valid_sources})
    return parsed


def create_profile_session(store, topic_sources):
    """Create a private `You` graph; only token hashes and sourced topic facts persist."""
    topics = _interests(topic_sources)
    session_id = secrets.token_urlsafe(18)
    token = secrets.token_urlsafe(32)
    token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    graph = _safe_session_graph(store, session_id)
    observed_at = datetime.now(timezone.utc).date().isoformat()
    evidence_by_url = {}

    with store.lock:
        store.query(
            graph,
            "MERGE (p:Person {id: $id}) SET p.name = $name, p.owner = true",
            {"id": "you", "name": "You"},
        )
        store.query(
            graph,
            "MERGE (c:ProfileSessionCredential {id: $id}) SET c.token_sha256 = $digest",
            {"id": session_id, "digest": token_digest},
        )
        for topic in topics:
            store.query(
                graph,
                "MERGE (t:Topic {id: $id}) SET t.name = $name",
                {"id": topic["id"], "name": topic["name"]},
            )
            for source in topic["sources"]:
                url = source["url"]
                evidence_id = evidence_by_url.get(url)
                if evidence_id is None:
                    evidence_id = "profile_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
                    evidence_by_url[url] = evidence_id
                    store.query(
                        graph,
                        "MERGE (e:Evidence {id: $id}) SET e.url = $url, e.claim = $claim, "
                        "e.visibility = 'private', e.platform = $platform, e.observed_at = $observed_at",
                        {"id": evidence_id, "url": url,
                         "claim": "Own profile professional text includes a conference topic label.",
                         "platform": source["platform"], "observed_at": observed_at},
                    )
                store.query(
                    graph,
                    "MATCH (p:Person {id: $person}), (t:Topic {id: $topic}), "
                    "(e:Evidence {id: $evidence}) "
                    "MERGE (p)-[:INTERESTED_IN {evidence_id: $evidence}]->(t) "
                    "MERGE (p)-[:SUPPORTED_BY]->(e)",
                    {"person": "you", "topic": topic["id"], "evidence": evidence_id},
                )

    interests = []
    for topic in topics:
        evidence_ids = sorted({evidence_by_url[source["url"]]
                               for source in topic["sources"] if source["url"] in evidence_by_url})
        interests.append({"id": topic["id"], "name": topic["name"],
                          "evidence_ids": evidence_ids, "sources": topic["sources"]})
    return {
        "id": session_id,
        "token": token,
        "node_id": "you",
        "name": "You",
        "interests": interests,
    }


def read_profile_session(store, session_id, token):
    """Authenticate before reading private own-topic context; raise for bad tokens."""
    graph = _safe_session_graph(store, session_id)
    if not isinstance(token, str) or not _SESSION_TOKEN.fullmatch(token):
        raise PermissionError("Invalid profile session token")
    rows = store.query(
        graph,
        "MATCH (c:ProfileSessionCredential {id: $id}) RETURN c.token_sha256",
        {"id": session_id},
    ).result_set
    if (not rows or not isinstance(rows[0][0], str)
            or not secrets.compare_digest(
                rows[0][0], hashlib.sha256(token.encode("utf-8")).hexdigest())):
        raise PermissionError("Invalid profile session token")

    people = store.query(
        graph,
        "MATCH (p:Person {id: $id}) RETURN p.name",
        {"id": "you"},
    ).result_set
    if not people or people[0][0] != "You":
        raise PermissionError("Invalid profile session")
    rows = store.query(
        graph,
        "MATCH (:Person {id: $person})-[r:INTERESTED_IN]->(t:Topic) "
        "OPTIONAL MATCH (e:Evidence {id: r.evidence_id}) "
        "RETURN t.id, t.name, r.evidence_id, e.url, e.platform "
        "ORDER BY t.name, t.id, r.evidence_id",
        {"person": "you"},
    ).result_set
    interests = {}
    for topic_id, name, evidence_id, url, platform in rows:
        topic = interests.setdefault(topic_id, {"id": topic_id, "name": name,
                                                "evidence_ids": [], "sources": []})
        if evidence_id and evidence_id not in topic["evidence_ids"]:
            topic["evidence_ids"].append(evidence_id)
        source = {"url": url, "platform": platform}
        if url and source not in topic["sources"]:
            topic["sources"].append(source)
    return {
        "id": session_id,
        "node_id": "you",
        "name": "You",
        "interests": sorted(interests.values(), key=lambda item: (item["name"].casefold(), item["id"])),
    }
