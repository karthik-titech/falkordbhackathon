"""Evidence-gated context for public profile comparisons."""

from collections import defaultdict
import math
import ipaddress
import re
from urllib.parse import parse_qsl, urlsplit

from .directory import _evidence, _valid_public_evidence
from .tryflow import public_people, public_try_paths

_REASONS = {
    "missing_piece": "The target has cited work on a capability you are seeking.",
    "mirror": "Both profiles have cited public topics in common.",
    "unexpected_connection": "A cited public graph route connects these profiles.",
    "unknown": "No topic overlap or cited route is available yet.",
}
_MENTION_SIGNAL_KEYS = (
    "professional_mention_count", "positive_mention_count", "neutral_mention_count",
    "critical_mention_count", "unclear_mention_count", "recent_mention_count",
    "mention_source_count",
)
_TOPIC_STOPWORDS = {
    "and", "for", "from", "into", "with", "the", "using", "build", "building",
    "systems", "system", "applications", "application", "technology", "technologies",
}
_TOPIC_ALIASES = {"agents": "agent", "agentic": "agent", "infra": "infrastructure",
                  "cloudinfra": "infrastructure", "databases": "database"}
_RELATED_DOMAINS = {
    "agent": {"cloud", "infrastructure", "security", "deployment"},
    "cloud": {"agent", "security", "infrastructure", "deployment"},
    "infrastructure": {"agent", "cloud", "security", "deployment"},
    "security": {"agent", "cloud", "infrastructure"},
}


def _topic_tokens(topic_id, topic):
    text = f"{topic_id} {topic.get('name', '')}".casefold()
    raw = re.findall(r"[a-z0-9]+", text)
    tokens = {_TOPIC_ALIASES.get(token, token) for token in raw
              if token not in _TOPIC_STOPWORDS and len(token) > 2}
    return tokens


def related_topic_pairs(source_topics, target_topics):
    """Pair distinct public professional topics with a fixed lexical/domain map."""
    pairs = []
    for source_id, source_topic in sorted(source_topics.items()):
        source_tokens = _topic_tokens(source_id, source_topic)
        for target_id, target_topic in sorted(target_topics.items()):
            if source_id == target_id:
                continue
            target_tokens = _topic_tokens(target_id, target_topic)
            if (source_tokens & target_tokens
                    or any(token in _RELATED_DOMAINS.get(other, set())
                           for token in source_tokens for other in target_tokens)):
                pairs.append({
                    "source": {"id": source_id, "name": source_topic.get("name") or source_id},
                    "target": {"id": target_id, "name": target_topic.get("name") or target_id},
                    "relation": "related",
                })
    return pairs


def _topic_names(store, topic_ids):
    ids = sorted({topic_id for topic_id in topic_ids if isinstance(topic_id, str)})
    if not ids:
        return {}
    rows = store.query(store.event(),
                       "MATCH (t:Topic) WHERE t.id IN $ids RETURN t.id, t.name",
                       {"ids": ids}).result_set
    return {topic_id: name for topic_id, name in rows if isinstance(topic_id, str)}


def _empty_mentions(status="not_requested"):
    return {"status": status, "items": [], "signals": {
        "mentions_available": False,
        **{key: 0 for key in _MENTION_SIGNAL_KEYS},
    }}


def _safe_mention_url(value):
    if (not isinstance(value, str) or not value or len(value) > 2048
            or any(char.isspace() or ord(char) < 32 for char in value)):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
        if parsed.scheme not in ("https", "http") or not parsed.netloc or not host:
            return False
        normalized_host = host.lower().rstrip(".")
        if (port is not None or parsed.username or parsed.password or normalized_host == "localhost"
                or normalized_host.endswith((".localhost", ".local", ".internal"))):
            return False
        if normalized_host not in {"x.com", "twitter.com", "linkedin.com", "www.linkedin.com"}:
            return False
        if parsed.query or parsed.fragment:
            return False
        if normalized_host in {"x.com", "twitter.com"}:
            if not re.fullmatch(r"/[A-Za-z0-9_]{1,15}/status/[0-9]{1,30}", parsed.path):
                return False
        elif not re.fullmatch(r"/posts/[A-Za-z0-9_-]{1,300}", parsed.path):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            if host.replace(".", "").isdigit():
                return False
        sensitive = {"token", "access_token", "api_key", "apikey", "password", "secret", "auth"}
        if any(key.lower() in sensitive for key, _value in parse_qsl(parsed.query, keep_blank_values=True)):
            return False
    except ValueError:
        return False
    return True


