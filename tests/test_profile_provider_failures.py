"""Provider errors and empty profiles must not become cached successes."""

from collections import OrderedDict
from types import SimpleNamespace

import pytest

from warmopen import profiles


class TopicStore:
    def event(self):
        return "event"

    def query(self, graph, cypher, params):
        return SimpleNamespace(result_set=[["graphs", "Graph databases"]])


@pytest.mark.parametrize("payload,status", [
    ([{"error": "Provider detail must remain private"}], "provider_error"),
    ([{"error_code": "not_found"}], "provider_error"),
    ([], "no_profile_data"),
    ([{}], "no_profile_data"),
])
def test_failed_or_empty_profile_is_not_a_cached_success(monkeypatch, payload, status):
    monkeypatch.setattr(profiles, "_CACHE", OrderedDict())
    calls = []

    def client(platform, url):
        calls.append(platform)
        return payload

    for _ in range(2):
        result = profiles.enrich_profile(
            TopicStore(), "conference", x="https://x.com/example",
            consent=True, client=client,
        )
        assert result["status"] == status
        assert result["sources"] == []
        assert result["topics"] == []
        assert "Provider detail" not in repr(result)
    assert len(calls) == 2
