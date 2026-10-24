RISK: crypto          # authorization fix in recording and replay (class closure)
BUILDER: sol
SCOPE: warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py, tests/test_ptc4b_view_scope.py, tests/test_ptc4c_replay_scope.py, tests/test_ptc4d_replay_all_authenticated.py
FORBID: git, env-keys, deps

GOAL
After this chunk, every recorded response for a call whose X-Owner-Token authenticated (requester or owner, any endpoint) carries auth_sha256 = sha256(token), and replay serves it only to a caller presenting the same token. Unauthenticated calls record and replay as before.

INTENT ANCHOR
A recording is safe to keep on the demo laptop: it replays private answers only to the person who made them.

CONTEXT
- ptc3 C1 binds: replay is stdlib-only and needs no store.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 "Authenticated" means the live handler successfully ran consent._authenticate (or own_allowed True) for that call's token; a call that failed auth (403) records no auth_sha256 and replays its 403 to anyone, as before.
- Q1 None.

WHAT EXISTS
- warmopen/app.py: ptc4c tags memory-aware responses via own_allowed; meetings, owner pending and grants are not tagged.

TASKS
T1. Live handler: track per call whether a token authenticated (requester or owner); if so, the recording record gets auth_sha256 = sha256(UTF-8 token). Raw tokens and headers are never written.
T2. Replay: any tagged recording (from ptc4c or T1) matches only when sha256(caller X-Owner-Token) equals auth_sha256; the hash itself presented as a token does not match. Sticky request view keeps the check.
T3. RUNBOOK: the fallback section says to enter the requester token and each owner token in replay mode for those steps.

FROZEN CONTRACT
tests/test_ptc4d_replay_all_authenticated.py (PROTECTED; 2 FAIL now), plus every earlier frozen file.

DONE-GATE
- Every task T1-T3 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit tests/. Print files changed and deviations.

C-ENV. Laptop tree, stdlib only; do not install anything. The gate seat runs the full suite in the local Docker runner.