def _sanitize_mentions(value):
    result = _empty_mentions("unavailable")
    if not isinstance(value, dict):
        return result
    status = value.get("status")
    if isinstance(status, str) and status in {"ok", "failed", "unavailable"}:
        result["status"] = status
    signals = value.get("signals")
    if isinstance(signals, dict):
        clean_signals = {"mentions_available": signals.get("mentions_available") is True}
        for key in _MENTION_SIGNAL_KEYS:
            count = signals.get(key)
            clean_signals[key] = count if type(count) is int and 0 <= count <= 1000000 else 0
        result["signals"] = clean_signals
    clean_items = []
    items = value.get("items")
    if isinstance(items, list):
        for item in items[:5]:
            if not isinstance(item, dict) or not _safe_mention_url(item.get("url")):
                continue
            tone = item.get("tone")
            platform = item.get("platform")
            clean_items.append({
                "url": item["url"][:2000],
                "title": str(item.get("title", ""))[:200],
                "excerpt": str(item.get("excerpt", ""))[:600],
                "published_at": str(item.get("published_at", ""))[:80],
                "tone": tone if tone in ("positive", "neutral", "critical", "unclear") else "unclear",
                "platform": platform if platform in ("x", "linkedin", "other") else "other",
            })
    result["items"] = clean_items
    return result


def conference_topics(store, conference_id):
    """List event talk topics only when schedule and topic links have citations."""
    rows = store.query(
        store.event(),
        "MATCH (:Person)-[s:SPEAKS_AT]->(talk:Talk)-[a:ABOUT]->(topic:Topic) "
        "WHERE talk.conference = $conference "
        "RETURN topic.id, topic.name, s.evidence_id, a.evidence_id",
        {"conference": conference_id}).result_set
    valid = _evidence(store, [eid for row in rows for eid in row[2:] if eid])
    topics = {}
    for topic_id, name, schedule_evidence, topic_evidence in rows:
        if schedule_evidence not in valid or topic_evidence not in valid:
            continue
        item = topics.setdefault(topic_id, {"id": topic_id, "name": name or topic_id,
                                            "evidence_ids": set()})
        item["evidence_ids"].update((schedule_evidence, topic_evidence))
    return [{**item, "evidence_ids": sorted(item["evidence_ids"])}
            for item in sorted(topics.values(), key=lambda item: (item["name"].casefold(), item["id"]))]


def validate_topic_ids(store, conference_id, value, field):
    if not isinstance(value, list) or len(value) > 40:
        raise ValueError(f"{field} must be a list of conference topic ids")
    if any(not isinstance(item, str) or not item.strip() for item in value) or len(set(value)) != len(value):
        raise ValueError(f"{field} contains invalid topic ids")
    allowed = {item["id"] for item in conference_topics(store, conference_id)}
    if not set(value) <= allowed:
        raise ValueError(f"{field} must use listed conference topic ids")
    return sorted(value)


def _person_topics(store, person_ids):
    people = sorted({person_id for person_id in person_ids if person_id})
    result = {person_id: {} for person_id in people}
    if not people:
        return result
    interests = store.query(
        store.event(),
        "MATCH (p:Person)-[r:INTERESTED_IN]->(topic:Topic) "
        "WHERE p.id IN $people RETURN p.id, topic.id, topic.name, r.evidence_id",
        {"people": people}).result_set
    talks = store.query(
        store.event(),
        "MATCH (p:Person)-[s:SPEAKS_AT]->(talk:Talk)-[a:ABOUT]->(topic:Topic) "
        "WHERE p.id IN $people "
        "RETURN p.id, topic.id, topic.name, s.evidence_id, a.evidence_id",
        {"people": people}).result_set
    evidence_ids = [row[3] for row in interests if row[3]]
    evidence_ids.extend(eid for row in talks for eid in row[3:] if eid)
    valid = _evidence(store, evidence_ids)
    for person_id, topic_id, name, evidence_id in interests:
        if evidence_id in valid:
            result[person_id].setdefault(topic_id, {"name": name or topic_id, "evidence_ids": set()})[
                "evidence_ids"].add(evidence_id)
    for person_id, topic_id, name, schedule_evidence, topic_evidence in talks:
        if schedule_evidence in valid and topic_evidence in valid:
            topic = result[person_id].setdefault(
                topic_id, {"name": name or topic_id, "evidence_ids": set()})
            topic["evidence_ids"].update((schedule_evidence, topic_evidence))
    return result


