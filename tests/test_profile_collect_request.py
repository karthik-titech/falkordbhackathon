"""Collect-by-URL request shape retains professional output selection."""

import io
import json

import pytest

from warmopen import brightdata_profiles


@pytest.mark.parametrize("platform,url,fields", [
    ("linkedin", "https://linkedin.com/in/example", "position|about|current_company"),
    ("x", "https://x.com/example", "biography|category_name"),
])
def test_collect_profile_uses_null_limit_and_selected_fields(monkeypatch, platform, url, fields):
    requests = []

    def open_request(request, timeout):
        requests.append(request)
        return io.BytesIO(b"[]")

    monkeypatch.setattr(brightdata_profiles, "urlopen", open_request)
    brightdata_profiles.profile_client("test-key")(platform, url)
    assert len(requests) == 1
    body = json.loads(requests[0].data)
    assert body["input"] == [{"url": url}]
    assert body["limit_per_input"] is None
    assert fields in body["custom_output_fields"]
