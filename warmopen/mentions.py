"""Bounded public post mentions via Bright Data's SERP API."""

from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
import json
import re
import threading
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


_ENDPOINT = "https://api.brightdata.com/request"
_MAX_BYTES = 1_000_000
_MAX_RESULTS_PER_SEARCH = 5
_MAX_ITEMS = 8
_MAX_TITLE = 150
_MAX_EXCERPT = 280
_CACHE_LIMIT = 64
_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_PRO_TERMS = {
    "talk", "keynote", "conference", "startup", "product", "launch", "research",
    "company", "founder", "engineering", "open source",
}
_POSITIVE = {
    "great", "excited", "successful", "wins", "award", "innovative", "impressive",
    "congratulations", "congrats", "excellent", "leading", "breakthrough", "growth",
    "praise", "shipped", "launched",
}
_CRITICAL = {
    "criticized", "criticism", "failed", "failure", "lawsuit", "controversy", "layoffs",
    "delayed", "problem", "concern", "negative", "fraud", "scam", "poor", "misleading",
    "complaint", "complaints", "issue", "issues",
}
_NEGATION = {"not", "no", "never", "hardly", "isnt", "wasnt", "without"}
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{6,}\d)(?!\w)")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_CACHE_TTL_MAX = 86_400
_X_RESERVED = {"about", "explore", "i", "intent", "login", "messages", "search", "settings"}


def _empty_signals():
    return {
        "mentions_available": False,
        "professional_mention_count": 0,
        "positive_mention_count": 0,
        "neutral_mention_count": 0,
        "critical_mention_count": 0,
        "unclear_mention_count": 0,
        "recent_mention_count": 0,
        "mention_source_count": 0,
    }


def _normalized(text):
    value = unicodedata.normalize("NFKD", text).casefold()
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _search_phrase(value):
    return _normalized(value)


def _serp_url(target_name, conference_name, platform):
    site = "site:x.com" if platform == "x" else "site:linkedin.com/posts"
    terms = ' OR '.join(f'"{term}"' for term in sorted(_PRO_TERMS))
    query = f'"{_search_phrase(target_name)}" "{_search_phrase(conference_name)}" ({terms}) {site}'
    return "https://www.google.com/search?" + urlencode({"q": query, "brd_json": "1", "num": "5"})


def _canonical_post_url(value, platform):
    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    if any(ord(char) < 33 or ord(char) == 127 for char in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme.lower() not in {"http", "https"} or not host
            or parsed.username is not None or parsed.password is not None or port is not None):
        return None
    host = host.lower()
    if parsed.netloc.lower() != host:
        return None
    path = parsed.path
    if platform == "x":
        if host not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
            return None
        if not re.fullmatch(r"/[A-Za-z0-9_]{1,15}/status/[0-9]{1,30}", path):
            return None
        if path.split("/", 2)[1].casefold() in _X_RESERVED:
            return None
        return urlunsplit(("https", "x.com", path, "", ""))
    if host not in {"linkedin.com", "www.linkedin.com"}:
        return None
    if not re.fullmatch(r"/posts/[A-Za-z0-9_-]{1,300}", path):
        return None
    return urlunsplit(("https", "www.linkedin.com", path, "", ""))


def _clean_text(value, limit):
    if not isinstance(value, str):
        return ""
    value = _URL.sub(" ", value)
    value = _EMAIL.sub(" ", value)
    value = _PHONE.sub(" ", value)
    value = " ".join(value.split())
    return value[:limit].strip()


def _parse_date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            return date.fromisoformat(candidate).isoformat()
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        return parsed.isoformat()
    except ValueError:
        return None


def _tone(text):
    words = _normalized(text).split()
    if not words:
        return "unclear"
    positive = set()
    critical = set()
    for index, word in enumerate(words):
        negated = any(item in _NEGATION for item in words[max(0, index - 3):index])
        if word in _POSITIVE:
            (critical if negated else positive).add(word)
        elif word in _CRITICAL:
            (positive if negated else critical).add(word)
    if positive and critical:
        return "unclear"
    if positive:
        return "positive"
    if critical:
        return "critical"
    return "neutral"


def _has_exact_name(text, target_name):
    haystack = " " + _normalized(text) + " "
    needle = _normalized(target_name)
    return bool(needle) and f" {needle} " in haystack


def _has_professional_term(text):
    words = " " + _normalized(text) + " "
    return any(f" {_normalized(term)} " in words for term in _PRO_TERMS)


def _organic_records(payload):
    if not isinstance(payload, dict):
        return []
    rows = payload.get("organic")
    if not isinstance(rows, list):
        return []
    return [item for item in rows[:_MAX_RESULTS_PER_SEARCH] if isinstance(item, dict)]


