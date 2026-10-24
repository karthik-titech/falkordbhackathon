RISK: mechanical
BUILDER: sol
SCOPE: warmopen/static
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the requester page has no horizontal page overflow at 390 px viewport width, as ptc3 T4 requires; the path view scales down (or scrolls inside its own box) instead of widening the page.

INTENT ANCHOR
Someone opening the demo link on a phone sees every card fully, with the path drawn inside the card.

CONTEXT
- Gate-seat measurement 2026-10-23 (Firefox 158, page in a 390 px iframe): requester page document scrollWidth 848. Elements past 390 px: the layout DIV (848), SECTION.panel (848), DIV.section-title (831), SPAN#request-state (831), DIV.path-scroll (831), svg#path-view (831). The owner page measures 390 (no overflow).
- Likely cause: a grid or flex child with the default min-width:auto around a fixed-width SVG. Fix in CSS (min-width: 0 on the grid children, SVG width 100% with its viewBox, or overflow-x: auto confined to .path-scroll). Builder's choice.
- 1280 px projector layout must not change visibly.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 CSS-only change is enough; if app.js sets a fixed SVG width attribute, switching to viewBox plus width 100% in app.js is in scope.
- Q1 None.

WHAT EXISTS
- warmopen/static/style.css: page layout, panels, .path-scroll.
- warmopen/static/app.js draw(): builds svg#path-view.

TASKS
T1. Make the requester page fit 390 px with no horizontal page overflow: no element's right edge past the viewport except inside an element that scrolls on its own (overflow-x auto). The path SVG stays readable (labels not clipped at 1280 px).

FROZEN CONTRACT
No new frozen test (layout is measured by the gate seat in a real browser). Every earlier frozen file stays green.

DONE-GATE
- (T1) `python3 -m pytest -q tests` all green against a live FalkorDB (54 tests).
- (T1) Gate seat: headless Firefox phone check reports requester page scrollWidth <= 390 and the 1280 px walk-through screenshots match the current layout.
- (T1) `grep -rniE "<script[^>]+src=\"https?:|<link[^>]+href=\"https?:|innerHTML" warmopen/static` returns nothing.
- Task T1 reported done or explicitly not done.

CONSTRAINTS: work only inside warmopen/static. No git. No network. Do not edit tests/. Print files changed.

C-ENV. Build environment (spec author, 2026-10-23): laptop tree, no FalkorDB, stdlib only. Do not install anything. The gate seat runs pytest in Daytona and the browser checks with headless Firefox.
