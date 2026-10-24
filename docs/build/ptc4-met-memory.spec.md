RISK: crypto          # writes to a private graph under an owner token; private edges join path search (authorization tier)
BUILDER: sol
SCOPE: warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py
FORBID: git, env-keys, deps

GOAL
After this chunk, a requester can log "I met <person>" into their own private graph, and the next Find a path uses that meeting as a warm first hop, so a new route appears live. Nothing about the meeting reaches the shared event graph or any other person's search.

INTENT ANCHOR
On stage: no route to Achin Gupta; log "met Divya Mahajan at the expo"; Find a path again; a 2-hop route appears (me -met-> Divya -co_speaker-> Achin), because the graph changed.

CONTEXT
- The requester is a consenting attendee with an OwnerCredential (fixture: me / tok-me). Their private graph is store.private(requester).

ASSUMPTIONS AND OPEN QUESTIONS
- A1 A meeting names an existing public Person (speaker or attendee) in the event graph; this flow never creates new private-only people.
- A2 Meeting edges are used only by the requester who logged them, only as the first hop of their own path search.
- Q1 Category is always "met" in v1; features {"met_today": True}; tie from ties.tie_strength.

WHAT EXISTS
- warmopen/paths.py:8-65 public_paths builds adjacency from event-graph warm links only (coauthor, shared_work, co_speaker) and runs a bounded BFS from the requester.
- warmopen/consent.py:21-33 _authenticate(store, owner, token) checks the hashed token.
- warmopen/seed.py writes private Person nodes and KNOWS edges with {category, strength, strength_source, evidence_id}.
- warmopen/app.py:75 _live routes API calls; error mapping 409/403/404/400.
- warmopen/static/index.html, app.js, owner.js (slide style, ptc3e).

TASKS
T1. warmopen/memory.py: log_meeting(store, requester, requester_token, person, request_id=None) -> {"requester","person","category":"met","tie"}. Under store.lock: authenticate the requester with consent._authenticate (PermissionError on a bad or missing token); person must be an existing event-graph Person, not the requester, else ValueError (an id that exists only in some private graph is "unknown", ValueError). MERGE the Person (id, name copied from the event graph) and a KNOWS edge requester->person in the requester's private graph with category "met", strength and strength_source from ties.tie_strength({"met_today": True}), evidence_id null. Idempotent. If request_id is given and belongs to this requester, log ("seeker","meeting_logged"). Write nothing to the event graph otherwise.
T2. paths.public_paths: add the requester's own private KNOWS edges (requester -> X, X an event-graph Person) as first-hop links {"from","to","category","evidence_id": None}. They are never used after the first hop, never for any other requester, and never read from another person's private graph. Route ordering and route_id numbering unchanged. Existing frozen behavior (topic overlap never a hop; ptc1 and ptc2 tests) stays green.
T3. app.py: POST /api/meetings {requester, person, request_id?} with header X-Owner-Token -> log_meeting result plus "mode"; errors via the existing mapping; the token is never echoed. POST /api/requests and GET /api/requests/<id> presentation payloads include names for any person on a route (people map) as today.
T4. UI (requester page, slide style): a compact "Log a meeting" row under the path: person picker (people and speakers, client-side filter), "Your token" password field (kept in sessionStorage), button "Log meeting". On success show "Logged: you met <name>. Find a path again to use it." and re-run Find a path for the current target. Path view labels a "met" span "met · your graph". Use textContent only.

FROZEN CONTRACT
tests/test_ptc4_met_memory.py (PROTECTED; 6 cases FAIL now), plus every earlier frozen file.

DONE-GATE
- (T1-T4) `python3 -m pytest -q tests` all green against a live FalkorDB (67 tests).
- (T1-T3) The event graph dump is byte-identical before and after log_meeting (frozen test).
- Every task T1-T4 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit tests/. Print files changed and deviations.


ASTRA PLAN REVIEW ADDITIONS (2026-10-24; accepted by the spec author; binding)
Decisions: own memory is opt-in and token-bound; logging a meeting writes nothing shared; meetings never overwrite owner edges.
C2. requests.create_request(store, requester, target, goal, requester_token=None): when requester_token authenticates the requester (consent._authenticate), set Request.use_own_memory = true; a bad token raises PermissionError; None leaves it false. Every caller that computes routes for a request (app request views, features, scoring introducer resolution) passes include_own=request.use_own_memory. POST /api/requests reads X-Owner-Token and passes it as requester_token.
C3. T1 amended: log_meeting takes no request_id and writes NO AgentEvent (event graph byte-identical). The meeting is its own relationship: MERGE (a)-[r:KNOWS {category: 'met'}]->(b) SET r.strength, r.strength_source, r.evidence_id = null; existing non-"met" KNOWS edges are never modified.
C4. log_meeting accepts only seed-public people (event-graph Person with kind set); people copied by a broker reveal (no kind) raise ValueError.
C5. A2 amended: a logged meeting is part of that person's private graph. Other requesters can benefit from it only through the broker with that owner's reachability and reveal grants (existing ptc1 flow), never through public_paths.
C6. HTTP errors from /api/meetings and /api/requests never include the presented token value.
C7. UI: the requester page keeps "Your token" in sessionStorage per requester id and sends X-Owner-Token on Find a path and Log meeting when present; Find a path shows "Using your logged meetings" when the request has use_own_memory.
C8. Known limit (keep_plan): route ids are positions; a concurrent meeting during scoring can renumber routes (single presenter, accepted).
