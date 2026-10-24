# ptc3 review adjudication (2026-10-23)


| # | Source | Card | Ruling | Route |
|---|---|---|---|---|
| 1 | Gate seat | Template opener runs claim into question | revise_plan | ptc3b T1 |
| 2 | Gate seat | no_consent answer and send not on timeline | revise_plan | ptc3b T2 |
| 3 | Gemma PP-4 | Server lock held across slow JEV/LLM calls | revise_plan | ptc3b T3 |
| 4 | Gemma PP-1 | Token leaks into recordings | rejected: headers not recorded; grep of 15 recordings finds no token | none |
| 5 | Gemma PP-2 | Error mapping shadowed by ValueError | rejected: StateError, PermissionError, NotFound checked before the 400 default (app.py:240-245) | none |
| 6 | Gemma PP-3 | Replay pops from a list | keep_plan: file-order matching is the design (ptc3 C2) | none |
| 7-17 | DeepSeek PP-1..PP-11 | Eleven "typos" whose fix is identical text (busy, setInterval, onsubmit, None, ...) | rejected: fabricated; live walk-through and offline replay work | none |

Seat note: DeepSeek V4 Pro fabricated identical-text typo cards on ptc1, and again on ptc3 (11 cards, 396 s). Recommend a reviewer ablation before the next panel.

## ptc3b (2026-10-23)


| # | Source | Card | Ruling |
|---|---|---|---|
| 18 | DeepSeek PP-1 | Request view reads without one lock | keep_plan (P2): display only, self-corrects on the next 2 s poll; consent and state checks run under store.lock in write paths; wrapping risks re-entry deadlock on the non-reentrant lock |
| 19 | DeepSeek PP-2 | /api/targets two queries | keep_plan: seed loads once at startup; no concurrent writer of people or talks |
| 20 | Gemma PP-1 | Recording order vs response order | keep_plan: counter assigned at delivery under response_lock, so recording order equals delivery order, which replay needs |
| 21 | Gemma PP-2 | Nested locks | keep_plan: fixed order response_lock then lock; replay path takes lock only; no deadlock |

## ptc3c (2026-10-23)


| # | Source | Card | Ruling |
|---|---|---|---|
| 22-24 | DeepSeek PP-1..PP-3 | Identical-text "typos" (persons, unshift, abstained) | rejected: fabricated; the browser run renders the path, requester node and abstention text |
| - | Gemma | No cards, verdict DEFENSIBLE | none |

## ptc3d (2026-10-23, mechanical, no panel)

Gate: 54/54 tests. Phone check (Firefox 158, 390 px iframe): requester page scrollWidth 848 -> 390; path SVG scrolls inside .path-scroll. 1280 px layout unchanged (screenshot). Fix: `.workspace > div { min-width: 0; }` in style.css.
