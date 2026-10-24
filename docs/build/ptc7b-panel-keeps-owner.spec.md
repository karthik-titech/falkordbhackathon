RISK: mechanical
BUILDER: sol
SCOPE: warmopen/static
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py, tests/test_ptc4b_view_scope.py, tests/test_ptc4c_replay_scope.py, tests/test_ptc4d_replay_all_authenticated.py, tests/test_ptc7_split_screen.py
FORBID: git, env-keys, deps

GOAL
After this chunk, pressing "Ask owners" again never switches or resets the owner panel while an approval session is open, so the presenter approves reachability and then reveal for the same owner without reopening the panel.

INTENT ANCHOR
On stage: open Owner B's phone once, approve reachability, press Ask owners, approve reveal, all without touching the panel's owner or token.

CONTEXT
- Gate-seat Firefox walk-through 2026-10-24 (single page): after the second Ask owners, app.js:329 calls panelOwners(<first owner with no_consent or reachable>), which picks Owner A, changes the select, calls restorePanelToken -> resetPanel and empties #panel-pending.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 Auto-selecting an owner is still helpful before any session is open.
- Q1 None.

WHAT EXISTS
- warmopen/static/app.js:181-189 panelOwners(preferred); warmopen/static/app.js:329 caller after Ask owners; warmopen/static/app.js:170 resetPanel; warmopen/static/app.js:176 restorePanelToken.

TASKS
T1. panelOwners: when panelSession is open (an owner's approvals are showing), keep the current owner selected and do not call restorePanelToken or resetPanel; only refresh the option list (keeping the selection). When no session is open, keep today's preferred-owner behavior. A requester change (different requester) still resets the panel.

FROZEN CONTRACT
No new frozen test (browser behavior; judged by the gate seat's Firefox walk-through). Every earlier frozen file stays green.

DONE-GATE
- (T1) `python3 -m pytest -q tests` all green against a live FalkorDB (local Docker gate).
- (T1) Gate seat: single-page Firefox walk-through completes (approve reachability, Ask owners again, approve reveal on the same open panel, reveal, score, openers).
- Task T1 reported done or explicitly not done.

CONSTRAINTS: work only inside warmopen/static. No git. No network. Do not edit tests/. Print files changed.

C-ENV. Laptop tree, stdlib only; do not install anything.