def _source_seeking(store, source):
    if source is None:
        return set(), set()
    rows = store.query(
        store.event(),
        "MATCH (p:Person {id: $source})-[r:FOUNDED]->(s:Startup) "
        "RETURN s.id, s.seeking, r.evidence_id", {"source": source}).result_set
    if not rows:
        return set(), set()
    startup_ids = [row[0] for row in rows]
    support_rows = store.query(
        store.event(),
        "MATCH (s:Startup)-[:SUPPORTED_BY]->(e:Evidence) "
        "WHERE s.id IN $startups RETURN s.id, e.id", {"startups": startup_ids}).result_set
    support_by_startup = defaultdict(set)
    for startup_id, evidence_id in support_rows:
        support_by_startup[startup_id].add(evidence_id)
    evidence_ids = [row[2] for row in rows if row[2]]
    evidence_ids.extend(eid for ids in support_by_startup.values() for eid in ids)
    valid = _evidence(store, evidence_ids)
    sought, supported = set(), set()
    for startup_id, values, founded_evidence in rows:
        startup_evidence = support_by_startup[startup_id]
        if founded_evidence not in valid or not any(eid in valid for eid in startup_evidence):
            continue
        sought.update(item for item in (values or []) if isinstance(item, str))
        supported.add(founded_evidence)
        supported.update(eid for eid in startup_evidence if eid in valid)
    return sought, supported


def public_pair_context(store, source, target, interest_topic_ids=(), seeking_topic_ids=()):
    """Classify a public pair from cited facts, with optional declared topic choices."""
    public_people_by_id = {item["id"]: item["name"] for item in public_people(store)}
    public_ids = set(public_people_by_id)
    target_listed = isinstance(target, str) and target in public_ids
    source_listed = isinstance(source, str) and source in public_ids
    source_valid = source is None or source_listed
    if not target_listed or not source_valid:
        raise ValueError("Choose listed public profiles")

    topic_data = _person_topics(store, [source, target])
    source_topics = topic_data.get(source, {}) if source else {}
    target_topics = topic_data[target]
    source_seeking, seeking_evidence = _source_seeking(store, source)
    shared = (set(source_topics) | set(interest_topic_ids)) & set(target_topics)
    sought = (source_seeking | set(seeking_topic_ids)) & set(target_topics)
    declared_names = _topic_names(store, set(interest_topic_ids) | set(seeking_topic_ids))
    related_sources = dict(source_topics)
    for topic_id in interest_topic_ids:
        related_sources.setdefault(topic_id, {
            "name": declared_names.get(topic_id, topic_id), "evidence_ids": set()})
    related_pairs = related_topic_pairs(related_sources, target_topics)
    evidence_ids = set(seeking_evidence)
    source_evidence_ids = {eid for topic in source_topics.values() for eid in topic["evidence_ids"]}
    target_evidence_ids = {eid for topic in target_topics.values() for eid in topic["evidence_ids"]}
    evidence_ids.update(source_evidence_ids)
    evidence_ids.update(target_evidence_ids)
    opener_topic_matches = defaultdict(set)
    for topic_id in shared | sought:
        if topic_id in source_topics:
            evidence_ids.update(source_topics[topic_id]["evidence_ids"])
        if topic_id in target_topics:
            target_topic_evidence = target_topics[topic_id]["evidence_ids"]
            evidence_ids.update(target_topic_evidence)
            for evidence_id in target_topic_evidence:
                opener_topic_matches[evidence_id].add(topic_id)
    for pair in related_pairs:
        evidence_ids.update(related_sources[pair["source"]["id"]]["evidence_ids"])
        evidence_ids.update(target_topics[pair["target"]["id"]]["evidence_ids"])

    routes, route_truncated = ([], False)
    route_evidence_ids = set()
    if source is not None and source != target:
        routes, route_truncated = public_try_paths(store, source, target)
        for route in routes:
            for edge in route["edges"]:
                evidence_ids.update(eid for eid in
                                    (edge.get("evidence_id"), edge.get("other_evidence_id")) if eid)
                route_evidence_ids.update(eid for eid in
                                          (edge.get("evidence_id"), edge.get("other_evidence_id")) if eid)

    if sought:
        connection_type, reason_code = "missing_piece", "desired_capability_overlap"
    elif shared:
        connection_type, reason_code = "mirror", "shared_public_topics"
    elif related_pairs:
        connection_type, reason_code = "unexpected_connection", "related_professional_topics"
    elif routes:
        connection_type, reason_code = "unexpected_connection", "cited_warm_route"
    else:
        connection_type, reason_code = "unknown", "no_supported_basis"

    best_route = min(routes, key=lambda route: (route["hops"], route["persons"])) if routes else None
    features = {
        "topic_overlap_count": len(shared),
        "seeking_overlap_count": len(sought),
        "cited_route_count": len(routes),
        "best_hops": min((route["hops"] for route in routes), default=None),
        "supported_edge_count": (sum(bool(edge.get("evidence_id")) for edge in best_route["edges"])
                                 if best_route else 0),
        "professional_evidence_count": len(evidence_ids),
        "source_listed": source_listed,
        "target_listed": target_listed,
    }
    reason = _REASONS[connection_type]
    if source is None and connection_type == "mirror":
        reason = "The target has cited work matching your selected interests."
    elif connection_type == "unexpected_connection" and related_pairs:
        reason = ("Your selected professional topics are related to the target's cited work."
                  if source is None else "The public profiles cite professionally related topics.")
    return {
        "source": source, "target": target,
        "public_names": public_people_by_id,
        "opener_target_topics": {eid: sorted(topic_id for topic_id, topic in target_topics.items() if eid in topic["evidence_ids"]) for eid in target_evidence_ids},
        "topic_names": {topic_id: topic.get("name") or topic_id for topic_id, topic in target_topics.items()},
        "connection_type": connection_type, "reason_code": reason_code,
        "reason": reason, "features": features,
        "evidence_ids": sorted(evidence_ids), "routes": routes,
        "opener_evidence_ids": sorted(target_evidence_ids | route_evidence_ids),
        "opener_topic_matches": {eid: sorted(ids) for eid, ids in opener_topic_matches.items()},
        "related_topic_matches": related_pairs,
        "related_topic_count": len(related_pairs),
        "route_truncated": route_truncated,
        "topic_matches": {"shared": sorted(shared), "seeking": sorted(sought)},
    }