def _items_from(payload, platform, target_name):
    items = []
    for record in _organic_records(payload):
        title = _clean_text(record.get("title"), _MAX_TITLE)
        excerpt = _clean_text(record.get("description") or record.get("snippet"), _MAX_EXCERPT)
        combined = f"{title} {excerpt}"
        if not _has_exact_name(combined, target_name) or not _has_professional_term(combined):
            continue
        url = _canonical_post_url(record.get("link") or record.get("url"), platform)
        if not url:
            continue
        item = {
            "url": url,
            "title": title,
            "excerpt": excerpt,
            "published_at": _parse_date(record.get("date")),
            "tone": _tone(combined),
            "platform": platform,
        }
        items.append(item)
    return items


def _signals(items):
    counts = _empty_signals()
    counts["mentions_available"] = True
    counts["professional_mention_count"] = len(items)
    for item in items:
        counts[f"{item['tone']}_mention_count"] += 1
    today = datetime.now(timezone.utc).date()
    year_ago = today - timedelta(days=365)
    for item in items:
        published = item["published_at"]
        if not published:
            continue
        try:
            parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
            published_date = parsed.date()
        except ValueError:
            try:
                published_date = date.fromisoformat(published)
            except ValueError:
                continue
        if year_ago <= published_date <= today:
            counts["recent_mention_count"] += 1
    counts["mention_source_count"] = len({item["url"] for item in items})
    return counts


def _result(status, items=()):
    bounded = list(items)[:_MAX_ITEMS]
    signals = _signals(bounded)
    signals["mentions_available"] = status == "ok"
    return {"status": status, "items": bounded, "signals": signals}


def _cache_get(key, now):
    with _CACHE_LOCK:
        value = _CACHE.get(key)
        if value is None:
            return None
        expires_at, result = value
        if expires_at <= now:
            del _CACHE[key]
            return None
        _CACHE.move_to_end(key)
        return {
            "status": result["status"],
            "items": [dict(item) for item in result["items"]],
            "signals": dict(result["signals"]),
        }


def _cache_put(key, result, now, ttl):
    with _CACHE_LOCK:
        _CACHE[key] = (now + ttl, result)
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_LIMIT:
            _CACHE.popitem(last=False)


def mentions_client(api_key, zone, timeout=12, ttl=600):
    """Create a lazy client; return None when credentials or a zone are absent."""
    if not isinstance(api_key, str) or not api_key.strip() or not isinstance(zone, str) or not zone.strip():
        return None
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
        raise ValueError("Invalid SERP timeout")
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or not 0 < ttl <= _CACHE_TTL_MAX:
        raise ValueError("Invalid SERP cache lifetime")
    secret = api_key.strip()
    zone_name = zone.strip()
    timeout_value = float(timeout)
    ttl_value = float(ttl)

    def fetch(target_name, conference_name):
        empty = _result("failed")
        if (not isinstance(target_name, str) or not target_name.strip() or len(target_name) > 160
                or not isinstance(conference_name, str) or not conference_name.strip()
                or len(conference_name) > 200):
            return empty
        if not _search_phrase(target_name) or not _search_phrase(conference_name):
            return empty
        cache_key = (_normalized(target_name), _normalized(conference_name))
        now = time.monotonic()
        cached = _cache_get(cache_key, now)
        if cached is not None:
            return cached
        found = {}
        succeeded = 0
        unavailable = False
        for platform in ("x", "linkedin"):
            body = json.dumps({
                "zone": zone_name,
                "url": _serp_url(target_name, conference_name, platform),
                "format": "raw",
            }).encode("utf-8")
            request = Request(
                _ENDPOINT,
                data=body,
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=timeout_value) as response:
                    if getattr(response, "status", 200) != 200:
                        continue
                    content = response.read(_MAX_BYTES + 1)
            except HTTPError:
                continue
            except (URLError, TimeoutError, OSError):
                unavailable = True
                continue
            except Exception:
                # Provider or transport exception strings can contain request details.
                unavailable = True
                continue
            if len(content) > _MAX_BYTES:
                continue
            try:
                payload = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            succeeded += 1
            for item in _items_from(payload, platform, target_name):
                found.setdefault(item["url"], item)
        items = sorted(found.values(), key=lambda item: (item.get("published_at") or "", item["url"]), reverse=True)[:_MAX_ITEMS]
        if succeeded == 0:
            return _result("unavailable" if unavailable else "failed")
        result = _result("ok", items)
        _cache_put(cache_key, result, now, ttl_value)
        return result

    return fetch
