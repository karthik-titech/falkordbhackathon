RISK: standard
BUILDER: sol
SCOPE: warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the demo reads well and stays responsive: template openers are clean sentences, the agent timeline shows a no-consent answer and the send step, and a slow JEV or LLM call no longer blocks other HTTP requests.

INTENT ANCHOR
On stage, the owner page keeps polling while scoring runs, and every agent handoff, including a refusal, appears on the timeline.

CONTEXT
- Parent specs ptc1, ptc2, ptc3 still bind (stdlib only; no external assets; agents seeker, broker, scorer, writer; replay stdlib-only; recording counter under a lock, ptc3 C8).

ASSUMPTIONS AND OPEN QUESTIONS
- A1 Store operations already serialize on GraphStore.lock; scoring and openers call JEV and the LLM outside that lock (warmopen/scoring.py:136, warmopen/openers.py:44).
- Q1 Template wording is the builder's choice within T1's rules; state the three templates in the report.

WHAT EXISTS
- warmopen/openers.py:17-24 _template returns "I read: " + claim + " What would you add?".
- warmopen/broker.py:26-27 reachability returns no_consent without logging reachability_answered.
- warmopen/app.py send endpoint advances state without an AgentEvent.
- warmopen/app.py:218 `with lock:` wraps body parsing, the live call (including JEV/LLM network calls) and the recording write.
- tests/test_ptc3b_polish.py: 3 cases, all FAIL now.

TASKS
T1. Template openers. Each template cue is one or two complete sentences: starts with a capital letter, ends with ".", "?" or "!", has no double spaces, and never runs a claim into the next sentence without punctuation (strip trailing punctuation from the claim, then add a period before the follow-up question). Keep <= 280 characters, the cited claim text included, and keep the {text, evidence_id, url, source} keys. Generic (no evidence) templates follow the same rules.
T2. Timeline. broker.reachability logs ("broker","reachability_answered") for every outcome, including no_consent and unavailable, exactly once per call. The send endpoint (both approved->requested and draft->requested) logs ("seeker","intro_requested") after the state change.
T3. Server lock scope. In app.py, hold the server lock only to consume a replay recording and to assign the recording counter and write the recording file. Live calls run outside the server lock (the store lock protects graph state). Recording file order must still match response order per counter (C8).
    GATE G1: the frozen test test_slow_scoring_does_not_block_other_requests passes.

FROZEN CONTRACT
tests/test_ptc3b_polish.py (PROTECTED), plus every earlier frozen file.

DONE-GATE
- (T1-T3) `python3 -m pytest -q tests` all green against a live FalkorDB (50 tests); GATE G1 holds.
- Every task T1-T3 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit any file under tests/. Print files changed and deviations.

C-ENV. Build environment (spec author, 2026-10-23): the builder tree is ~/repos/warm-open on the laptop with NO FalkorDB and NO packages beyond the standard library. Do not install anything. Verify with `python3 -m compileall -q warmopen` and by reading the frozen tests. The gate seat syncs the tree to Daytona sandbox warm-open-ptc and runs the DONE-GATE pytest there.
