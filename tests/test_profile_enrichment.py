"""Privacy and consent contracts for own-profile enrichment."""

import io
import json

import pytest

from warmopen import brightdata_profiles, profiles


class _Result:
    def __init__(self, rows):
        self.result_set = rows


class _Store:
    def __init__(self, topics):
        self._topics = topics
        self.queries = []

    def event(self):
        return "event"

    def query(self, graph, cypher, params=None):
        self.queries.append((graph, cypher, params or {}))
        assert graph == "event"
        assert "MATCH (talk:Talk)-[:ABOUT]->(t:Topic)" in cypher
        return _Result([(item["id"], item["name"]) for item in self._topics])


@pytest.fixture(autouse=True)
def _clear_cache():
    with profiles._CACHE_LOCK:
        profiles._CACHE.clear()
    yield
    with profiles._CACHE_LOCK:
        profiles._CACHE.clear()


def test_requires_explicit_consent_before_graph_or_provider_access():
    store = _Store([{"id": "ai", "name": "AI"}])
    calls = []
    result = profiles.enrich_profile(
        store, "event", linkedin="https://www.linkedin.com/in/owner", consent=False,
        client=lambda *args: calls.append(args),
    )
    assert result["status"] == "consent_required"
    assert result["topics"] == []
    assert calls == []
    assert store.queries == []


@pytest.mark.parametrize("url", [
    "http://linkedin.com/in/owner",
    "https://www.linkedin.com/company/owner",
    "https://linkedin.com/in/owner/extra",
    "https://linkedin.com/in/%2e%2e",
    "https://linkedin.com:443/in/owner",
    "https://owner@linkedin.com/in/owner",
    "https://linkedin.com/in/owner?x=1",
    "https://linkedin.com/in/owner#bio",
    "https://linkedin.com.evil/in/owner",
    "https://x.com/search",
    "https://x.com/owner/status/1",
    "https://x.com/owner?lang=en",
    "https://twitter.com/owner/",
])
def test_rejects_non_profile_or_unsafe_urls_without_provider_calls(url):
    store = _Store([{"id": "ai", "name": "AI"}])
    calls = []
    result = profiles.enrich_profile(
        store, "event", linkedin=url, consent=True,
        client=lambda *args: calls.append(args),
    )
    assert result["status"] == "invalid_profile_url"
    assert calls == []


def test_validates_linkedin_and_x_url_variants():
    assert profiles._validate_profile_url("linkedin", "https://linkedin.com/in/alice-7") == "linkedin"
    assert profiles._validate_profile_url("x", "https://x.com/alice_7") == "x"
    assert profiles._validate_profile_url("x", "https://twitter.com/alice_7") == "x"


def test_returns_only_known_topics_and_sources_without_profile_text_or_pii():
    store = _Store([
        {"id": "ai_infra", "name": "AI Infrastructure"},
        {"id": "climate", "name": "Climate Tech"},
    ])
    raw = {
        "position": "Founder working on AI infrastructure",
        "about": "Building reliable AI Infrastructure. mail owner@example.test call +1 415-555-0112",
        "current_company": {"industry": "AI Infrastructure", "website": "https://private.example"},
        "email": "secret@example.test",
        "birth_date": "2000-01-01",
        "url": "https://arbitrary.example/redirect",
        "profile_name": "Owner Secret Name",
    }
    calls = []

    def client(platform, url):
        calls.append((platform, url))
        return [raw]

    result = profiles.enrich_profile(
        store, "event", linkedin="https://linkedin.com/in/owner", consent=True, client=client,
    )
    assert result == {
        "topic_ids": ["ai_infra"],
        "topics": [{"id": "ai_infra", "name": "AI Infrastructure"}],
        "sources": [{"url": "https://linkedin.com/in/owner", "platform": "linkedin"}],
        "status": "complete",
    }
    assert calls == [("linkedin", "https://linkedin.com/in/owner")]
    assert len(store.queries) == 1
    rendered = repr(result)
    for secret in ("Owner Secret Name", "owner@example.test", "415-555-0112", "private.example"):
        assert secret not in rendered
    assert "https://arbitrary.example/redirect" not in rendered