def _opener_candidates(context, evidence_map, refreshed):
    route_ids = {eid for route in context["routes"] for edge in route["edges"]
                 for eid in (edge.get("evidence_id"), edge.get("other_evidence_id")) if eid}
    matched_ids = set(context["opener_evidence_ids"]) & set(evidence_map)
    refresh_by_id = {item["evidence_id"]: item for item in refreshed if item.get("evidence_id")}
    candidates = []
    seen_topics = set()
    if context.get("source") is not None:
        for route in context["routes"]:
            persons = route.get("persons", [])
            edges = route.get("edges", [])
            if (route.get("hops") != 2 or len(persons) != 3 or len(set(persons)) != 3
                    or persons[0] != context["source"] or persons[-1] != context["target"]
                    or len(edges) != 2):
                continue
            mutual_id = persons[1]
            mutual_name = context.get("public_names", {}).get(mutual_id)
            edge_evidence_ids = []
            route_is_cited = True
            for edge in edges:
                valid_edge_citations = [
                    evidence_id for evidence_id in
                    (edge.get("evidence_id"), edge.get("other_evidence_id"))
                    if evidence_id in evidence_map
                    and _valid_public_evidence(evidence_map[evidence_id])]
                if not valid_edge_citations:
                    route_is_cited = False
                    break
                edge_evidence_ids.extend(valid_edge_citations)
            edge_evidence_ids = list(dict.fromkeys(edge_evidence_ids))
            if (not route_is_cited or not isinstance(mutual_name, str) or not mutual_name.strip()
                    or not edge_evidence_ids):
                continue
            if all(edge.get("category") == "co_speaker" for edge in edges):
                text = f"I noticed we've both presented with {mutual_name}. How do you know them?"
            else:
                text = f"I noticed our public work connects through {mutual_name}. How do you know them?"
            primary_id = edge_evidence_ids[0]
            candidates.append({
                "text": text, "evidence_id": primary_id,
                "evidence_ids": edge_evidence_ids,
                "url": evidence_map[primary_id]["url"], "style": "public_route",
                "reason": "Both links in this public route have citations.",
                "mutual_name": mutual_name, "mutual_person_id": mutual_id,
            })
            break
    # Prefer evidence tied to the user's shared interests over general articles.
    ordered_ids = sorted(matched_ids, key=lambda eid: (
        eid not in context["opener_topic_matches"], eid not in route_ids, eid))
    target_name = context.get("public_names", {}).get(context["target"], "")
    greeting = f"Hey {target_name.split()[0]}, " if target_name else "Hey, "
    for evidence_id in ordered_ids:
        evidence = evidence_map.get(evidence_id)
        if not evidence:
            continue
        refreshed_item = refresh_by_id.get(evidence_id)
        shared_topic_ids = context.get("opener_topic_matches", {}).get(evidence_id, [])
        topic_ids = shared_topic_ids or context.get("opener_target_topics", {}).get(evidence_id, [])
        topic = next((context.get("topic_names", {}).get(tid) for tid in topic_ids
                      if context.get("topic_names", {}).get(tid)), None)
        talk = re.search(r'presented "([^"\n]+)"', evidence.get("claim", ""))
        if topic:
            key = topic.casefold()
            if key in seen_topics:
                continue
            seen_topics.add(key)
            prompts = (
                f"{greeting}I'm interested in {topic} too—what are you working on right now?",
                f"{greeting}your work on {topic} caught my eye—what's the hardest problem you're tackling?",
                f"{greeting}I'd love your take on {topic}—what should more people be paying attention to?",
            )
            text = prompts[min(len(candidates), 2)]
            if not shared_topic_ids:
                text = f"{greeting}your work on {topic} caught my eye—what are you exploring next?"
        elif talk:
            title = " ".join(talk.group(1).split())
            if title.casefold() in seen_topics:
                continue
            seen_topics.add(title.casefold())
            if len(title) > 85:
                # Long session titles are not natural spoken opening lines.
                text = f"{greeting}your session caught my eye—what's the one idea you'd want me to take away?"
            else:
                text = f"{greeting}what sparked your session on “{title}”?"
        else:
            # A page excerpt may contain navigation or another author's words.
            # Keep that in the citation rather than claiming the target wrote it.
            continue
        style = ("public_context" if refreshed_item else
                 "public_route" if evidence_id in route_ids else
                 "shared_topic" if evidence_id in context["opener_topic_matches"] else "public_talk")
        candidates.append({"text": text, "evidence_id": evidence_id,
                           "evidence_ids": [evidence_id],
                           "url": evidence["url"], "style": style,
                           "reason": "Based on a cited public professional source."})
        if len(candidates) == 3:
            break
    generic = (
        "What brought you to this conference?",
        "Which session are you most looking forward to?",
        "What idea from today has stuck with you?",
    )
    if matched_ids:
        generic = (
            f"{greeting}what are you most excited to be building right now?",
            f"{greeting}what problem would you love to find a collaborator for here?",
            f"{greeting}what conversation would make this conference worthwhile for you?",
        )
    while len(candidates) < 3:
        number = len(candidates)
        candidates.append({"text": generic[number], "evidence_id": None,
                           "evidence_ids": [], "url": None, "style": "public_context",
                           "reason": "General conversation prompt; no source attached."})
    return candidates


