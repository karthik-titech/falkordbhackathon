RISK: mechanical
BUILDER: sol
SCOPE: warmopen/static
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the UI shows conference display names ("AI Engineer World's Fair 2026", "GitHub Universe 2026") instead of seed ids ("aie_worldsfair_2026", "github_universe_2026") wherever it shows a conference, including the subline and the speaker filter.

INTENT ANCHOR
The projector never shows a database id.

CONTEXT
- Gate-seat Firefox run 2026-10-24: subline read "... · AIE_WORLDSFAIR_2026".
- Seed conference ids: aie_worldsfair_2026, github_universe_2026 (data prep). The test fixture uses "aie" and "ghu"; unknown ids fall back to the id itself.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 A fixed map in app.js is enough; no API change.
- Q1 None.

WHAT EXISTS
- warmopen/static/app.js:81 subline joins talk?.conference raw.
- warmopen/static/app.js:170 speaker filter matches on raw conference ids.

TASKS
T1. Add a CONFERENCE_NAMES map in app.js {aie_worldsfair_2026: "AI Engineer World's Fair 2026", github_universe_2026: "GitHub Universe 2026"} and a helper that returns the name or the id. Use it in the subline (app.js:81) and include both id and name in the filter haystack (app.js:170).

FROZEN CONTRACT
tests/test_ptc3f_conference_names.py (PROTECTED; FAILS now), plus every earlier frozen file.

DONE-GATE
- (T1) `python3 -m pytest -q tests` all green against a live FalkorDB (61 tests).
- (T1) `grep -rniE "innerHTML|probability" warmopen/static` returns nothing.
- Task T1 reported done or explicitly not done.

CONSTRAINTS: work only inside warmopen/static. No git. No network. Do not edit tests/. Print files changed.

C-ENV. Laptop tree, stdlib only; `python3 -m pytest -q tests/test_ptc3f_conference_names.py tests/test_ptc3e_slide_style.py` runs without FalkorDB. The gate seat runs the full suite in Daytona.