def test_x_uses_only_biography_and_categories_and_cache_avoids_second_call():
    store = _Store([{"id": "robotics", "name": "Robotics"}])
    calls = []

    def client(platform, url):
        calls.append((platform, url))
        return [{
            "biography": "I work in robotics",
            "category_name": ["Robotics"],
            "profile_name": "Sensitive Name",
            "posts": [{"text": "Climate Tech"}],
        }]

    kwargs = {"x": "https://x.com/owner", "consent": True, "client": client}
    first = profiles.enrich_profile(store, "event", **kwargs)
    second = profiles.enrich_profile(store, "event", **kwargs)
    assert first["topic_ids"] == ["robotics"]
    assert second == first
    assert calls == [("x", "https://x.com/owner")]
    assert "Sensitive Name" not in repr(second)
    assert "Climate Tech" not in repr(second)


def test_provider_failures_are_sanitized_and_do_not_expose_exception_text():
    store = _Store([{"id": "ai", "name": "AI"}])

    def failed_client(platform, url):
        raise RuntimeError("Bearer PRIVATE profile body")

    result = profiles.enrich_profile(
        store, "event", x="https://x.com/owner", consent=True, client=failed_client,
    )
    assert result["status"] == "provider_error"
    assert result["error_codes"] == ["provider_unavailable"]
    assert "PRIVATE" not in repr(result)


def test_async_provider_response_is_reported_as_pending_without_polling_or_snapshot_leak():
    store = _Store([{"id": "ai", "name": "AI"}])
    calls = []

    def pending_client(platform, url):
        calls.append((platform, url))
        return {"status": "pending", "snapshot_id": "private-snapshot"}

    result = profiles.enrich_profile(
        store, "event", linkedin="https://linkedin.com/in/owner", consent=True,
        client=pending_client,
    )
    assert result["status"] == "pending"
    assert calls == [("linkedin", "https://linkedin.com/in/owner")]
    assert "snapshot_id" not in repr(result)


def test_brightdata_client_posts_documented_endpoint_and_selects_only_professional_fields(monkeypatch):
    captured = {}

    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["headers"] = request.headers
        captured["timeout"] = timeout
        return Response(b"[]")

    monkeypatch.setattr(brightdata_profiles, "urlopen", fake_urlopen)
    client = brightdata_profiles.profile_client("test-key", timeout=30)
    assert client("linkedin", "https://linkedin.com/in/owner") == []
    assert captured["url"].startswith("https://api.brightdata.com/datasets/v3/scrape?")
    assert "dataset_id=gd_l1viktl72bvl7bjuj0" in captured["url"]
    assert "format=json" in captured["url"]
    assert "notify=false" in captured["url"]
    assert captured["body"]["input"] == [{"url": "https://linkedin.com/in/owner"}]
    assert "position|about|current_company|experience" in captured["body"]["custom_output_fields"]
    assert "name" not in captured["body"]["custom_output_fields"]
    assert captured["timeout"] == 30
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_brightdata_client_is_lazy_and_sanitizes_http_errors(monkeypatch):
    calls = []

    def failed_urlopen(request, timeout):
        calls.append((request, timeout))
        raise brightdata_profiles.HTTPError(request.full_url, 401, "secret detail", {}, None)

    monkeypatch.setattr(brightdata_profiles, "urlopen", failed_urlopen)
    client = brightdata_profiles.profile_client("test-key")
    assert calls == []
    with pytest.raises(brightdata_profiles.ProfileProviderError) as error:
        client("x", "https://x.com/owner")
    assert error.value.code == "provider_http_error"
    assert "secret detail" not in str(error.value)
