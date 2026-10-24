"""The profile form's canonical links must work at the server boundary."""

import pytest

from warmopen.profiles import _validate_profile_url


@pytest.mark.parametrize("url", [
    "https://linkedin.com/in/conference-demo",
    "https://www.linkedin.com/in/conference-demo",
    "https://www.linkedin.com/in/conference-demo/",
])
def test_linkedin_browser_and_shared_url_forms(url):
    assert _validate_profile_url("linkedin", url) == "linkedin"


def test_browser_canonical_link_reaches_profile_provider(loaded):
    from warmopen.app import _live

    called = []

    def scrape(platform, url):
        called.append((platform, url))
        return [{"about": "Graph databases and agents"}]

    response = _live(loaded, "POST", "/api/profile/enrich", {
        "conference_id": "ghu", "linkedin": "https://www.linkedin.com/in/conference-demo",
        "consent": True,
    }, None, None, None, profile_client=scrape)
    assert called == [("linkedin", "https://www.linkedin.com/in/conference-demo")]
    assert response["status"] == "complete"
    assert "graphs" in response["topic_ids"]


def test_one_link_works_when_the_other_optional_field_is_empty(loaded):
    from warmopen.app import _live

    called = []

    def scrape(platform, url):
        called.append(platform)
        return [{"about": "Graph databases"}]

    response = _live(loaded, "POST", "/api/profile/enrich", {
        "conference_id": "ghu", "linkedin": "https://www.linkedin.com/in/one-link-only",
        "x": "", "consent": True,
    }, None, None, None, profile_client=scrape)
    assert called == ["linkedin"]
    assert response["status"] == "complete"


@pytest.mark.parametrize("url", [
    "https://www.x.com/home/", "https://www.linkedin.com.evil.example/in/person/",
    "https://www.linkedin.com/in/person/?token=private",
])
def test_url_variants_keep_security_checks(url):
    platform = "x" if "x.com" in url else "linkedin"
    assert _validate_profile_url(platform, url) is None
