"""Mocked public post mention collection and signal contracts."""

from datetime import date, datetime, timedelta, timezone
import io
import json

import pytest

from warmopen import mentions


@pytest.fixture(autouse=True)
def _clear_cache():
    with mentions._CACHE_LOCK:
        mentions._CACHE.clear()
    yield
    with mentions._CACHE_LOCK:
        mentions._CACHE.clear()


class _Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _json_response(payload):
    return _Response(json.dumps(payload).encode("utf-8"))


def test_missing_key_or_zone_returns_none_without_io(monkeypatch):
    calls = []
    monkeypatch.setattr(mentions, "urlopen", lambda *args, **kwargs: calls.append(args))
    assert mentions.mentions_client(None, "zone") is None
    assert mentions.mentions_client("key", " ") is None
    assert calls == []


@pytest.mark.parametrize(("url", "platform", "expected"), [
    ("http://x.com/alice/status/123", "x", "https://x.com/alice/status/123"),
    ("https://twitter.com/alice/status/123?utm_source=search#top", "x", "https://x.com/alice/status/123"),
    ("https://www.linkedin.com/posts/alice_launch-activity-123?trk=feed", "linkedin",
     "https://www.linkedin.com/posts/alice_launch-activity-123"),
])
def test_canonicalizes_only_public_post_urls(url, platform, expected):
    assert mentions._canonical_post_url(url, platform) == expected


@pytest.mark.parametrize(("url", "platform"), [
    ("https://x.com/alice", "x"),
    ("https://x.com/alice/status/1/extra", "x"),
    ("https://x.com/search/status/123", "x"),
    ("https://x.com/alice/status/notdigits", "x"),
    ("https://x.com.evil/alice/status/123", "x"),
    ("https://alice@x.com/alice/status/123", "x"),
    ("https://x.com:443/alice/status/123", "x"),
    ("https://linkedin.com/in/alice", "linkedin"),
    ("https://linkedin.com/posts/alice%2f..", "linkedin"),
    ("https://evil.test/posts/alice_launch-1", "linkedin"),
])
def test_rejects_profiles_lookalike_hosts_and_unsafe_post_urls(url, platform):
    assert mentions._canonical_post_url(url, platform) is None


def test_searches_two_sites_and_filters_for_exact_name_professional_posts_and_safe_fields(monkeypatch):
    today_date = datetime.now(timezone.utc).date()
    today = today_date.isoformat()
    yesterday = (today_date - timedelta(days=1)).isoformat()
    old_date = (today_date - timedelta(days=500)).isoformat()
    payloads = [
        {"organic": [
            {
                "link": "http://twitter.com/alice/status/101?utm=1#frag",
                "title": "Alice Example gives an exciting keynote at Summit Week",
                "description": "Great product launch; write to alice@example.test or call +1 415-555-0134",
                "date": yesterday,
            },
            {
                "link": "https://x.com/alice/status/102",
                "title": "Alice Example startup receives complaints",
                "description": "Founder report: a serious issue and a major award",
                "date": old_date,
            },
            {
                "link": "https://x.com/alice/status/103",
                "title": "Alice Example attends an engineering conference",
                "description": "Research updates",
                "date": "yesterday",
            },
            {
                "link": "https://x.com/alice/status/104",
                "title": "Alice Example2 launches a product",
                "description": "Founder announcement",
            },
            {
                "link": "https://x.com/alice/status/105",
                "title": "Alice Example has an ordinary personal day",
                "description": "No professional mention terms here",
            },
            {
                "link": "https://x.com/alice",
                "title": "Alice Example research keynote",
                "description": "Profile page, not a public post",
            },
            {
                "link": "https://elsewhere.test/alice/status/106",
                "title": "Alice Example launches a startup",
            },
        ]},
        {"organic": [
            {
                "url": "https://www.linkedin.com/posts/alice_conference-activity-201?trk=search",
                "title": "Alice Example founder shares a neutral company update",
                "snippet": "Product engineering notes",
                "date": today + "T12:00:00Z",
            },
            {
                "url": "https://www.linkedin.com/in/alice",
                "title": "Alice Example founder profile, keynote speaker",
            },
        ]},
    ]
    captured = []

    def fake_urlopen(request, timeout):
        captured.append((request, timeout))
        return _json_response(payloads[len(captured) - 1])

    monkeypatch.setattr(mentions, "urlopen", fake_urlopen)
    client = mentions.mentions_client("test-key", "serp-zone")
    result = client("Alice Example", "Summit Week")

    assert result["status"] == "ok"
    assert len(captured) == 2
    assert result["signals"] == {
        "mentions_available": True,
        "professional_mention_count": 4,
        "positive_mention_count": 1,
        "neutral_mention_count": 2,
        "critical_mention_count": 0,
        "unclear_mention_count": 1,
        "recent_mention_count": 2,
        "mention_source_count": 4,
    }
    assert {item["platform"] for item in result["items"]} == {"x", "linkedin"}
    positive = next(item for item in result["items"] if item["url"] == "https://x.com/alice/status/101")
    assert positive["published_at"] == (today_date - timedelta(days=1)).isoformat()
    assert positive["tone"] == "positive"
    assert "alice@example.test" not in repr(result)
    assert "415-555-0134" not in repr(result)
    for request, timeout in captured:
        body = json.loads(request.data.decode("utf-8"))
        assert body["zone"] == "serp-zone"
        assert body["format"] == "raw"
        assert body["url"].startswith("https://www.google.com/search?")
        assert timeout == 12
        assert request.headers["Authorization"] == "Bearer test-key"
    assert "site%3Ax.com" in captured[0][0].data.decode("utf-8") or "site:x.com" in captured[0][0].data.decode("utf-8")
    assert "site%3Alinkedin.com%2Fposts" in captured[1][0].data.decode("utf-8") or "site:linkedin.com/posts" in captured[1][0].data.decode("utf-8")


