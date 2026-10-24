RISK: mechanical
BUILDER: sol
SCOPE: warmopen/static
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py, tests/test_ptc4b_view_scope.py, tests/test_ptc4c_replay_scope.py, tests/test_ptc4d_replay_all_authenticated.py, tests/test_ptc7_split_screen.py, tests/test_ptc7c_product_name.py
FORBID: git, env-keys, deps

GOAL
After this chunk, no visible UI text says "the app"; the product name is one constant PRODUCT_NAME = "Name to come" in warmopen/static/brand.js that sets both page titles and the header labels, so Karthik's final name is a one-line change.

INTENT ANCHOR
Renaming the product before the demo takes one edit.

CONTEXT
- Karthik 2026-10-24: do not call the product the app; he will pick a name.
- Static rules from ptc3e bind (no external assets; textContent only).

ASSUMPTIONS AND OPEN QUESTIONS
- A1 Internal identifiers (package warmopen, sessionStorage keys, WARMOPEN_* env vars) are invisible and stay.
- Q1 None.

WHAT EXISTS
- warmopen/static/index.html:6 and warmopen/static/index.html:14, warmopen/static/owner.html:6 and warmopen/static/owner.html:12 hard-code "the app" / "WARM OPEN · FALKORDB".

TASKS
T1. Add warmopen/static/brand.js with `const PRODUCT_NAME = "Name to come";` loaded first by index.html and owner.html (`<script src="/static/brand.js"></script>`). Header label element id "product-name" shows `${PRODUCT_NAME} · FalkorDB` (uppercase via CSS as today). document.title is set from PRODUCT_NAME in app.js ("<name>") and owner.js ("Owner approvals · <name>"). Static <title> fallback text "Name to come".

FROZEN CONTRACT
tests/test_ptc7c_product_name.py (PROTECTED), plus every earlier frozen file.

DONE-GATE
- (T1) `python3 -m pytest -q tests` all green against a live FalkorDB (local Docker gate).
- Task T1 reported done or explicitly not done.

CONSTRAINTS: work only inside warmopen/static. No git. No network. Do not edit tests/. Print files changed.

C-ENV. Laptop tree, stdlib only; do not install anything.
