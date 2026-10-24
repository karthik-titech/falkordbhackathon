# ptc3e / ptc3f gate notes (2026-10-24)

- ptc3e (standard, slide restyle): 60/60 tests; Firefox walk-through screenshots match Karthik's reference slides (kicker, heavy headline, mono subline, line-art path, ■ ◩ □ columns, numbered openers, bottom step track); phone scrollWidth 390. Builder-side Firefox crashed (exit 134), so visual gating was done by the gate seat. Panel: not run yet (UI-only restyle; queue with the next panel batch).
- ptc3f (mechanical): conference display names; 61/61 tests; live server serves it.

## ptc3e panel (2026-10-24)

| # | Source | Card | Ruling |
|---|---|---|---|
| 25 | DeepSeek PP-1 | Owner named in headline before reveal | rejected: owners are consenting public attendees already shown in owner rows; hidden middle contacts never appear before reveal |
| 26 | Gemma PP-1 | Target name in headline before reveal | rejected: targets are public speakers |
| 27 | Gemma PP-2 | APPROVE step semantics | keep_plan: spec defines APPROVE as route approved (done) |
| 28 | Gemma PP-3 | `opened` flag sticks across requests | rejected: flags reset on each new request (app.js:189-190) |

## ptc4 build review and panel (2026-10-24)


| # | Source | Card | Ruling |
|---|---|---|---|
| 29 | Astra P1 (FIX-FIRST); DeepSeek PP-1; Gemma PP-1 | Owners get request ids in their pending list; GET /api/requests/<id>, score and openers then expose the requester's meetings without the requester's token | revise_plan -> ptc4b (contract test_ptc4b_view_scope.py reproduces it: anonymous score named owner_a) |
| 30 | DeepSeek PP-2 | use_own_memory flag visible on the Request | keep_plan: says only that a token was presented, not whether or whom the requester met |
| 31 | Gemma PP-2 | public_paths reads private graph without its own auth | covered by ptc4b: authorization in app.py per call, library default include_own=False |
| 32 | Gemma PP-3 | Coarse lock in log_meeting | keep_plan: single presenter; the store lock serializes all graph writes by design |

## ptc7 / 7b / 7c panel (2026-10-24)

Gate: 84/84 then 94/94 with ptc6; single-page Firefox walk-through passes.

| # | Source | Card | Ruling |
|---|---|---|---|
| 33 | DeepSeek PP-1 | prefers-reduced-motion misspelled | rejected: spelled correctly (style.css:149); ptc3e test pins it |
| 34 | DeepSeek PP-2 | draw() throws without routes | rejected: draw handles a null route; every API view returns routes |
| 35 | DeepSeek PP-3 | requester token after requester change | keep_plan: calls use the token of the request's own requester by design (ptc4b) |
| 36 | Gemma PP-1 | panel session/grant mismatch on fast owner switch | keep_plan: grant handler checks panelSession identity before and after the call |
| 37 | Gemma PP-2 | owner tokens in sessionStorage keyed by owner | keep_plan: spec choice (tab-scoped, never localStorage, never in DOM or URL) |
| 38 | Gemma PP-3 | polling race across revisions | keep_plan: responses from stale revisions are dropped by the revision check |
