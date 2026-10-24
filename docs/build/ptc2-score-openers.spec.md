RISK: standard
BUILDER: sol
SCOPE: pyproject.toml README.md .gitignore warmopen scripts docs data
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the app can turn a request into (a) abstract features and gaps read from the graph, (b) one JEV call that returns an uncalibrated fit band and an introducer choice, or an honest abstention, and (c) exactly three opener cues, each citing a public evidence node with its URL, with template fallback. The scorer and writer agents log their steps as AgentEvents.

INTENT ANCHOR
For an invest or sales request, the user gets a fit band labeled uncalibrated with reasons drawn from the graph, or an honest abstention, plus three openers that each cite a public source. JEV sees only abstract numbers and fixed labels.

CONTEXT
- Goals: "invest" (target is a fund partner) and "sales" (target works at a company that may buy). Karthik's pick, 2026-10-23.
- The fit score is NOT a calibrated probability. The output key is "value" under label "uncalibrated fit". The word "probability" must not appear as a key anywhere in score output.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 JEV request shape for choice lists is unconfirmed (PLAN.md A4); T3 probe settles it. Tests use a fake.
- A2 Opener LLM is the Anthropic Messages API via urllib, model from WARMOPEN_LLM_MODEL (default claude-haiku-5-5).
- A3 Keys come only from env vars in the sandbox (PLAN.md A7).
- Q1 would_improve rule is the builder's choice, stated in the report; the gate seat checks it is deterministic.

WHAT EXISTS
- ptc1 package (landed). Frozen: tests/conftest.py (SEED fixture), tests/test_ptc1_core.py, and now tests/test_ptc2_score.py (FAILS now).
- JEV API as recorded 2026-09-21: POST https://api.typesafe.ai/v1/systemone, header Authorization: Bearer <key>, body {state, model:"jev-latest", questions:{<name>:{type,instructions,criteria}}}; response {model, answers:{<name>:{choice,confidence,probabilities}}, usage}. Where the list of allowed choices goes in the request is NOT recorded (PLAN.md A4).

TASKS
T1. Persist the revealed route: ptc1 broker.reveal stores the revealed route on the request (after approval only). Add broker.revealed_route(store, request_id) -> route dict or None. ptc1 tests must stay green.

