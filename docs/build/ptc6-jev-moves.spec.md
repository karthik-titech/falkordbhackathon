RISK: standard
BUILDER: sol
SCOPE: warmopen
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py, tests/test_ptc3f_conference_names.py, tests/test_ptc4_met_memory.py, tests/test_ptc4b_view_scope.py, tests/test_ptc4c_replay_scope.py, tests/test_ptc4d_replay_all_authenticated.py, tests/test_ptc6_jev_moves.py, tests/test_ptc7_split_screen.py, tests/test_ptc7c_product_name.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the single JEV call also decides the opener style (cue_type) and the next move (next_action). The fit card shows "Suggested move" and "Opener style" with JEV's confidence, the openers follow the chosen style, and JEV still sees only abstract numbers, booleans and fixed labels.

INTENT ANCHOR
JEV chooses how to approach the person; the graph supplies every fact; the LLM only words it.

CONTEXT
- Karthik 2026-10-24 ("add it as ptc6") after reviewing ChatGPT's JEV design. Accepted: cue_type, best_next_action. Rejected: evidence_grounded (sends free text to an external API; grounding is already structural). Not added: mutual_topic and complementarity scores (already counts in features), missing_information (gaps() already).
- JEV live shape (docs/jev-probe.json): choice questions use "criteria" as {choice: description}; no "choices" key.
- Frozen limits: score_fit returns exactly its current keys (tests/test_ptc2_score.py:105); feature strings may only be invest|sales|public|revealed|route ids (test_ptc2_score.py:13), so new features are numbers or booleans; jev.calls[0]["state"] == extract_features(...).

ASSUMPTIONS AND OPEN QUESTIONS
- A1 Missing cue_type or next_action answers (older JEV, fakes) mean "no move", never "jev_unavailable"; fit and introducer validation (ptc2 C1) is unchanged.
- A2 Move confidence gate is the same min_confidence as fit (0.6).

WHAT EXISTS
- warmopen/scoring.py build_payload (fit, introducer), score_fit, _validate.
- warmopen/features.py extract_features (topic_overlap_count etc.).
- warmopen/openers.py _template ("I read: <claim>. What would you add?"), LLM prompt.
- warmopen/memory.py (ptc4) private met edges; warmopen/seed.py Startup.seeking (ptc5).
- warmopen/app.py POST /api/requests/<id>/score.

TASKS
T0. seed.py stores the optional Startup.seeking list (topic ids the requester is looking for); moved here from ptc5 T1 because ptc6 is built first.
T1. features.extract_features adds "seeking_overlap_count" (int: topics in the requester startup's seeking list that the target speaks on) and "met_before" (bool: the requester's private graph has a KNOWS edge requester->target). Abstract only.
T2. scoring.build_payload adds two choice questions after fit and introducer, in this order: "cue_type" with criteria keys exactly shared_interest, capability, problem, previous_conversation, portfolio_news, personal_interest, INSUFFICIENT_EVIDENCE (the last two hook types get their opener text in ptc8; until then openers use the default ending for them); "next_action" with criteria keys exactly start_conversation, ask_discovery_question, request_intro, no_approach, INSUFFICIENT_EVIDENCE. Fixed descriptions written in code; no graph strings.
T3. score_fit (output keys unchanged) stores on the Request node the cue_type and next_action choice and confidence when the answer is present, the choice is a known non-INSUFFICIENT_EVIDENCE option, and confidence >= min_confidence; otherwise stores nothing for that question (clears any earlier value). scoring.suggested_move(store, request_id) -> {"cue_type": {"choice","confidence"}|None, "next_action": {"choice","confidence"}|None}.
T4. openers: when a cue_type is stored, evidence-backed templates end with: shared_interest "What drew you to it?"; capability "How did you approach it?"; problem "What problem are you most focused on there?"; previous_conversation "What has changed since we last spoke?" (default unchanged "What would you add?"). The LLM prompt names the cue type and asks for that style. Keys and <= 280 rule unchanged.
T5. app.py: the score endpoint response adds "move": suggested_move(...). UI fit card shows "Suggested move: <plain words>" and "Opener style: <plain words>" with confidence, or "No suggested move" when None. textContent only.

FROZEN CONTRACT
tests/test_ptc6_jev_moves.py (PROTECTED), plus every earlier frozen file.

DONE-GATE
- (T0-T5) `python3 -m pytest -q tests` all green against a live FalkorDB.
- (T2) Gate seat: one live JEV call from the laptop with the real payload returns HTTP 200 with all four answers.
- Every task T0-T5 reported done or explicitly not done.

CONSTRAINTS: work only inside the warm-open repo. No git. No key material. No network. Do not edit tests/. Print files changed and deviations.

C-ENV. Laptop tree, no FalkorDB, stdlib only; do not install anything. The gate seat runs the full suite in Daytona and the live JEV probe from the laptop.

AMENDMENT 2026-10-24 (ptc4 Astra plan review carry-over; binding)
What changed: requester-own meeting memory is opt-in and token-bound.
Why: Astra plan review of ptc4 (P1: requester id is caller-controlled on unauthenticated endpoints).
Affected tests: tests/test_ptc6_jev_moves.py (re-pinned 4e342a51).
Reapproval: no
Note: spec author folded an Astra P1 on 2026-10-24; scope unchanged.
C1. met_before is True only when the Request has use_own_memory (created with the requester's valid token, ptc4 C2) AND the requester's private graph has a "met" or other KNOWS edge to the target. A tokenless request always reports False.
