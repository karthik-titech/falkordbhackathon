RISK: standard
BUILDER: sol
SCOPE: warmopen/static
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py, tests/test_ptc4b_view_scope.py, tests/test_ptc4c_replay_scope.py, tests/test_ptc4d_replay_all_authenticated.py, tests/test_ptc7_split_screen.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the whole stage demo runs on one page: the requester view on the left and an owner panel on the right, labeled as the owner's phone, that lists pending requests and approves reachability and reveal through the same grant API. No second browser is needed.

INTENT ANCHOR
The audience sees two different people act: the requester asks on the left, the owner consents on the right, and the path lights up only after the right side approves.

CONTEXT
- Karthik 2026-10-24: no Daytona (local Docker FalkorDB now); "single page" = split screen, owner panel on the right labeled as the owner's phone.
- Slide-style tokens and rules from ptc3e bind (paper, ink, graphite, olive, muted, rule; heavy grotesk headline; mono labels; no cards or shadows; textContent only; no external assets). The step strip stays at the bottom of the left side.
- The standalone /owner page (owner.html, owner.js) stays unchanged; earlier frozen tests and replay recordings use it.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 1280 px projector: left column about 68%, right panel about 32% with a thin ink rule between. Under 900 px the panel stacks below the requester view (no horizontal overflow at 390 px, ptc3d).
- Q1 The panel's owner picker lists consented attendees except the current requester; default to the first owner the broker reported as no_consent or reachable.

WHAT EXISTS
- warmopen/static/index.html: requester layout (ptc3e), no owner UI.
- warmopen/static/owner.js: pending poll, Approve reachability / Approve reveal, token in sessionStorage.
- warmopen/static/app.js: requester flow, step strip, timeline polling.
- warmopen/app.py: GET /api/owner/<owner>/pending (X-Owner-Token), POST /api/grants.

TASKS
T1. index.html: add <aside id="owner-panel" aria-label="Owner's phone: approvals"> to the right of the requester view, with a small mono label "OWNER'S PHONE", an owner picker (select id "panel-owner"), a password field (id "panel-token"), a button (id "panel-open") "Open approvals", and a list (id "panel-pending"). Styled like a phone screen in the slide palette: thin ink outline, no shadow, no rounded-card kit (a single modest radius on the phone frame only is allowed).
T2. app.js: panel logic reusing the owner flow: poll GET /api/owner/<owner>/pending every 2 seconds with X-Owner-Token from the panel; per row show "<requester_name> -> <target_name>", the goal in plain words, and two buttons "Approve reachability" and "Approve reveal" that POST /api/grants; show granted state; tokens kept per owner in sessionStorage only; never echo a token. After a grant, nudge the requester side ("Owner approved. Press Ask owners again.").
T3. style.css: #owner-panel layout (two columns at >= 900 px; stacked below the requester view under 900 px); page has no horizontal overflow at 390 px.

FROZEN CONTRACT
tests/test_ptc7_split_screen.py (PROTECTED; 3 of 5 FAIL now), plus every earlier frozen file.

DONE-GATE
- (T1-T3) `python3 -m pytest -q tests` all green against a live FalkorDB (local Docker gate).
- (T1-T3) Gate seat: Firefox walk-through of the full loop on one page at 1280 px; phone check scrollWidth <= 390.
- Every task T1-T3 reported done or explicitly not done.

CONSTRAINTS: work only inside warmopen/static. No git. No network. Do not edit tests/. Print files changed and deviations.

C-ENV. Laptop tree, stdlib only; do not install anything. `python3 -m pytest -q tests/test_ptc7_split_screen.py tests/test_ptc3e_slide_style.py` runs locally without FalkorDB. The gate seat runs the full suite in the local Docker runner.