T2. warmopen/features.py: extract_features(store, request_id) -> dict with exactly these keys:
    goal ("invest"|"sales"), public_route_count (int), best_public_hops (int|None), revealed (bool), revealed_hops (int|None), revealed_min_tie (float|None), shared_work_links (int), co_speaker_links (int), coauthor_links (int), topic_overlap_count (int: topics both requester and target link to via INTERESTED_IN or a talk they speak at ABOUT), stage_match (bool|None; invest only: requester's FOUNDED Startup.stage in target's PARTNER_AT Fund.stages), sector_overlap_count (int|None; invest only), category_match (bool|None; sales only: requester startup product_category in target's WORKS_AT Company.needs), evidence_count (int: distinct public evidence on target facts and public route edges), gaps_count (int), routes (list of {"route_id","hops","min_tie","kind"} with kind "public"|"revealed"; min_tie None for public).
    gaps(store, request_id) -> list of {"id","text"}; ids from: gap_stage, gap_sector, gap_category, gap_no_warm_route (no public route and no revealed route). Deterministic order: as listed.
    GATE G1: every leaf value in extract_features output is int, float, bool, None, or a string matching ^(invest|sales|public|revealed|public_\d+|revealed_\d+)$.

T3. warmopen/jev.py: jev_client(api_key, url="https://api.typesafe.ai/v1/systemone", timeout=8.0) -> callable(payload: dict) -> dict using urllib only. scripts/jev_probe.py: one real call with a two-choice question, writes request and response (key redacted) to docs/jev-probe.json; run it once in the sandbox and adapt build_payload to the confirmed request shape. Not run by tests.
    warmopen/scoring.py: build_payload(features, choices) -> dict {"model":"jev-latest","state":features,"questions":{"fit":...,"introducer":...}}. Fit choices: ["high","medium","low","INSUFFICIENT_EVIDENCE"]. Introducer choices: every route_id in features["routes"] + ["APPROACH_DIRECTLY","INSUFFICIENT_EVIDENCE"]. Instructions and criteria are fixed strings written in code per goal (invest: would this partner take a first meeting; sales: would this buyer take a 20-minute call).
    score_fit(store, request_id, jev, min_confidence=0.6) -> dict with exactly keys {"label","band","value","confidence","abstained","reason","introducer","supports","against","would_improve"}.
      - Calls jev exactly once with build_payload(...).
      - label is always "uncalibrated fit".
      - Abstain (abstained True, band None, value None) when: fit choice is INSUFFICIENT_EVIDENCE (reason "insufficient_evidence"), confidence < min_confidence (reason "low_confidence"), or jev raises or returns a malformed answer (reason "jev_unavailable"). Otherwise abstained False, reason None, band = fit choice, confidence = JEV confidence, value = round((p_high + 0.5*p_medium) / (p_high + p_medium + p_low), 2) from the fit probabilities.
      - introducer: None if JEV chose INSUFFICIENT_EVIDENCE, an unknown id, or abstained for jev_unavailable; {"route_id":"APPROACH_DIRECTLY","via":None} for direct; for a public route {"route_id", "via": persons[1]}; for the revealed route {"route_id", "via": persons[0]}.
      - supports: at most 2 {"text","evidence_id"}, public evidence only, route-edge evidence first, then target facts. against: at most 1 {"text","gap_id"} from gaps(). would_improve: at most 1 {"text"}; deterministic rule of your choice, stated in the report. These three are computed from the graph, never from JEV, and are present even when abstained.
      - Logs (scorer, "fit_scored").
    GATE G2: fake JEV with probabilities high .7 medium .2 low .05 IE .05 and confidence .8 gives value 0.84, band "high".

T4. warmopen/openers.py: generate_openers(store, request_id, llm) -> list of exactly 3 {"text","evidence_id","url","source"}.
      - Allowed evidence: visibility "public" evidence attached to target facts (talks they speak at, their fund or company facts) and to public route edges. Private evidence is never allowed, even after reveal.
      - llm is callable(prompt: str) -> str. The prompt lists goal and allowed evidence (id, claim, url) and asks for a JSON array of {"text","evidence_id"}.
      - Keep a cue only if it parses, evidence_id is allowed, text is non-empty and at most 280 characters, and its evidence_id is not already used. url comes from the graph, never from the LLM.
      - Fill to 3 with templates (source "template") built from unused allowed evidence, then reuse if fewer than 3 exist. If no allowed evidence exists, return 3 generic templates with evidence_id None and url None.
      - llm raising or returning non-JSON -> all templates.
      - Logs (writer, "openers_written").
    warmopen/llm.py: anthropic_llm(api_key, model=os.environ.get("WARMOPEN_LLM_MODEL","claude-haiku-5-5")) -> callable using urllib against the Anthropic Messages API. Not called by tests.
    GATE G3: an LLM cue citing ev_private_b or an unknown id is dropped and replaced by a template.

FROZEN CONTRACT
tests/test_ptc2_score.py (PROTECTED), plus ptc1 frozen files.

DONE-GATE
- (T1-T4) `python3 -m pytest -q tests` all green against a live FalkorDB (ptc1 + ptc2); GATE G1 to G3 hold.
- (T3) `grep -rn "probability" warmopen/scoring.py` shows no output-dict key named probability.
- (T3) docs/jev-probe.json exists from one real call, or the report says the sandbox had no JEV key.
- Every task T1-T4 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material in files (read keys from env). Network only to FalkorDB, and in T3/T4 clients only (never from tests). Print files changed and deviations.

ASTRA PLAN REVIEW ADDITIONS (2026-10-23; accepted by the spec author; binding)
Decisions: JEV answers are validated before any arithmetic; openers show the cited claim so the user can check support.
C1. Malformed JEV answer (reason "jev_unavailable"): missing answers.fit or answers.introducer; fit choice outside the fit choices; confidence not a finite number in [0,1]; any of high, medium, low probabilities missing, negative or non-finite; p_high + p_medium + p_low == 0.
C2. Introducer reads route persons through broker.revealed_route for the revealed route (owner-rooted, via persons[0]) and through paths.public_paths for public routes (via persons[1]).
C3. Openers with evidence_id None (no allowed evidence) carry "source": "template" and the UI labels them "No source: general opener". PLAN.md criterion 5 is amended to match.
C4. The opener dict keeps exactly the keys text, evidence_id, url, source (the frozen equality check depends on it). ptc3 supplies each cited claim through its presentation payload.
C6. (ptc1 build review carry-over, Astra P2) The reveal replay path (same offer already revealed) re-runs the idempotent Person-name MERGE for the stored route people, so a post-commit copy failure is repaired on retry. tests/test_ptc1b_fixes.py (PROTECTED) must stay green; ptc1b is built and gated (not yet committed): one conditional statement commits the snapshot and approval, OwnerCredential stores token_sha256, GraphStore.private validates owner ids.
C5. Known limit: a valid evidence id does not prove the text is supported. The LLM prompt instructs "only restate what the cited claim says"; ptc3 shows the claim under each opener.

C-ENV. Build environment (spec author, 2026-10-23): the builder tree is ~/repos/warm-open on the laptop with NO FalkorDB and NO packages beyond the standard library. Do not install anything. Verify with `python3 -m compileall -q warmopen` and by reading the frozen tests. The gate seat syncs the tree to Daytona sandbox warm-open-ptc (FalkorDB 6.0.1, falkordb client 1.7.1, pytest 9.1.1) and runs the DONE-GATE pytest there; failures return as <tag>b with the output.