def test_uses_exact_name_and_event_in_quoted_search_queries(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return _json_response({"organic": []})

    monkeypatch.setattr(mentions, "urlopen", fake_urlopen)
    mentions.mentions_client("key", "zone")("Zoë Example", "AI Expo 2026")
    assert len(requests) == 2
    for request in requests:
        body = json.loads(request.data.decode("utf-8"))
        assert '"zoe example"' in body["url"] or "%22zoe+example%22" in body["url"]
        assert '"ai expo 2026"' in body["url"] or "%22ai+expo+2026%22" in body["url"]
        assert "brd_json=1" in body["url"]
        assert "num=5" in body["url"]


def test_constructor_is_lazy_and_successful_result_is_cached(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        return _json_response({"organic": [{
            "link": "https://x.com/alice/status/222",
            "title": "Alice Example announces a startup product",
            "description": "Founder launch",
        }]})

    monkeypatch.setattr(mentions, "urlopen", fake_urlopen)
    client = mentions.mentions_client("key", "zone", ttl=600)
    assert calls == []
    first = client("Alice Example", "Summit Week")
    second = client("Alice Example", "Summit Week")
    assert first == second
    assert len(calls) == 2


def test_failures_are_sanitized_and_do_not_cache(monkeypatch):
    calls = []

    def failed_urlopen(request, timeout):
        calls.append(request)
        raise mentions.HTTPError(request.full_url, 401, "secret provider detail", {}, None)

    monkeypatch.setattr(mentions, "urlopen", failed_urlopen)
    client = mentions.mentions_client("key", "zone")
    result = client("Alice Example", "Summit Week")
    assert result["status"] == "failed"
    assert result["items"] == []
    assert result["signals"]["mentions_available"] is False
    assert "secret provider detail" not in repr(result)
    assert len(calls) == 2


def test_network_unavailability_is_reported_without_provider_details(monkeypatch):
    def unavailable(request, timeout):
        raise mentions.URLError("private network detail")

    monkeypatch.setattr(mentions, "urlopen", unavailable)
    result = mentions.mentions_client("key", "zone")("Alice Example", "Summit Week")
    assert result["status"] == "unavailable"
    assert result["signals"]["mentions_available"] is False
    assert "private network detail" not in repr(result)


@pytest.mark.parametrize(("text", "expected"), [
    ("Great product launch", "positive"),
    ("serious complaints and great awards", "unclear"),
    ("not a great launch", "critical"),
    ("keynote at the conference", "neutral"),
    ("", "unclear"),
])
def test_tone_uses_only_a_small_lexicon_and_marks_mixed_or_empty_unclear(text, expected):
    assert mentions._tone(text) == expected


def test_iso_date_parsing_does_not_invent_dates():
    assert mentions._parse_date("2026-10-24") == "2026-10-24"
    assert mentions._parse_date("2026-10-24T12:30:00Z") == "2026-10-24T12:30:00+00:00"
    assert mentions._parse_date("yesterday") is None
    assert mentions._parse_date(None) is None
