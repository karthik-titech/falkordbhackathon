"""Explicit, bounded Bright Data refreshes for public professional sources."""

from collections import OrderedDict
from html.parser import HTMLParser
import ipaddress
import json
import math
import threading
import time
from urllib.parse import parse_qsl, urlsplit
from urllib.request import Request, urlopen

API_URL = "https://api.brightdata.com/request"
MAX_RESPONSE_BYTES = 80_000
MAX_TEXT_LENGTH = 600
MAX_CACHE_ITEMS = 128
_SOCIAL_HOSTS = ("linkedin.com", "facebook.com", "x.com", "twitter.com", "instagram.com",
                 "tiktok.com", "threads.net", "snapchat.com")
_SENSITIVE_QUERY_KEYS = {"token", "access_token", "api_key", "apikey", "password", "secret", "auth"}


def _safe_professional_url(value):
    if (not isinstance(value, str) or not value or any(ord(char) < 32 or char.isspace() for char in value)):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        _ = parsed.port
        normalized_host = host.lower().rstrip(".") if host else ""
        if (parsed.scheme not in ("http", "https") or not parsed.netloc or not host
                or parsed.username or parsed.password or normalized_host == "localhost"
                or normalized_host.endswith((".localhost", ".local", ".internal"))):
            return False
        lower_host = normalized_host.removeprefix("www.")
        if any(lower_host == domain or lower_host.endswith("." + domain) for domain in _SOCIAL_HOSTS):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            if host.replace(".", "").isdigit():
                return False
        if any(key.lower() in _SENSITIVE_QUERY_KEYS
               for key, _item in parse_qsl(parsed.query, keep_blank_values=True)):
            return False
    except ValueError:
        return False
    return True


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.text = []
        self.in_title = False
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        value = " ".join(data.split())
        if not value or self.skip_depth:
            return
        if self.in_title:
            self.title.append(value)
        else:
            self.text.append(value)


def _summarize(body):
    page = _PageText()
    try:
        page.feed(body.decode("utf-8", errors="replace"))
        page.close()
    except Exception:
        return {"title": "", "excerpt": ""}
    title = " ".join(page.title)[:160]
    excerpt = " ".join(page.text)
    return {"title": title, "excerpt": excerpt[:MAX_TEXT_LENGTH]}


def brightdata_client(api_key=None, zone=None, timeout=8.0, ttl=900):
    """Build a callable. Construction is offline; each fetch is explicit."""
    if not api_key or not zone:
        return None
    if (not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0
            or type(ttl) is not int or ttl < 0):
        raise ValueError("Invalid Bright Data client settings")
    cache = OrderedDict()
    lock = threading.Lock()

    def fetch(url):
        if not _safe_professional_url(url):
            raise ValueError("Source URL is not an allowed public professional URL")
        now = time.monotonic()
        with lock:
            entry = cache.get(url)
            if entry and entry[0] > now:
                cache.move_to_end(url)
                return dict(entry[1])
            cache.pop(url, None)

        payload = {"zone": zone, "url": url, "format": "raw"}
        request = Request(API_URL, data=json.dumps(payload, allow_nan=False).encode("utf-8"),
                          headers={"Authorization": "Bearer " + api_key,
                                   "Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except Exception as exc:
            raise ValueError("Public source refresh failed") from exc
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("Public source response exceeded the size limit")
        result = {"url": url, **_summarize(body)}
        with lock:
            if ttl:
                cache[url] = (time.monotonic() + ttl, result)
                cache.move_to_end(url)
                while len(cache) > MAX_CACHE_ITEMS:
                    cache.popitem(last=False)
        return dict(result)

    return fetch
