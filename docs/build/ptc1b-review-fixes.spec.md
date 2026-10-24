RISK: crypto          # fixes to consent grants and the broker (authorization tier)
BUILDER: sol
SCOPE: README.md .gitignore warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py
FORBID: git, env-keys, deps

GOAL

INTENT ANCHOR
A requester learns nothing from a private graph unless a live, unrevoked, unexpired grant exists at the moment the broker checks it, and a reveal is all-or-nothing.

CONTEXT
- Hashing a stored login token is ordinary credential storage, not a grant mechanism. Grants stay plain records (parent spec A9 is unchanged).

ASSUMPTIONS AND OPEN QUESTIONS
- A1 The server (ptc3) holds exactly one GraphStore in one process; the threading.Lock is the only concurrency guard (Astra P2, accepted as a documented limit).
- A2 Seed reload with reclassified evidence reconciles in place (removes the public copy); it does not require drop_all.
- Q1 Token hash: sha256 hex of the UTF-8 token, compared with secrets.compare_digest on the hex digests. A salt is not required for demo tokens; state the choice in the report.

WHAT EXISTS
- warmopen/broker.py:17-25 reachability samples `at = _time(now)` before `with store.lock` and passes it to has_grant.
- warmopen/broker.py:62-105 reveal writes revealed_offer_id and revealed_route (lines ~97-101), then calls _advance_locked separately (line ~102).
- warmopen/seed.py:58-73 computes `excluded` evidence but never removes an existing event Evidence node or SUPPORTED_BY edge for an id that is now excluded.
- warmopen/seed.py:~135-138 writes OwnerCredential {id, token} with the plain token; warmopen/consent.py:21-29 _authenticate compares against it.
- warmopen/graphstore.py:26-27 private(owner_id) concatenates the id into a graph name without validation.
- Frozen: tests/test_ptc1b_fixes.py (10 cases, all FAIL now); tests/test_ptc1_core.py (15, pass now, must stay green).

TASKS
T1. Clock at check time. In broker.reachability, when `now` is None, read the clock inside the lock immediately before the grant check (and use that value for the Ask record). An explicit `now` passes through unchanged. Apply the same rule to broker.reveal's grant check.
    GATE G1: `grep -n "_time(now)" warmopen/broker.py` shows no call placed before its function's `with store.lock:` line.

T2. Atomic reveal. The route snapshot (revealed_offer_id, revealed_route) and the state change awaiting_approval -> approved are written in one Cypher statement on the Request node, conditioned on `r.state = 'awaiting_approval'` and `r.revealed_offer_id IS NULL`. If the statement matches no row, raise StateError and write nothing. The broker must not call _advance_locked for this transition (so a failure there cannot split the write). Copy revealed Person names into the event graph only after the atomic write succeeds. The cached replay path (same offer already revealed) returns the stored route only when the request state is approved or requested. Log ("broker","route_revealed") after success.

T3. Reload reconciliation. In load_seed, before writing public evidence, remove from the event graph every Evidence node whose id is now excluded (DETACH DELETE removes its SUPPORTED_BY edges) and clear `evidence_id` on any event relationship that names an excluded id. Repeated loads of the same seed stay idempotent (test_seed_is_idempotent must stay green).

T4. Token hash. OwnerCredential stores `token_sha256` (hex) and never the plain token. _authenticate hashes the presented token and compares digests with secrets.compare_digest. No plain token appears in any graph.

T5. Owner id validation. GraphStore.private(owner_id) raises ValueError unless owner_id matches ^[A-Za-z0-9_-]{1,64}$.


FROZEN CONTRACT
tests/test_ptc1b_fixes.py (PROTECTED), plus tests/conftest.py and tests/test_ptc1_core.py.

DONE-GATE
- (T1-T5) `python3 -m pytest -q tests` all green against a live FalkorDB (15 ptc1 + 10 ptc1b); GATE G1 holds.
- (T1-T6) `python3 -m compileall -q warmopen` clean.
- (T4) `grep -rn "\"token\":" warmopen/seed.py` returns nothing.
- (T6) `grep -n "launch.json" .gitignore` prints a line.
- Every task T1-T6 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git commands. No key material. No network other than FalkorDB. No packages beyond stdlib, falkordb, pytest. Do not edit any file under tests/. Print files changed and every deviation.

C-ENV. Build environment (spec author, 2026-10-23): the builder tree is ~/repos/warm-open on the laptop with NO FalkorDB and NO packages beyond the standard library. Do not install anything. Verify with `python3 -m compileall -q warmopen` and by reading the frozen tests. The gate seat syncs the tree to Daytona sandbox warm-open-ptc (FalkorDB 6.0.1, falkordb client 1.7.1, pytest 9.1.1) and runs the DONE-GATE pytest there; failures return as <tag>b with the output.
