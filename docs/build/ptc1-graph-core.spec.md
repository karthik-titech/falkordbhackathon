RISK: crypto          # consent grants are authorization (Astra review 2026-10-23, project rule)
BUILDER: sol
SCOPE: pyproject.toml README.md .gitignore warmopen scripts docs data
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py
FORBID: git, env-keys, deps

GOAL
After this chunk, a new Python package `warmopen/` exists in the private repo `karthik-titech/warm-open`. It loads conference seed data into FalkorDB, computes tie strength, finds public warm routes from a requester to a target, records consent grants, answers private reachability through a broker without leaking names, reveals a route only under a separate reveal grant, runs an introduction request state machine, and writes every agent action as an AgentEvent node in the shared graph.

INTENT ANCHOR
A requester can see, through graph queries alone, every warm public route to a speaker, and can learn from a consenting owner's private graph only a hop count and tie strength until that owner separately approves a reveal. No private name reaches the shared graph before that approval.

CONTEXT
- No branding of any real company (do not use the word "Gigi").
- Dependencies: Python 3.11+ standard library, the `falkordb` Python client, and `pytest` for tests. NOTHING ELSE. No FastAPI, no requests, no numpy. If you believe another package is required, stop and say so in the final report.
- FalkorDB runs at FALKORDB_HOST / FALKORDB_PORT (defaults localhost / 6379). Tests need a live FalkorDB; they do not mock it.
- Agents are plain backend functions with fixed permissions, named seeker, broker, scorer, writer. They hand off through Request, Grant, Offer and AgentEvent nodes in the shared graph.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 FalkorDB runs at FALKORDB_HOST:FALKORDB_PORT, reachable from the build tree (Daytona sandbox). Default: localhost:6379.
- A3 RISK is standard although consent grants are authorization (PLAN.md A3). Karthik may raise it.
- A4 Owner tokens are demo credentials from the seed file, not real secrets.
- Q1 For a shared_work hop, which evidence id goes on the edge when both people have one? Default: the requester-side (earlier person) contribution evidence.

WHAT EXISTS

GRAPHS
- Shared graph name: f"{prefix}event". Private graph per owner: f"{prefix}p_{owner_id}". `prefix` comes from GraphStore.connect (tests pass a random prefix; app default "wo_").
- Event graph labels: Person{id,name,handle,kind('speaker'|'attendee'),consented(bool)}, Talk{id,title,conference,starts,room}, Topic{id,name}, Repo{id,full_name}, Company{id,name,needs(list)}, Fund{id,name,stages(list),sectors(list)}, Startup{id,name,stage,sectors(list),product_category}, Evidence{id,url,claim,observed_at,visibility}, Request{id,requester,target,goal,state,created_at}, Grant{id,owner,requester,request_id,scope,expires_at,revoked}, Offer{id,request_id,owner,hops,tie}, AgentEvent{seq,agent,action,request_id,at}.
- Event graph edges (each fact edge carries evidence_id when the seed gives one): SPEAKS_AT(Person->Talk), ABOUT(Talk->Topic), INTERESTED_IN(Person->Topic), CONTRIBUTED_TO(Person->Repo), MAINTAINS(Person->Repo), COAUTHORED(Person->Person), WORKS_AT{role}(Person->Company), PARTNER_AT(Person->Fund), FOUNDED(Person->Startup), SUPPORTED_BY(any fact node->Evidence).
- Private graph: Person{id, owner(bool)}, KNOWS{category('colleague'|'coauthor'|'friend'|'met'), strength(float), strength_source('formula'|'owner'), evidence_id}, plus private Offer-route records (your design) that hold the route behind an Offer id. Private names and ids never appear in the event graph before a reveal.
- Owner tokens: each consenting owner has an owner_token from the seed. Store it so it cannot be read back through any event-graph dump (store only in the private graph, or as a salted digest; your choice, state it in the report).

TASKS

