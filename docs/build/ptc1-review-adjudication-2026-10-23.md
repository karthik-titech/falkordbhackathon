# ptc1 review adjudication (2026-10-23)



| # | Source | Card | Ruling | Route |
|---|---|---|---|---|
| 1 | Astra P0 | Clock sampled before the lock; queued call honors an expired grant | revise_plan | ptc1b T1 |
| 2 | Astra P1 | Reload keeps evidence reclassified private | revise_plan | ptc1b T3 |
| 3 | Astra P1 | Reveal writes snapshot and state separately | revise_plan | ptc1b T2 |
| 4 | Astra P2 | Lock is per GraphStore instance | keep_plan (documented limit) | ptc1b T6 README line; ptc3 holds one store |
| 5 | DeepSeek PP-1 | "Typos" json.loads / r.evidence_id | rejected: false, identical text, tests green | none |
| 6 | DeepSeek PP-2 | PermissionError undefined | rejected: Python built-in | none |
| 7 | DeepSeek PP-3 | Reveal does not authenticate the caller | keep_plan: request ids are bearer by design (ptc1 C2); reveal still needs the owner's reveal grant | none |
| 8 | DeepSeek PP-4, Gemma kill shot 5 | Plain-text owner token in private graph | revise_plan (cheap) | ptc1b T4 |
| 9 | Gemma PP-1 | Cypher label injection | rejected: labels come only from constant tables; fact types validated before import | none |
| 10 | Gemma PP-2 | Grant not bound to offer_id | keep_plan: grants are request-scoped by design (PLAN A9); offer bound to owner and request; one reveal per request | none |
| 11 | Gemma PP-3 | Cached reveal skips state check | keep_plan: idempotent replay is C6; ptc1b T2 limits replay to approved or requested | ptc1b T2 |
| 12 | Gemma PP-4 | Owner id unvalidated in graph name | revise_plan (cheap) | ptc1b T5 |

Seat note: DeepSeek V4 Pro produced two fabricated "typo" cards on a corpus that passed live tests. Record for reviewer ablation.