def _fit_score(answer):
    if not isinstance(answer, dict):
        return None, None
    confidence = answer.get("confidence")
    probabilities = answer.get("probabilities")
    if (type(confidence) not in (int, float) or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
            or answer.get("choice") not in ("high", "medium", "low")
            or not isinstance(probabilities, dict)):
        return None, None
    values = [probabilities.get(label) for label in ("high", "medium", "low")]
    if any(type(value) not in (int, float) or not math.isfinite(value)
           or not 0 <= value <= 1 for value in values):
        return None, None
    total = sum(values)
    if total <= 0 or confidence < 0.6:
        return None, confidence
    high, medium, _low = values
    return round(100 * (high + 0.5 * medium) / total), confidence


def _rough_evidence_score(features):
    """Give a clearly labeled starting estimate from counts, never a probability."""
    hops = features.get("best_hops")
    route_points = min(15, round(15 / hops)) if hops else 0
    score = (20
             + min(30, features.get("topic_overlap_count", 0) * 15)
             + min(25, features.get("seeking_overlap_count", 0) * 15)
             + route_points
             + min(10, features.get("professional_evidence_count", 0) * 2))
    return min(90, score)


def _rough_category_scores(features):
    evidence_points = min(10, features.get("professional_evidence_count", 0) * 2)
    overlap = features.get("topic_overlap_count", 0)
    seeking = features.get("seeking_overlap_count", 0)
    hops = features.get("best_hops")
    route_points = min(15, round(15 / hops)) if hops else 0
    routes = features.get("cited_route_count", 0)
    related = features.get("related_topic_count", 0)
    return {
        "mirror": min(90, 20 + min(60, overlap * 15) + evidence_points) if overlap else 0,
        "missing_piece": min(90, 25 + min(55, seeking * 15) + evidence_points) if seeking else 0,
        "unexpected_connection": min(90, 20 + route_points + min(15, related * 10)
                                     + evidence_points) if routes or related else 0,
    }


