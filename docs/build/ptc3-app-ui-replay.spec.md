RISK: standard
BUILDER: sol
SCOPE: pyproject.toml README.md .gitignore warmopen scripts docs data
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the app runs as one stdlib HTTP server with a JSON API, a requester page, and an owner page (second browser). The requester page shows the lit graph path with evidence per hop, the broker's no-names reachability answers, the uncalibrated fit card, three sourced openers, and a live agent timeline read from AgentEvent nodes. The server can record every API response and replay them, labeled "Recorded run", for a wifi-failure fallback. A CLI loads a seed file and serves.

INTENT ANCHOR
On stage, two browsers drive the whole loop: find the path, ask owners, approve in the second browser, reveal, score, openers, send. The agent timeline shows each handoff read from the graph. If the network fails, a recorded run replays with a visible Recorded run label.

CONTEXT
- Stdlib only on the server (http.server.ThreadingHTTPServer, json, urllib). Frontend is hand-written HTML, CSS and vanilla JS in warmopen/static/. NO external scripts, stylesheets, fonts or CDNs; no npm. The path view is inline SVG drawn by your own JS (simple layered layout: requester left, target right, middle hops between).

ASSUMPTIONS AND OPEN QUESTIONS
- A1 The demo runs from a Daytona preview URL; the laptop runs only browsers (PLAN.md).
- A2 No external web assets; the SVG layout is hand-written JS.
- Q1 Exact visual styling is the builder's choice within the T4 element ids and copy rules.

WHAT EXISTS
- ptc1 + ptc2 packages and frozen tests. Frozen now: tests/test_ptc3_app.py (FAILS now).

TASKS
T1. Request transitions: add draft->requested (direct or public-route intro, no owner approval needed). All other ptc1 transition rules unchanged; ptc1 tests stay green.

T2. warmopen/app.py: make_server(store, host="127.0.0.1", port=0, mode="live", jev=None, llm=None, record_dir=None, recordings_dir=None) -> ThreadingHTTPServer (caller runs serve_forever). jev/llm None means "unavailable" (score abstains with jev_unavailable; openers use templates).
    Every JSON response is an object with key "mode" ("live" or "recorded"); list results go under "items". Errors: ValueError 400, PermissionError 403, unknown request or route 404, StateError 409, body {"error": str, "mode": ...}.
    Endpoints:
      GET  /                          requester page (static/index.html)
      GET  /owner                     owner page (static/owner.html)
      GET  /static/<file>             static assets, no directory traversal (404 on ..)
      GET  /api/targets               items: speakers {id,name,talks:[{title,conference,starts}]}
      GET  /api/people                items: consented attendees {id,name}
      POST /api/requests              {requester,target,goal} -> {request_id,state,routes}
      GET  /api/requests/<id>         {request,routes,revealed_route,events}
      POST /api/requests/<id>/reachability   {owner} -> broker.reachability result fields
      GET  /api/owner/<owner>/pending header X-Owner-Token -> items {request_id,requester,target,goal,reachability_granted,reveal_granted,asked}
      POST /api/grants                header X-Owner-Token, {owner,requester,request_id,scope} -> {grant_id}
      POST /api/requests/<id>/reveal  {owner,offer_id} -> route
      POST /api/requests/<id>/score   -> score_fit output fields
      POST /api/requests/<id>/openers -> items: openers
      POST /api/requests/<id>/send    -> advances approved->requested or draft->requested -> {state}
    The owner token is never echoed in any response.
    GATE G1: grant with a wrong or missing X-Owner-Token returns 403 and creates no Grant.

T3. Record and replay. record_dir set (live mode): append every /api/ response as record_dir/<NNNN>.json {"method","path","request_body","status","body"}, NNNN zero-padded increasing. mode="recorded" with recordings_dir: for each /api/ call serve the next unconsumed recording with the same method and path (in file order), status as recorded, body["mode"]="recorded"; no match -> 404 {"error":"not in recording","mode":"recorded"}. Static pages still served. No store access in recorded mode (store may be None).
    GATE G2: a recorded GET /api/targets replays with mode "recorded" and the recorded items.