T2. warmopen/graphstore.py: class GraphStore with classmethod connect(host, port, prefix="wo_"), methods event() and private(owner_id) returning graph handles, query(graph_name_or_handle, cypher, params) helper, dump(graph="event") -> list[dict] of every node's label plus properties and every edge's type plus properties (used by tests to prove non-leakage), drop_all() deleting only graphs that start with this store's prefix. warmopen/seed.py: load_seed(store, seed: dict) -> dict of counts, idempotent (MERGE by id). Seed format is exactly the one built in tests/conftest.py::SEED; private section builds the private graphs; KNOWS strength from T3.
    GATE G1: loading SEED twice gives identical dump() output and identical counts.

T3. warmopen/ties.py: tie_strength(features: dict, owner_strength: float | None = None) -> tuple[float, str].
    Formula (exact): x = 0.35*min(shared_repos,5) + 0.6*coauthored + 0.25*mutual_follow + 0.5*met_today + 0.3*same_company (booleans as 0/1, missing keys = 0); s = round(1 - exp(-x), 3); return (s, "formula"). If owner_strength is not None it must be in [0,1] (else ValueError) and the result is (round(owner_strength,3), "owner").
    GATE G2: tie_strength({}) == (0.0,"formula"); tie_strength({"shared_repos":2}) == (0.503,"formula"); owner override wins; out-of-range override raises.

T4. warmopen/paths.py: public_paths(store, requester, target, max_hops=3, k=3) -> list[dict]. A route is a sequence of persons from requester to target where each consecutive pair is linked by a WARM public link: COAUTHORED (category "coauthor"), both CONTRIBUTED_TO or MAINTAINS the same Repo (category "shared_work"), or both SPEAKS_AT the same Talk (category "co_speaker"). Topic links (INTERESTED_IN, ABOUT) are NEVER warm links. Route dict: {"route_id": "public_<n>" (1-based in output order), "hops": number of person-to-person links, "persons": [ids requester..target], "edges": [{"from","to","category","evidence_id"}]}. evidence_id is the evidence on the linking fact (null allowed only when the seed has none). Order: hops ascending, then more non-null evidence first, then route persons lexicographic. At most k routes, no route longer than max_hops, no person repeated in a route. Unknown requester or target -> ValueError.
    GATE G3: topic-only connection returns []; shortest route first; every edge has a category from the three allowed.

T5. warmopen/requests.py: GOALS = ("invest", "sales"). create_request(store, requester, target, goal) -> request_id (goal not in GOALS -> ValueError; unknown people -> ValueError); state starts "draft". get_request(store, request_id) -> dict. advance(store, request_id, expected_state, new_state) -> dict: allowed transitions draft->awaiting_approval, awaiting_approval->approved, awaiting_approval->declined, approved->requested; anything else, or expected_state != current state, raises StateError (define it) and changes nothing. Seeker logs "request_created".
    GATE G4: a stale expected_state is rejected and leaves state unchanged.

T6. warmopen/consent.py: SCOPES = ("reachability", "reveal"). grant(store, owner, owner_token, requester, request_id, scope, ttl_s=900, now=None) -> grant_id; wrong token -> PermissionError; bad scope -> ValueError; owner must be a consented Person. has_grant(store, owner, requester, request_id, scope, now=None) -> bool (false if revoked or expired). revoke(store, owner, owner_token, grant_id). A reachability grant never implies a reveal grant. `now` is an epoch float for tests; default time.time().
    GATE G5: reachability grant alone -> has_grant(...,"reveal") is False; expired grant -> False.

