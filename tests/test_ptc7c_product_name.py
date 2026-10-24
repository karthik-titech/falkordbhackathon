"""ptc7c frozen contract: the product name lives in one constant.

Source: Karthik 2026-10-24: "don't call it warm-open; I'll come up with a
different name." Visible UI text must not say "Warm Open"; one constant in
warmopen/static/brand.js ("Name to come" until Karthik picks) feeds the page
titles and header labels on both pages. Internal identifiers (the warmopen
package, storage keys, env vars) are not visible and may stay.
"""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "warmopen" / "static"


def test_no_visible_old_name():
    for name in ("index.html", "owner.html", "app.js", "owner.js", "style.css"):
        text = (STATIC / name).read_text(encoding="utf-8")
        assert not re.search(r"warm[ \-]open", text, re.I), name


def test_one_constant_feeds_both_pages():
    brand = (STATIC / "brand.js").read_text(encoding="utf-8")
    assert re.search(r'PRODUCT_NAME\s*=\s*"Name to come"', brand)
    for page in ("index.html", "owner.html"):
        html = (STATIC / page).read_text(encoding="utf-8")
        assert '<script src="/static/brand.js"' in html, page
        assert 'id="product-name"' in html, page
    js = (STATIC / "app.js").read_text(encoding="utf-8") + (STATIC / "owner.js").read_text(encoding="utf-8")
    assert js.count("PRODUCT_NAME") >= 2
