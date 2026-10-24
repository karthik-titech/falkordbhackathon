"""ptc3e frozen contract: slide-style restyle of the requester and owner pages.

Source: Karthik's reference slides 2026-10-24 (heavy grotesk headline, small
tracked monospace labels, off-white page, olive square markers, thin rules,
numbered step track along the bottom). Visual fit is judged by the gate seat
from Firefox screenshots; this file pins structure, ids and constraints.
"""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "warmopen" / "static"
STEPS = ["find", "ask", "approve", "score", "open"]


def _read(name):
    return (STATIC / name).read_text(encoding="utf-8")


def test_step_track_has_five_ordered_steps():
    html = _read("index.html")
    track = re.search(r'<ol[^>]*id="step-track"[^>]*>(.*?)</ol>', html, re.S)
    assert track, "requester page needs <ol id=\"step-track\">"
    steps = re.findall(r'data-step="([a-z]+)"', track.group(1))
    assert steps == STEPS


def test_app_sets_current_step_from_progress():
    js = _read("app.js")
    assert "step-track" in js
    assert "aria-current" in js
    for step in STEPS:
        assert f'"{step}"' in js


def test_headline_and_kicker_exist_and_update():
    html = _read("index.html")
    assert re.search(r'<h1[^>]*id="headline"', html)
    assert 'id="kicker"' in html
    js = _read("app.js")
    assert '$("headline")' in js and '$("kicker")' in js


def test_earlier_ids_and_copy_survive():
    html = _read("index.html")
    for element_id in ("path-view", "agent-timeline", "mode-banner", "find-form", "requester", "target",
                       "goal", "find", "ask", "score", "openers", "send", "owners", "fit", "opener-cards",
                       "request-state", "status"):
        assert f'id="{element_id}"' in html, element_id
    assert "uncalibrated fit" in html
    assert "Recorded run" in html or "Recorded run" in _read("app.js")


def test_style_tokens_and_no_external_fonts():
    css = _read("style.css")
    for token in ("--paper", "--ink", "--graphite", "--olive", "--muted", "--rule"):
        assert token in css, token
    assert "ui-monospace" in css
    assert "prefers-reduced-motion" in css
    assert not re.search(r"@import|@font-face|url\(\s*['\"]?https?:", css)
    for name in ("index.html", "owner.html"):
        assert not re.search(r'<link[^>]+href="https?:', _read(name))


def test_owner_page_shares_the_style():
    html = _read("owner.html")
    assert 'href="/static/style.css"' in html
    assert re.search(r"<h1[^>]*>", html)
