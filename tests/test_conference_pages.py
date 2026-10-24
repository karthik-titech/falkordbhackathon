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


def test_profile_links_stay_in_session_storage_and_are_not_looked_up_or_matched():
    start_js = (STATIC / "start.js").read_text(encoding="utf-8")
    assert "JSON.stringify({linkedin: linkedin.value, x: x.value})" in start_js
    assert "fetch(linkedin" not in start_js and "fetch(x" not in start_js
    assert 'method: "POST"' not in start_js and "headers:" not in start_js
    assert "Profile lookup is not connected yet." in start_js
    assert "window.location.assign(`/explore?conference=" in start_js
    assert "No confirmed attendee list imported yet." in (STATIC / "conferences.js").read_text(encoding="utf-8")
    assert "profile-linkedin" in (STATIC / "start.html").read_text(encoding="utf-8")
