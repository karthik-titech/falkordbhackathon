RISK: crypto          # authorization fix: meeting memory exposure through request ids
BUILDER: sol
SCOPE: warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py, tests/test_ptc4b_view_scope.py
FORBID: git, env-keys, deps

GOAL
After this chunk, holding a request id never reveals the requester's logged meetings. Every HTTP call that computes routes, scores, or writes openers uses the requester's own meeting edges only when that same call carries the requester's valid X-Owner-Token and the request has use_own_memory.

INTENT ANCHOR
Owner B sees your request id on the approval list, but cannot learn whom you met.

CONTEXT
- ptc1 C2 (bearer request ids) still holds for everything except requester-private memory.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 Library functions keep include_own (default False); authorization is decided in app.py per call.
- Q1 None.

WHAT EXISTS
- warmopen/app.py:65 request view helper, warmopen/app.py:143 score, warmopen/app.py:152 openers, warmopen/app.py:161 request detail: pass include_own=request.use_own_memory without checking the caller.
- warmopen/features.py, warmopen/scoring.py read use_own_memory from the request.
- warmopen/static/app.js sends X-Owner-Token on Find a path and Log meeting only.

TASKS
T1. app.py: a helper own_allowed(store, request, token) returns True only if request.use_own_memory is true AND consent._authenticate(store, request.requester, token) succeeds (a missing or wrong token returns False; it is not an error on these read paths). Use it for POST /api/requests (response routes), GET /api/requests/<id>, POST /api/requests/<id>/score and /openers, and any other route-computing endpoint.
T2. features.extract_features, scoring.score_fit and openers.generate_openers take an explicit include_own argument (default False) and pass it down; they no longer read use_own_memory on their own. Frozen ptc2/ptc6 library-level behavior holds (ptc6 A: met_before only when include_own is True and the request has use_own_memory).
T3. UI: app.js sends X-Owner-Token (the requester token kept in sessionStorage) on request detail polling, score and openers calls when present.

FROZEN CONTRACT
tests/test_ptc4b_view_scope.py (PROTECTED; 2 of 3 FAIL now), plus every earlier frozen file.

DONE-GATE
- (T3) `grep -rniE "innerHTML|localStorage|probability" warmopen/static` returns nothing.
- Every task T1-T3 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit tests/. Print files changed and deviations.

C-ENV. Laptop tree, stdlib only; do not install anything. The gate seat runs the full suite in the local Docker runner.
