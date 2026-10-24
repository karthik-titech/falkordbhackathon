"""ptc3f frozen contract: show conference names, not seed ids, in the UI.

Source: gate-seat Firefox run 2026-10-24 (ptc3e): the subline read
"INVEST · CLOSING KEYNOTE: GARRY TAN · AIE_WORLDSFAIR_2026".
"""
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "warmopen" / "static" / "app.js"


def test_app_maps_conference_ids_to_names():
    js = APP_JS.read_text(encoding="utf-8")
    assert "AI Engineer World's Fair 2026" in js or "AI Engineer World\\'s Fair 2026" in js
    assert "GitHub Universe 2026" in js
    assert "talk?.conference]" not in js
