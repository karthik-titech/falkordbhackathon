RISK: standard
BUILDER: sol
SCOPE: warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the stage demo reads cleanly: openers never repeat a claim, the owner page shows names, the fit card explains an abstention in words, and the revealed path visibly connects the requester to the approving owner with a dashed "asked" edge.

INTENT ANCHOR
A judge watching the projector understands every card without reading an id or a reason code.

CONTEXT
- Parent specs still bind: stdlib only, no external assets, no innerHTML with graph strings, UI copy says "uncalibrated fit", never "probability" or "chance"; opener dict keys stay exactly {text, evidence_id, url, source}.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 With fewer than 3 distinct allowed evidence items, the remaining openers are generic templates (evidence_id None, url None, source "template"), not repeats. This amends ptc2 T4 "then reuse if fewer than 3 exist".
- Q1 Visual styling of the dashed edge is the builder's choice; it must use an SVG stroke-dasharray and the label "asked".

WHAT EXISTS
- warmopen/openers.py:63-64 fill loop reuses evidence when fewer than 3 exist.
- warmopen/app.py owner pending items: {request_id, requester, target, goal, reachability_granted, reveal_granted, asked}.
- warmopen/static/owner.js renders "<requester> -> <target>" from ids.
- warmopen/static/app.js:148 renders `Abstained: ${fit.reason}`.
- warmopen/static/app.js draw(): the requester node is drawn but not joined to the route's first person on a revealed route.
- tests/test_ptc3c_demo_polish.py: 4 cases, all FAIL now.

TASKS
T1. Openers: never emit the same evidence id twice. After LLM cues and one template per unused allowed evidence item, fill to 3 with distinct generic templates (no evidence). Generic texts are distinct from each other.
T2. Owner pending items add "requester_name" and "target_name" (Person.name from the event graph). owner.js shows "<requester_name> -> <target_name>" with the goal shown as "Invest" or "Product sales proposal".
T3. Fit card: when abstained, show exactly one of: insufficient_evidence -> "Not enough public evidence to score."; low_confidence -> "The decision model was not confident enough to score."; jev_unavailable -> "Scoring service unavailable. Showing graph reasons only." Supports, against and would improve still render below. When not abstained, show band, value and confidence as now.
T4. Path view: for a revealed route (first person is not the requester), draw a dashed edge (stroke-dasharray) from the requester node to the route's first person, labeled "asked". Public routes are unchanged.

FROZEN CONTRACT
tests/test_ptc3c_demo_polish.py (PROTECTED), plus every earlier frozen file.

DONE-GATE
- (T1-T4) `python3 -m pytest -q tests` all green against a live FalkorDB (54 tests).
- Every task T1-T4 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit any file under tests/. Print files changed and deviations.

C-ENV. Build environment (spec author, 2026-10-23): the builder tree is ~/repos/warm-open on the laptop with NO FalkorDB and NO packages beyond the standard library. Do not install anything. Verify with `python3 -m compileall -q warmopen` and by reading the frozen tests. The gate seat syncs the tree to Daytona sandbox warm-open-ptc, runs the DONE-GATE pytest there, and re-runs the headless Firefox walk-through.