def assess_conversation(store, conference_id, source, target, jev=None, brightdata=None, mentions=None,
                        refresh=False, interest_topic_ids=None, seeking_topic_ids=None):
    from .brightdata import _safe_professional_url
    from .decisions import conversation_payload
    from .directory import conference_people

    if not isinstance(target, str) or not target.strip():
        raise ValueError("Choose a target profile")
    target = target.strip()
    if source is not None and (not isinstance(source, str) or not source.strip()):
        raise ValueError("Invalid public comparison profile")
    source = source.strip() if source is not None else None
    if source is not None and source == target:
        raise ValueError("Choose two different public profiles")
    interests = validate_topic_ids(store, conference_id,
                                   [] if interest_topic_ids is None else interest_topic_ids,
                                   "interest_topic_ids")
    seeking = validate_topic_ids(store, conference_id,
                                 [] if seeking_topic_ids is None else seeking_topic_ids,
                                 "seeking_topic_ids")
    conference = conference_people(store, conference_id)
    roster = {item["id"] for role in ("confirmed_attendees", "scheduled_speakers")
              for item in conference[role]}
    if target not in roster:
        raise ValueError("Target must be listed for this conference")

    context = public_pair_context(store, source, target, interests, seeking)
    features = context["features"]
    evidence_map = _evidence(store, context["evidence_ids"])
    refresh_result = {"status": "not_requested", "items": []}
    mentions_result = _empty_mentions()
    if refresh:
        sources = [(eid, evidence_map[eid]) for eid in context["opener_evidence_ids"]
                   if eid in evidence_map and _safe_professional_url(evidence_map[eid].get("url"))]
        if brightdata is None:
            refresh_result = {"status": "unavailable", "items": []}
        elif not sources:
            refresh_result = {"status": "no_sources", "items": []}
        else:
            items, failures = [], 0
            for evidence_id, evidence in sources[:3]:
                try:
                    fetched = brightdata(evidence["url"])
                    if not isinstance(fetched, dict):
                        raise ValueError("Invalid public source result")
                    items.append({"evidence_id": evidence_id, "url": evidence["url"],
                                  "title": str(fetched.get("title", ""))[:160],
                                  "excerpt": str(fetched.get("excerpt", ""))[:600]})
                except Exception:
                    failures += 1
            refresh_result = {"status": "ok" if items else "failed", "items": items}

        if mentions is None:
            mentions_result = _empty_mentions("unavailable")
        else:
            try:
                from .directory import list_conferences

                person = next((item for role in ("confirmed_attendees", "scheduled_speakers")
                               for item in conference[role] if item["id"] == target), None)
                event = next((item for item in list_conferences(store)
                              if item["id"] == conference_id), None)
                target_name = person.get("name") if person else None
                event_name = event.get("name") if event else conference_id
                if not isinstance(target_name, str) or not target_name.strip():
                    mentions_result = _empty_mentions("no_public_target_name")
                else:
                    mentions_result = _sanitize_mentions(mentions(target_name, event_name))
            except Exception:
                mentions_result = _empty_mentions("failed")

    selected_topics = set(interests) | set(seeking)
    selected_topics.update(context["topic_matches"]["shared"])
    selected_topics.update(context["topic_matches"]["seeking"])
    names_by_topic = {item["id"]: item["name"] for item in conference_topics(store, conference_id)
                      if item["id"] in selected_topics}
    public_context_topic_matches = set()
    for item in refresh_result["items"]:
        content = f"{item.get('title', '')} {item.get('excerpt', '')}".casefold()
        matches = sorted(topic_id for topic_id, topic_name in names_by_topic.items()
                         if len(topic_name.strip()) >= 3 and topic_name.casefold() in content)
        item["topic_match_ids"] = matches
        public_context_topic_matches.update(matches)

    candidates = _opener_candidates(context, evidence_map, refresh_result["items"])
    refresh_matches_by_evidence = {item["evidence_id"]: set(item.get("topic_match_ids", []))
                                   for item in refresh_result["items"] if item.get("evidence_id")}
    candidate_features = [{"candidate_id": f"candidate_{number}",
                           "cited": candidate["evidence_id"] is not None,
                           "topic_match_count": len(set(context["opener_topic_matches"].get(
                               candidate["evidence_id"], []))
                               | refresh_matches_by_evidence.get(candidate["evidence_id"], set())),
                           "style": candidate["style"]}
                          for number, candidate in enumerate(candidates, 1)]
    decision_state = {**features, "public_context_count": len(refresh_result["items"]),
                      "public_context_match_count": len(public_context_topic_matches),
                      "opener_candidates": candidate_features,
                      "mentions": mentions_result["signals"]}
    decision_payload = conversation_payload(decision_state)
    decision = None
    expected_type = context["connection_type"]
    related_only = (context["related_topic_count"] > 0
                    and features["topic_overlap_count"] == 0
                    and features["seeking_overlap_count"] == 0
                    and features["cited_route_count"] == 0)
    status = ("no_supported_basis" if expected_type == "unknown" else
              "related_topics_only" if related_only else
              "no_cited_evidence" if features["professional_evidence_count"] == 0 else
              "decision_unavailable")
    if (jev is not None and expected_type != "unknown" and not related_only
            and features["professional_evidence_count"] > 0):
        try:
            decision = jev(decision_payload)
            status = "assessed"
        except Exception:
            status = "decision_failed"

    answers = decision.get("answers", {}) if isinstance(decision, dict) else {}
    connection_answer = answers.get("connection_type") if isinstance(answers, dict) else None
    fit_answer = answers.get("conversation_fit") if isinstance(answers, dict) else None
    if decision is not None and (not isinstance(answers, dict)
                                 or not isinstance(connection_answer, dict)
                                 or not isinstance(fit_answer, dict)):
        status = "model_refused"
    elif isinstance(fit_answer, dict) and fit_answer.get("choice") == "INSUFFICIENT_EVIDENCE":
        status = "model_refused"
    type_confidence = connection_answer.get("confidence") if isinstance(connection_answer, dict) else None
    type_consistent = (expected_type != "unknown" and isinstance(connection_answer, dict)
                       and connection_answer.get("choice") == expected_type
                       and type(type_confidence) in (int, float)
                       and math.isfinite(type_confidence)
                       and 0 <= type_confidence <= 1 and type_confidence >= 0.6)
    total_score, model_confidence = _fit_score(fit_answer)
    if isinstance(connection_answer, dict) and connection_answer.get("choice") != expected_type:
        status = "category_inconsistent"
    elif (isinstance(connection_answer, dict) and type(type_confidence) in (int, float)
          and math.isfinite(type_confidence)
          and type_confidence < 0.6):
        status = "low_confidence"
    if not type_consistent:
        total_score, model_confidence = None, None

    rough_total = _rough_evidence_score(features)
    rough_by_category = _rough_category_scores({
        **features, "related_topic_count": context["related_topic_count"]})
    limitations = []
    if features["topic_overlap_count"] == 0 and features["seeking_overlap_count"] == 0:
        limitations.append("No shared topic or sought-capability overlap is established.")
    if features["cited_route_count"] == 0:
        limitations.append("No cited public route was found.")
    if features["professional_evidence_count"] == 0:
        limitations.append("No cited professional evidence was available.")
    if total_score is None:
        limitations.append("This starting estimate uses evidence counts only; it is not a model assessment.")

    categories = []
    category_specs = (
        ("mirror", "Mirror", "mirror_fit", features["topic_overlap_count"] > 0,
         ("The target has cited work matching your selected interests."
          if source is None else "Both profiles have cited public topics in common.")),
        ("missing_piece", "Missing piece", "missing_piece_fit", features["seeking_overlap_count"] > 0,
         "Cited work by the target covers a capability being sought."),
        ("unexpected_connection", "Unexpected connection", "unexpected_connection_fit",
         features["cited_route_count"] > 0 or context["related_topic_count"] > 0,
         ("Cited professional topics are related."
          if context["related_topic_count"] else "A cited public route connects the profiles.")),
    )
    for kind, label, answer_key, supported, reason in category_specs:
        fit, confidence = _fit_score(answers.get(answer_key) if isinstance(answers, dict) else None)
        if not supported or not type_consistent:
            fit, confidence = None, None
        elif fit is None:
            confidence = None
        categories.append({"type": kind, "label": label, "supported": supported,
                           "score": fit, "confidence": confidence,
                           "rough_score": rough_by_category[kind],
                           "rough_score_label": "rough evidence match",
                           "reasons": [reason] if supported else [
                               "No cited basis supports this category yet."]})
    categories.sort(key=lambda item: (
        -(item["score"] if item["score"] is not None else item["rough_score"]),
        0 if item["supported"] else 1,
        -(item["confidence"] or 0),
        {"mirror": 0, "missing_piece": 1, "unexpected_connection": 2}[item["type"]]))
    for rank, category in enumerate(categories, 1):
        category["rank"] = rank

    opener_answer = answers.get("opener") if isinstance(answers, dict) else None
    selected = opener_answer.get("choice") if isinstance(opener_answer, dict) else None
    opener_confidence = opener_answer.get("confidence") if isinstance(opener_answer, dict) else None
    mutual_index = next((index for index, candidate in enumerate(candidates)
                         if candidate.get("mutual_person_id")), None)
    if mutual_index is not None:
        order = [mutual_index] + [index for index in range(len(candidates))
                                  if index != mutual_index]
        opener_status = "mutual_route_first"
    elif (type_consistent and isinstance(selected, str)
            and selected in {item["candidate_id"] for item in candidate_features}
            and type(opener_confidence) in (int, float) and math.isfinite(opener_confidence)
            and 0.6 <= opener_confidence <= 1):
        chosen = int(selected.rsplit("_", 1)[1]) - 1
        order = [chosen] + [index for index in range(len(candidates)) if index != chosen]
        opener_status = "ranked"
    else:
        order = sorted(range(len(candidates)), key=lambda index: (
            candidates[index]["evidence_id"] is None, candidates[index]["style"], index))
        opener_status = "deterministic"
    ranked_openers = [{**candidates[index], "rank": rank}
                      for rank, index in enumerate(order, 1)]
    if (mutual_index is None and decision is not None and isinstance(opener_answer, dict)
            and opener_answer.get("choice") == "INSUFFICIENT_EVIDENCE"):
        opener_status = "abstained"

    return {
        "source": source, "target": target,
        "connection_type": expected_type,
        "reason_code": context["reason_code"],
        "reason": context["reason"],
        "categories": categories,
        "ranked_openers": ranked_openers,
        "opener_status": opener_status,
        "assessment": {"label": "uncalibrated conversation fit", "score": total_score,
                       "model_confidence": model_confidence,
                       "abstained": total_score is None,
                       "status": status,
                       "rough_score": rough_total if total_score is None else None,
                       "rough_score_label": ("starting estimate from available conference information"
                                             if total_score is None else None),
                       "estimate_kind": ("rule_based_starting_estimate" if total_score is None
                                         else "model_assessment"),
                       "limitations": limitations},
        "context": {**features, "topic_matches": context["topic_matches"],
                    "related_topic_count": context["related_topic_count"],
                    "related_topic_matches": context["related_topic_matches"],
                    "evidence_ids": context["evidence_ids"],
                    "public_context_topic_matches": sorted(public_context_topic_matches),
                    "public_context_match_count": len(public_context_topic_matches),
                    "route_truncated": context["route_truncated"]},
        "evidence_ids": context["evidence_ids"],
        "refresh": refresh_result,
        "mentions": mentions_result,
    }
