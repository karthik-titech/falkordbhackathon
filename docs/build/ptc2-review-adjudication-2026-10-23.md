# ptc2 review adjudication (2026-10-23)


| # | Source | Card | Ruling | Route |
|---|---|---|---|---|
| 1 | Gate seat probe, DeepSeek PP-1, Gemma PP-3 | JEV criteria must be a choice map | revise_plan | ptc2b T1-T3 |
| 2 | DeepSeek PP-2 | Prompt injection through claim text | keep_plan: claims come from the curated seed; output gated on allowed evidence id, graph URL, 280 chars; known limit C5 | none |
| 3 | DeepSeek PP-3 | Introducer not checked against allowed list | keep_plan: spec maps unknown ids to introducer None | none |
| 4 | Gemma PP-1 | Abstract-label regex unanchored | rejected: code uses fullmatch with \Z (scoring.py:26, 36) | none |
| 5 | Gemma PP-2 | Zero-evidence crash in openers | rejected: fill loop handles empty evidence (openers.py:63-64); frozen test covers it | none |
