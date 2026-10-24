RISK: standard
BUILDER: sol
SCOPE: warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py, tests/test_ptc4b_view_scope.py, tests/test_ptc4c_replay_scope.py, tests/test_ptc4d_replay_all_authenticated.py, tests/test_ptc6_jev_moves.py, tests/test_ptc7_split_screen.py, tests/test_ptc7c_product_name.py, tests/test_ptc8_hooked_openers.py
FORBID: git, env-keys, deps

GOAL
After this chunk, when JEV picks the portfolio_news hook for an investor target, the first opener reads like a person at a conference: "Hi, I'm <requester name>, founder of <startup>. Nice to meet you. Did you see <company>'s news? Great company. <bridge>" where the bridge names a speaker from that company when the graph has one, and always ends "Is anyone from their team here?". The fact comes from a public INVESTED_IN edge with a source URL.

INTENT ANCHOR
Karthik's example: founder F looking for an angel in AI security meets VC V; the opener cites V's portfolio company U and asks whether anyone from U's team is here. The graph answers that question before you ask it.

CONTEXT
- Karthik 2026-10-24 (example opener in the request). Data rule: company news and self-published bios with source URLs; never personal social feeds; never inferred traits.
- Builds on ptc6 (cue_type choices include portfolio_news and personal_interest; suggested_move stores the cue; template endings for the other cue types).
- JEV sees only booleans: has_portfolio_news, team_member_present, has_stated_interest (added to extract_features; abstract only, frozen ptc2 rules).

ASSUMPTIONS AND OPEN QUESTIONS
- A1 The requester's display name is Person.name and the startup is the Startup they FOUNDED; both come from the requester's own consented profile.
- A2 Timing rule: name the conference of the team member's talk; say "today" only when the talk's conference is the current event (not in v1 data).
- Q1 personal_interest hooks need (Person)-[:ENJOYS]->(Interest) from self-published bios; none exist in today's data. Support the edge type in seed.py and a template, but no data is loaded.

WHAT EXISTS
- warmopen/seed.py _FACTS (no INVESTED_IN or ENJOYS yet).
- warmopen/features.py extract_features; warmopen/openers.py templates and LLM prompt (ptc6 cue endings); warmopen/scoring.py suggested_move (ptc6).

TASKS
T1. seed.py: add fact types INVESTED_IN (Fund -> Company; properties round, lead; evidence) and ENJOYS (Person -> Interest node {id, name}; evidence required). Both public facts with SUPPORTED_BY evidence like other facts.
T2. features.extract_features adds has_portfolio_news (the target is PARTNER_AT a Fund with an INVESTED_IN edge whose evidence is public), team_member_present (some event-graph speaker WORKS_AT that company), has_stated_interest (the target has an ENJOYS edge with public evidence). Booleans only.
T3. openers: when the stored cue_type is portfolio_news and a portfolio company exists, opener 1 is built from the INVESTED_IN evidence (evidence_id and url from the graph): "Hi, I'm <name>, founder of <startup>. Nice to meet you. Did you see <company>'s news? Great company." then, if a team member exists, " I saw <member> from <company> gave a talk at <conference name>." then " Is anyone from their team here?". Keep <= 280 characters (shorten the talk sentence first, then drop it). Openers 2 and 3 follow the existing rules (distinct, cited where possible). For personal_interest with an ENJOYS edge: "Hi, I'm <name>, founder of <startup>. I read that you enjoy <interest>. How did you get into it?". The LLM prompt includes the cue type and the hook evidence (claim and company name) and asks for that structure.
T4. Ranking: if several portfolio companies exist, prefer one whose sectors or Topics overlap the requester startup's seeking or sectors, then one with a team member present, then the most recent evidence observed_at.

T5. (ptc6 panel carry-over, DeepSeek PP-1, P2) When score_fit runs with include_own=True, store the moves with a flag own_derived=true on the Request. suggested_move(store, rid, include_own=False) and generate_openers(..., include_own=False) ignore own-derived moves (treat as no move, default ending) unless include_own is True; app.py passes own_allowed(...) for the calling request. Existing frozen tests keep their behavior.

FROZEN CONTRACT
tests/test_ptc8_hooked_openers.py (PROTECTED), plus every earlier frozen file.

DONE-GATE
- (T3) Gate seat: on the real demo seed with the sourced Keycard chain loaded, the opener for Aliisa Rosenthal (goal invest) names Keycard and Kim Maida and ends with "Is anyone from their team here?".
- Every task T1-T5 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit tests/. Print files changed and deviations.

C-ENV. Laptop tree, stdlib only; do not install anything. The gate seat runs the full suite in the local Docker runner.
