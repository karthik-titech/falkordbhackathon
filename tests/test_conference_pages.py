"""Conference directory and no-signup profile collection page contracts."""

from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "warmopen" / "static"


def test_conference_flow_pages_are_local_and_keep_old_explorer_at_explore():
    app = (STATIC.parent / "app.py").read_text(encoding="utf-8")
    conference_js = (STATIC / "conferences.js").read_text(encoding="utf-8")
    start_js = (STATIC / "start.js").read_text(encoding="utf-8")
    try_html = (STATIC / "try.html").read_text(encoding="utf-8")
    assert '"/try": "conferences.html"' in app
    assert '"/explore": "try.html"' in app
    assert '"/start": "start.html"' in app
    assert "public_landing=False" in app
    assert '"/": "conferences.html" if public_landing else "index.html"' in app
    assert '"/workspace": "index.html"' in app
    assert "/api/conferences" in conference_js
    assert 'fetch("/api/conferences")' in start_js
    assert "sessionStorage.setItem" in start_js
    assert "linkedin.com" in start_js and "twitter.com" in start_js and "x.com" in start_js
    assert "url.search" in start_js and "url.hash" in start_js
    assert "fetch(" not in try_html


def test_profile_research_requires_explicit_consent_and_continue_action():
    start_js = (STATIC / "start.js").read_text(encoding="utf-8")
    start_html = (STATIC / "start.html").read_text(encoding="utf-8")
    assert 'id="profile-consent" type="checkbox"' in start_html
    assert 'id="continue-button" type="button" class="primary-button">Find my interests' in start_html
    assert 'Use my public profile to suggest conference interests' in start_html
    assert 'fetch("/api/profile/enrich"' in start_js
    assert 'method: "POST"' in start_js and 'consent: true' in start_js
    assert 'if (!$("profile-consent").checked)' in start_js
    assert 'if (enrichmentFinished) { goToExplore(); return; }' in start_js
    assert 'const body = {conference_id: conferenceId, consent: true};' in start_js
    assert 'if (links.linkedin) body.linkedin = links.linkedin;' in start_js
    assert 'if (links.x) body.x = links.x;' in start_js
    assert "window.location.assign(`/explore?conference=" in start_js
    assert 'fetch("/api/profile/enrich"' not in (STATIC / "try.js").read_text(encoding="utf-8")
    assert "We look up your links only after you opt in and choose Find my interests." in start_html
    assert 'sessionStorage.setItem(PROFILE_CONTEXT_KEY' in start_js
    assert 'seeking_topic_ids: []' in start_js
    assert "Profile research could not be completed yet." in start_js
    assert "window.location.assign(`/explore?conference=" in start_js
    assert "No confirmed attendee list imported yet." in (STATIC / "conferences.js").read_text(encoding="utf-8")
    assert "profile-linkedin" in start_html