T4. Requester page (static/index.html, app.js, style.css): pick requester (people), target (targets), goal (Invest | Product sales proposal); "Find a path" lights the best route in an SVG with id "path-view": nodes labeled by name, edges labeled by category, each edge clickable to its evidence URL; "Ask owners" calls reachability for each other consented attendee and shows rows like "Owner B: reachable, 2 hops, tie 0.74" (no names of hidden people); "Reveal" appears per reachable owner and lights the revealed route; "Score fit" shows a card titled "uncalibrated fit" with band, value, confidence, introducer, supports (with links), against, would improve, or the abstention reason; "Openers" shows 3 cards with source links; "Send intro request" calls send. An agent timeline panel (id "agent-timeline") polls GET /api/requests/<id> every 2 seconds and lists events as "seeker: request_created". A banner element id "mode-banner" with text "Recorded run" is visible only when any response has mode "recorded". Works at 1280 px projector width and at phone width.

T5. Owner page (static/owner.html, owner.js): owner id from ?owner=, token typed once (kept in sessionStorage); polls pending every 2 seconds; per row two buttons "Approve reachability" and "Approve reveal" that call /api/grants; shows granted state.


FROZEN CONTRACT
tests/test_ptc3_app.py (PROTECTED), plus ptc1 and ptc2 frozen files.

DONE-GATE
- (T1-T3) `python3 -m pytest -q tests` all green against a live FalkorDB; GATE G1 and G2 hold.
- (T4-T5) `grep -rnE "<script[^>]+src=\"https?:|<link[^>]+href=\"https?:" warmopen/static` returns nothing.
- (T4-T6) Manual check by the gate seat: load seed with the T6 CLI, serve, run the full demo loop in two browsers.
- Every task T1-T6 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material in files. stdlib + falkordb + pytest only. Print files changed and deviations.

ASTRA PLAN REVIEW ADDITIONS (2026-10-23; accepted by the spec author; binding)
Decisions: ptc3 starts only after ptc2 lands (serialized); replay must run on the laptop with no network and no FalkorDB; replay matches request bodies.
C1. Recorded mode imports nothing outside the standard library (no falkordb import at module load in app.py or cli.py on the replay path), so `python3 -m warmopen.cli serve --replay DIR` runs on the laptop offline. RUNBOOK states: phone hotspot first, laptop replay second.
C2. Replay matches method + path + request body (parsed JSON equality, absent body == None). Mismatch -> 404 "not in recording". Exception: GET /api/requests/<id> is sticky; once its recordings are consumed, it keeps serving the last one (so polling does not break). All other paths are finite.
C3. Error mapping precedence: StateError 409, PermissionError 403, NotFound 404, ValueError 400.
C4. Presentation payload: POST /api/requests, GET /api/requests/<id> and POST /api/requests/<id>/reveal also return "people": {id: name} for every person on returned routes (revealed names only after reveal) and "evidence": {id: {"url","claim"}} for every public evidence id on routes, supports and openers. Private evidence is never returned.
C5. One reveal per request: after the first reveal, the UI disables other Reveal buttons.
C6. No full-text search: target picker filters /api/targets client side. PLAN.md A5 amended.
C7. The UI shows the cited claim text under each opener; unsourced openers show "No source: general opener".
C8. Recording filenames come from a counter under the server lock (no collisions).

C9. (ptc1/ptc2 review carry-over) make_server uses the one GraphStore it is given for every request; never construct a second store in the server (the threading.Lock is per instance; README Limits line). JEV request shape is confirmed live (criteria maps, see docs/jev-probe.json); do not change scoring.build_payload. tests/test_ptc1b_fixes.py and tests/test_ptc2b_jev_shape.py are PROTECTED and must stay green.

C-ENV. Build environment (spec author, 2026-10-23): the builder tree is ~/repos/warm-open on the laptop with NO FalkorDB and NO packages beyond the standard library. Do not install anything. Verify with `python3 -m compileall -q warmopen` and by reading the frozen tests. The gate seat syncs the tree to Daytona sandbox warm-open-ptc (FalkorDB 6.0.1, falkordb client 1.7.1, pytest 9.1.1) and runs the DONE-GATE pytest there; failures return as <tag>b with the output.
