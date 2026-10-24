"""Consent-gated own-profile enrichment into existing conference topics."""

from collections import OrderedDict
import os
import re
import threading
import time
from urllib.parse import urlsplit

from .brightdata_profiles import ProfileProviderError, profile_client


_MAX_URL_LENGTH = 2048
_MAX_RECORDS = 4
_MAX_TEXT_CHARS = 12_000
_CACHE_TTL = 600
_CACHE_LIMIT = 128
_CACHE_LOCK = threading.Lock()
_CACHE = OrderedDict()
_NO_PROFILE_DATA = object()
_LINKEDIN_PATH = re.compile(r"/in/[A-Za-z0-9][A-Za-z0-9-]{0,99}/?\Z")
_X_PATH = re.compile(r"/[A-Za-z0-9_]{1,15}/?\Z")
_X_RESERVED = {
    "about", "account", "admin", "advertise", "api", "compose", "explore",
    "hashtag", "help", "home", "i", "intent", "jobs", "login", "logout",
    "messages", "notifications", "privacy", "search", "settings", "share",
    "signup", "terms", "tos",
}

# These are the professional fields documented by the two Bright Data profile
# schemas. Nested strings are accepted only under the documented professional
# containers; personal identifiers, contact details, locations, and URLs are
# filtered before matching.
_FIELDS = {
    "linkedin": {
        "position", "about", "current_company", "experience", "educations_details",
        "courses", "certifications", "publications", "patents", "projects",
        "organizations", "honors_and_awards",
    },
    "x": {"biography", "category_name"},
}
_SKIP_KEYS = {
    "id", "url", "input_url", "avatar", "image", "image_url", "profile_image_link",
    "name", "first_name", "last_name", "email", "phone", "telephone", "birth_date",
    "date", "start_date", "end_date", "location", "city", "country", "country_code",
    "external_link", "bio_links", "website", "link", "links",
}
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{6,}\d)(?!\w)")
_URL_TEXT = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)


def _validate_profile_url(platform, value):
    """Return the platform for a strictly shaped own-profile URL, or None."""
    if (platform not in ("linkedin", "x") or not isinstance(value, str)
            or not value or len(value) > _MAX_URL_LENGTH
            or any(ord(char) < 33 or ord(char) == 127 for char in value)
            or "\\" in value or "%" in value or "?" in value or "#" in value):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme.lower() != "https" or host is None or parsed.username is not None
            or parsed.password is not None or port is not None or parsed.query or parsed.fragment):
        return None
    host = host.lower()
    if parsed.netloc.lower() != host:
        return None
    if platform == "linkedin":
        if host not in {"linkedin.com", "www.linkedin.com"} or not _LINKEDIN_PATH.fullmatch(parsed.path):
            return None
        return "linkedin"
    if host not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"} or not _X_PATH.fullmatch(parsed.path):
        return None
    handle = parsed.path.strip("/").casefold()
    if handle in _X_RESERVED:
        return None
    return "x"


def _topics(store, conference_id):
    rows = store.query(
        store.event(),
        "MATCH (talk:Talk)-[:ABOUT]->(t:Topic) WHERE talk.conference = $conference "
        "RETURN DISTINCT t.id, t.name ORDER BY t.id",
        {"conference": conference_id},
    ).result_set
    found = []
    for row in rows:
        if (isinstance(row, (tuple, list)) and len(row) >= 2
                and isinstance(row[0], str) and row[0]
                and isinstance(row[1], str) and row[1].strip()):
            found.append({"id": row[0], "name": row[1].strip()})
    return found


def _text_parts(value, *, depth=0, key=None, budget=None):
    if budget is None:
        budget = [0]
    if budget[0] >= _MAX_TEXT_CHARS or depth > 5:
        return []
    if key and str(key).casefold() in _SKIP_KEYS:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        part = _URL_TEXT.sub(" ", value)
        part = _EMAIL.sub(" ", part)
        part = _PHONE.sub(" ", part)
        part = " ".join(part.split())[: min(2000, _MAX_TEXT_CHARS - budget[0])]
        budget[0] += len(part)
        return [part] if part else []
    if isinstance(value, dict):
        parts = []
        for child_key, child in list(value.items())[:40]:
            parts.extend(_text_parts(child, depth=depth + 1, key=child_key, budget=budget))
            if budget[0] >= _MAX_TEXT_CHARS:
                break
        return parts
    if isinstance(value, (list, tuple)):
        parts = []
        for child in value[:40]:
            parts.extend(_text_parts(child, depth=depth + 1, budget=budget))
            if budget[0] >= _MAX_TEXT_CHARS:
                break
        return parts
    return []


