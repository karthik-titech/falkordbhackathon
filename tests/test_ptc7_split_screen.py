"""ptc7 frozen contract: one-page split screen for the stage demo.

Source: Karthik 2026-10-24 ("not Daytona, single page"; chose "split screen,
one page"): requester view on the left, an owner panel on the right labeled as
the owner's phone, so the consent story stays visible without a second
browser. The standalone /owner page stays (earlier frozen tests use it).
Layout is judged by the gate seat in Firefox; this file pins structure.
"""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "warmopen" / "static"


def _read(name):
    return (STATIC / name).read_text(encoding="utf-8")


def test_index_has_an_owner_panel_labeled_as_a_phone():
    html = _read("index.html")
    panel = re.search(r'<aside[^>]*id="owner-panel"[^>]*>', html)
    assert panel, 'index.html needs <aside id="owner-panel">'
    assert re.search(r'aria-label="[^"]*phone[^"]*"', panel.group(0), re.I)
    for element_id in ("panel-owner", "panel-token", "panel-open", "panel-pending"):
        assert f'id="{element_id}"' in html, element_id


def test_panel_uses_the_same_grant_api_with_the_owner_token_header():
    js = _read("app.js")
    assert "/api/grants" in js
    assert "X-Owner-Token" in js
    assert "Approve reachability" in js and "Approve reveal" in js
    assert re.search(r"/api/owner/\$\{[^}]+\}/pending|/api/owner/\"\s*\+", js)


def test_panel_token_stays_in_the_tab_and_never_in_markup():
    js = _read("app.js")
    assert "sessionStorage" in js
    assert "localStorage" not in js
    assert 'value="tok' not in _read("index.html")


def test_split_layout_and_stacking():
    css = _read("style.css")
    assert "#owner-panel" in css
    assert re.search(r"@media[^{]*max-width", css)


def test_standalone_owner_page_still_exists():
    assert (STATIC / "owner.html").is_file() and (STATIC / "owner.js").is_file()
