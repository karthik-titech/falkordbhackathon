RISK: standard
BUILDER: sol
SCOPE: warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py, tests/test_ptc5_who_to_meet.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the requester page opens with "Who should I meet?": four columns, each filled by its own FalkorDB query and showing that query: 1 the mirror, 2 the missing piece, 3 the unexpected connection, 4 the intended target. Picking a person starts the existing warm-path flow for that target.

INTENT ANCHOR
The graph sorts the room: every suggestion has a reason drawn from the graph and the exact Cypher that found it.

CONTEXT
- Karthik 2026-10-24: categories 1-3 from the ChatGPT brainstorm, 4 added by Karthik (angel/VC for invest, sales prospect for sales); idea B "show the Cypher" folded in.
- Builds on ptc4 (warmopen/memory.py log_meeting; requester-own first-hop edges in paths.public_paths).
- Parent specs bind: stdlib + falkordb; no external assets; textContent only; slide-style tokens (ptc3e); "uncalibrated fit" wording; no private names before reveal.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 The requester's Startup gains an optional "seeking" list of topic ids (what they are looking for). seed.py stores it as a Startup property. Placeholder in the demo seed until Karthik's profile arrives.
- A2 Mirror threshold is 1 or more shared topics (the fixture has single-topic profiles); rank by shared-topic count, then name.
- Q1 k = 3 items per column.

WHAT EXISTS
- warmopen/seed.py:5-13 _NODES lists Startup fields (no "seeking" yet).
- warmopen/features.py: topic overlap (INTERESTED_IN and SPEAKS_AT->ABOUT), stage/sector match (PARTNER_AT Fund), category match (WORKS_AT Company.needs).
- warmopen/paths.py public_paths (BFS over warm links plus requester-own first hop, ptc4).
- warmopen/static/index.html, app.js (slide style, step track).

TASKS
T1. seed.py: store Startup.seeking (list of topic ids) when present.
T2. warmopen/meet.py: who_to_meet(store, requester, goal, k=3) -> list of four dicts in order mirror, missing_piece, unexpected, target with keys exactly {id, label, items, cypher, params}; labels "The mirror", "The missing piece", "The unexpected connection", "The intended target". Items {person, name, reason, evidence_id, url}. Rules (event-graph people only, never the requester, each person in at most one category, priority target > missing_piece > mirror > unexpected):
    - target: invest = PARTNER_AT a Fund whose stages contain the requester's startup stage OR whose sectors overlap its sectors; sales = WORKS_AT a Company whose needs contain the startup product_category. evidence_id/url = the Fund or Company evidence (public only). reason states the matched stage, sectors or need.
    - missing_piece: speaks at a Talk ABOUT a topic in startup.seeking and shares no topic with the requester. reason "Speaks on <Topic name>, which you are looking for."
    - mirror: shares 1+ topics (INTERESTED_IN or SPEAKS_AT->ABOUT) with the requester. reason "Also works on <Topic names>."
    - unexpected: shares no topic, is not in another category, and public_paths(requester, person, max_hops=3) is non-empty. reason describes the first route ("via <name> (<category>)", "you met them" for a direct met edge). evidence_id/url from the first evidenced edge or None.
    Each category's "cypher" is the exact query string executed for it (module constants passed to store.query), and "params" the parameters, always including "requester". For unexpected, show the requester-own-edge or warm-link query from paths.py. ValueError for unknown requester or goal.
T3. app.py: GET /api/meet?requester=<id>&goal=invest|sales -> {"items": who_to_meet(...), "mode"}.
T4. UI: section id "meet-view" at the top of the requester page titled "Who should I meet?" with four columns in the slide style (markers: ■ target in olive, ◩ missing piece, ◪ mirror or similar square glyph, □ unexpected; builder may pick glyphs but order on screen is 1 mirror, 2 missing piece, 3 unexpected, 4 intended target). Each item: name, one-line reason, source link when present; clicking selects that person as target and runs Find a path. Each column has a <details> "Show the query" with the Cypher in a monospace block and the params. Refresh after Log meeting and on requester or goal change.

FROZEN CONTRACT
tests/test_ptc5_who_to_meet.py (PROTECTED), plus every earlier frozen file.

DONE-GATE
- (T1-T4) `python3 -m pytest -q tests` all green against a live FalkorDB.
- Every task T1-T4 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit tests/. Print files changed and deviations.

C-ENV. Laptop tree, no FalkorDB, stdlib only; do not install anything. The gate seat runs the full suite in Daytona plus a Firefox walk-through.

AMENDMENT 2026-10-24 (ptc4 Astra plan review carry-over; binding)
What changed: requester-own meeting memory is opt-in and token-bound.
Why: Astra plan review of ptc4 (P1: requester id is caller-controlled on unauthenticated endpoints).
Affected tests: tests/test_ptc5_who_to_meet.py (re-pinned 48d6f6b9).
Reapproval: no
Note: spec author folded an Astra P1 on 2026-10-24; scope unchanged.
C1. who_to_meet(store, requester, goal, k=3, include_own=False): requester-own meeting edges count (unexpected column, via paths.public_paths(..., include_own=True)) only when include_own is True. GET /api/meet sets include_own only when X-Owner-Token authenticates the requester; a bad token is 403; no token means include_own False. Error bodies never echo token values.
