RISK: standard
BUILDER: sol
SCOPE: warmopen scripts
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py
FORBID: git, env-keys, deps

GOAL
After this chunk, build_payload sends JEV the request shape that a live call confirmed: each choice question has "type", "instructions" and a "criteria" map of {choice: description}, and no "choices" key. The probe script uses the same shape.

INTENT ANCHOR
The fit score on stage comes from a real JEV call that the API accepts, still fed only abstract numbers and fixed labels.

CONTEXT
- Live probe 2026-10-23 (gate seat, model jev-1.14.0): {"type":"choice","choices":[...],"criteria":"<string>"} returns HTTP 422 "questions.fit.choice.criteria: Input should be a valid dictionary". {"type":"choice","instructions":"...","criteria":{"high":"...","low":"..."}} returns 200 with answers.fit {type, choice, confidence, probabilities:{high, low}}.
- Parent spec: ptc2-score-openers.spec.txt; all constraints still bind (abstract features only; label "uncalibrated fit"; no "probability" output key; stdlib only).

ASSUMPTIONS AND OPEN QUESTIONS
- A1 Description text per choice is fixed strings written in code per goal. It must not contain names, ids, URLs or claims.
- Q1 Introducer descriptions: one fixed string per choice kind (public route, revealed route, APPROACH_DIRECTLY, INSUFFICIENT_EVIDENCE); route ids are the map keys. Builder may add the route's hop count as a number in the text.

WHAT EXISTS
- warmopen/scoring.py:44-60 build_payload emits "choices" lists and string "criteria" from _CRITERIA (warmopen/scoring.py:16-21).
- scripts/jev_probe.py:19-26 sends the rejected shape.
- tests/test_ptc2b_jev_shape.py: 1 of 2 cases FAILS now (choices key present).

TASKS
T1. scoring.build_payload: fit question becomes {"type":"choice","instructions":<goal instruction>,"criteria":{"high":...,"medium":...,"low":...,"INSUFFICIENT_EVIDENCE":...}} in that key order, with per-goal descriptions (invest: first meeting; sales: 20-minute call). Introducer question becomes {"type":"choice","instructions":...,"criteria":{<each choice in the given order>: description}}. Remove every "choices" key. Keep the ValueError guard on non-abstract features and the fixed choice list.
T2. score_fit validation unchanged in behavior; confirm it reads answers.<q>.choice, confidence and probabilities as the live response returns them (probabilities is a map keyed by choice).
T3. scripts/jev_probe.py: send the confirmed shape (criteria map, no choices key).
    GATE G1: `grep -n '"choices"' warmopen/scoring.py scripts/jev_probe.py` returns nothing.

FROZEN CONTRACT
tests/test_ptc2b_jev_shape.py (PROTECTED), plus every earlier frozen file.

DONE-GATE
- (T1-T3) `python3 -m pytest -q tests` all green against a live FalkorDB (41 tests); GATE G1 holds.
- (T1) `python3 -m compileall -q warmopen scripts` clean.
- Every task T1-T3 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit any file under tests/. Print files changed and deviations.

C-ENV. Build environment (spec author, 2026-10-23): the builder tree is ~/repos/warm-open on the laptop with NO FalkorDB and NO packages beyond the standard library. Do not install anything. Verify with `python3 -m compileall -q warmopen` and by reading the frozen tests. The gate seat syncs the tree to Daytona sandbox warm-open-ptc and runs the DONE-GATE pytest there, and runs the live JEV probe from the laptop.