T7. warmopen/broker.py: reachability(store, owner, request_id, now=None) -> dict with exactly keys {"status","hops","tie","offer_id"}. Without a reachability grant: {"status":"no_consent","hops":None,"tie":None,"offer_id":None} and an AgentEvent (broker, "reachability_asked"). With a grant: search the owner's private graph for a KNOWS route owner->target of 1 or 2 hops (never more); tie = minimum strength on the route; best route = fewer hops, then higher tie. Found -> status "reachable", offer_id = opaque random token (secrets.token_urlsafe, no ids inside), store event-graph Offer{id,request_id,owner,hops,tie} and the private route record; advance request draft->awaiting_approval if it is in draft; log (broker, "reachability_answered"). Not found -> status "unavailable", other fields None. The result and the event graph must not contain any private person id or name other than the owner and the target.
    reveal(store, owner, request_id, offer_id, now=None) -> route dict in the T4 shape with route_id "revealed_1", categories from KNOWS, plus "tie" on each edge; requires a reveal grant (else PermissionError); unknown offer -> ValueError; advances awaiting_approval->approved; logs (broker, "route_revealed").
    GATE G6: event dump() after reachability contains no private intermediary id; reveal without reveal grant raises PermissionError.

T8. warmopen/agentlog.py: log(store, request_id, agent, action) writes AgentEvent with increasing seq per request, linked to its Request; events(store, request_id) -> list of {"seq","agent","action"} ascending. AGENTS = ("seeker","broker","scorer","writer"); unknown agent -> ValueError.

FROZEN CONTRACT
tests/conftest.py and tests/test_ptc1_core.py (PROTECTED). Implement against them; do not edit them.

DONE-GATE
- (T1-T8) `python3 -m pytest -q tests/test_ptc1_core.py` all green against a live FalkorDB; GATE G1 to G6 hold.
- (T1) `python3 -m compileall -q warmopen` clean.
- Every task T1-T8 reported done or explicitly not done.


ASTRA PLAN REVIEW ADDITIONS (2026-10-23; accepted by the spec author; binding)
Decisions: tier raised to crypto for ptc1 (consent grants are authorization; project rule); private evidence lives only in private graphs; request ids are bearer ids for the demo; one reveal per request.
C1. warmopen/errors.py defines NotFound(ValueError). Unknown request id, unknown offer and unknown person raise NotFound. Existing ValueError expectations still hold.
C2. Request ids and Grant ids come from secrets.token_urlsafe(16). The demo treats a request id as bearer access; state this in README.
C3. Evidence partition: evidence whose visibility is "private", and every evidence id referenced only from a seed private section, is written only to that owner's private graph, never to the event graph. Private section may carry "people": [{"id","name"}]; those names live only in the private graph. Without a name, a private person's name is its id.
C4. Ask record: reachability() always records an Ask{request_id, owner, at} node in the event graph (owner is a consenting person, so this is allowed), including the no_consent case, so an owner can list pending asks. Repeat asks update `at`, they do not duplicate.
C5. Binding checks: grant() raises ValueError when requester != Request.requester. revoke() raises PermissionError when the grant's owner is not `owner` or the token is wrong. reveal() raises NotFound unless the Offer exists AND Offer.owner == owner AND Offer.request_id == request_id.
C6. reveal() order: validate offer (NotFound), then reveal grant (PermissionError), then state. If the request is already approved: same offer returns the stored route unchanged; a different offer raises StateError. A later revoke does not retract an already revealed route (demo rule, stated in README).
C7. The revealed route is owner-rooted (persons start at the owner, as the frozen test asserts). This is the one exception to the T4 route shape. hops counts owner-to-target KNOWS links only; tie is the minimum on that route.
C8. Atomicity: GraphStore holds one threading.Lock; every mutation that reads then writes (advance, AgentEvent seq allocation, grant, revoke, offer creation, reveal) runs under it.

C-ENV. Build environment (spec author, 2026-10-23): the builder tree is ~/repos/warm-open on the laptop with NO FalkorDB and NO packages beyond the standard library. Do not install anything. Verify with `python3 -m compileall -q warmopen` and by reading the frozen tests. The gate seat syncs the tree to Daytona sandbox warm-open-ptc (FalkorDB 6.0.1, falkordb client 1.7.1, pytest 9.1.1) and runs the DONE-GATE pytest there; failures return as <tag>b with the output.