def _normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _match_topics(platform, payload, topics):
    if isinstance(payload, dict) and payload.get("status") == "pending":
        return None
    records = payload if isinstance(payload, list) else [payload]
    parts = []
    budget = [0]
    for record in records[:_MAX_RECORDS]:
        if not isinstance(record, dict):
            continue
        if record.get("error") or record.get("error_code"):
            raise ProfileProviderError("provider_invalid_response")
        for key in sorted(_FIELDS[platform]):
            if key in record:
                parts.extend(_text_parts(record[key], key=key, budget=budget))
                if budget[0] >= _MAX_TEXT_CHARS:
                    break
    if not parts:
        return _NO_PROFILE_DATA
    content = " " + _normalized(" ".join(parts)) + " "
    matched = []
    for topic in topics:
        label = _normalized(topic["name"])
        if label and f" {label} " in content:
            matched.append(topic)
    return matched


def _cache_read(key, now):
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= now:
            del _CACHE[key]
            return None
        _CACHE.move_to_end(key)
        return value


def _cache_write(key, value, now):
    with _CACHE_LOCK:
        _CACHE[key] = (now + _CACHE_TTL, value)
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_LIMIT:
            _CACHE.popitem(last=False)


def enrich_profile(store, conference_id, linkedin=None, x=None, consent=False, client=None):
    """Infer only existing conference topics from explicitly consented own URLs.

    Topic lookup is read-only in the shared event graph. Matched topic IDs and
    source URLs are copied to a separate token-protected private graph; raw provider
    records are discarded after deterministic topic matching.
    """
    empty = {"topic_ids": [], "topics": [], "sources": []}
    if consent is not True:
        return dict(empty, status="consent_required")
    submitted = [(platform, value) for platform, value in (("linkedin", linkedin), ("x", x))
                 if value not in (None, "")]
    if not submitted:
        return dict(empty, status="no_profiles")

    requests = []
    for requested_platform, value in submitted:
        platform = _validate_profile_url(requested_platform, value)
        if platform is None:
            return dict(empty, status="invalid_profile_url")
        requests.append((platform, value))

    try:
        topic_rows = _topics(store, conference_id)
    except Exception:
        return dict(empty, status="topic_lookup_failed")
    if not topic_rows:
        return dict(empty, status="no_conference_topics")
    topic_signature = tuple((item["id"], item["name"]) for item in topic_rows)

    if client is None:
        key = os.environ.get("BRIGHTDATA_API_KEY")
        if not key:
            return dict(empty, status="provider_unconfigured")
        try:
            client = profile_client(key)
        except ValueError:
            return dict(empty, status="provider_unconfigured")

    now = time.monotonic()
    collected = {}
    topic_sources = {}
    sources = []
    errors = []
    pending = False
    had_success = False
    for platform, url in requests:
        cache_key = (url.casefold(), topic_signature)
        cached = _cache_read(cache_key, now)
        if cached is not None:
            had_success = True
            collected.update((item["id"], item) for item in cached["topics"])
            sources.append({"url": url, "platform": platform})
            for item in cached["topics"]:
                topic_sources.setdefault(item["id"], {})[url] = {
                    "url": url, "platform": platform,
                }
            continue
        try:
            payload = client(platform, url)
            matched = _match_topics(platform, payload, topic_rows)
        except ProfileProviderError as exc:
            errors.append(exc.code if exc.code in {
                "provider_http_error", "provider_unavailable", "provider_response_too_large",
                "provider_invalid_response",
            } else "provider_unavailable")
            continue
        except Exception:
            # Never return/log provider exception text: it can contain request details.
            errors.append("provider_unavailable")
            continue
        if matched is None:
            pending = True
            continue
        if matched is _NO_PROFILE_DATA:
            continue
        had_success = True
        collected.update((item["id"], item) for item in matched)
        sources.append({"url": url, "platform": platform})
        for item in matched:
            topic_sources.setdefault(item["id"], {})[url] = {
                "url": url, "platform": platform,
            }
        _cache_write(cache_key, {"topics": matched}, now)

    result = dict(empty)
    result["topic_ids"] = sorted(collected)
    result["topics"] = sorted(collected.values(), key=lambda item: (item["name"].casefold(), item["id"]))
    result["sources"] = sources
    if errors and had_success:
        result["status"] = "partial"
        result["error_codes"] = sorted(set(errors))
    elif errors:
        result["status"] = "provider_error"
        result["error_codes"] = sorted(set(errors))
    elif pending and had_success:
        result["status"] = "partial"
        result["pending"] = True
    elif pending:
        result["status"] = "pending"
    elif had_success:
        result["status"] = "complete"
    else:
        result["status"] = "no_profile_data"
    if had_success and sources:
        session_topics = [
            {"id": item["id"], "name": item["name"],
             "sources": list(topic_sources.get(item["id"], {}).values())}
            for item in result["topics"]
        ]
        try:
            from .profile_sessions import create_profile_session

            result["profile_session"] = create_profile_session(store, session_topics)
        except Exception:
            # Do not leak datastore details or issue an unusable session token.
            result["status"] = "profile_storage_failed"
            result.pop("profile_session", None)
    return result
