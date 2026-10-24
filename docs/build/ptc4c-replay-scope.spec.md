RISK: crypto          # authorization fix in recording and replay
BUILDER: sol
SCOPE: warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py, tests/test_ptc4b_view_scope.py, tests/test_ptc4c_replay_scope.py
FORBID: git, env-keys, deps

GOAL
After this chunk, a recorded response that was computed with the requester's own meeting memory is served in replay only to a caller presenting the same requester token; recordings store only the token's sha256, never the token.

INTENT ANCHOR
The offline fallback works for the presenter and reveals nothing about their meetings to anyone else.

CONTEXT
- ptc3 C1 binds: replay imports nothing outside the standard library; store may be None in recorded mode.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 hashlib (stdlib) computes sha256 of the UTF-8 token in replay; no FalkorDB access is needed to check it.
- Q1 None.

WHAT EXISTS
- warmopen/app.py: own_allowed (ptc4b), recording write, _Replay matching, sticky GET /api/requests/<id>.

TASKS
T1. Recording: when the live call used own memory (own_allowed True for that call, including request creation, request view, score, openers), add "auth_sha256": sha256(token) to the recording record. Never write the raw token or headers.
T2. Replay: a recording with auth_sha256 matches only if the replay request carries X-Owner-Token whose sha256 equals it; otherwise it is skipped as if absent (404 {"error": "not in recording", "mode": "recorded"} when nothing else matches). The sticky request view applies the same check on every serve. Recordings without auth_sha256 behave as before.
T3. RUNBOOK: one line under the fallback section: type your requester token on the replay laptop to replay memory-aware steps; recordings contain only a hash of it.

FROZEN CONTRACT
tests/test_ptc4c_replay_scope.py (PROTECTED; 2 of 3 FAIL now), plus every earlier frozen file.

DONE-GATE
- (T1-T2) `python3 -S -m scripts.check_offline` still passes (replay stdlib-only).
- Every task T1-T3 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit tests/. Print files changed and deviations.

C-ENV. Laptop tree, stdlib only; do not install anything. The gate seat runs the full suite in the local Docker runner.
