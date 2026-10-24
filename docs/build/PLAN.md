# the app: build plan (ptc1, ptc2, ptc3)

Author: Claude (Opus 5.5, planner seat), 2026-10-23. Product picked by joint debate (Claude + Sol 6.1, consensus, 2 rounds, 2026-10-23). Goals picked by Karthik 2026-10-23: **invest** and **sales** (product sales proposal).

Event: Patch the Conference hackathon, Sat 2026-10-24, 625 2nd St San Francisco. Build 11:00 to 17:30, live demo 17:30. Solo. FalkorDB lane.

## Product in one line

Name a speaker you want to reach and why (invest or sales). Agents find the warmest consented path, score your fit with reasons, and hand you three sourced openers. Every step is a graph query you can see.

## Done means

| # | Success criterion | Checked by |
|---|---|---|
| 1 | Requester picks target + goal, gets up to 3 public warm routes with evidence per hop | ptc1 frozen tests + demo |
| 3 | Reveal needs a separate reveal grant from a second browser with the owner token | ptc1 + ptc3 frozen tests |
| 4 | One JEV call returns fit band + introducer choice; abstains on low confidence; JEV sees abstract features only | ptc2 frozen tests |
| 5 | Exactly 3 openers, each citing a public evidence node with URL when one exists (else labeled "No source: general opener"); uncited LLM cues dropped; template fallback | ptc2 frozen tests |
| 6 | Agent handoffs visible as AgentEvent nodes in the shared graph and as a timeline in the UI | ptc1 + ptc3 |
| 7 | Live run on Daytona preview URL; labeled "Recorded run" replay fallback | ptc3 + rehearsal |
| 8 | Both datasets loaded: GitHub Universe 2026 and an AI Engineer conference schedule | data prep (Claude, not builder) |

## Chunks

| Tag | Spec | Scope | Builder | Risk |
|---|---|---|---|---|
| ptc1 | `ptc1-graph-core.spec.txt` | Repo skeleton, GraphStore, seed loader, tie formula, public paths, consent grants, broker, request state machine, agent log | Sol 6.1 | crypto (authorization) |
| ptc2 | `ptc2-score-openers.spec.txt` | Feature extraction, gap query, JEV client + fit scoring, opener generation + validation | Sol 6.1 | standard |
| ptc3 | `ptc3-app-ui-replay.spec.txt` | Stdlib HTTP server, requester UI, owner UI, lit path SVG, agent timeline, record/replay, sandbox run script | Sol 6.1 | standard |

Order: ptc1, then ptc2, then ptc3, serialized (Astra review 2026-10-23).

## Work that is not the builder's (Claude and Karthik)

| Item | Owner | When |
|---|---|---|
| Create private repo `karthik-titech/warm-open` | Karthik approves, Claude runs `gh repo create --private` | Tonight |
| Daytona sandbox with FalkorDB running; confirm `redis-cli -p 6379 GRAPH.QUERY t "RETURN 1"` | Claude, verified tonight | Tonight |
| Data prep: AI Engineer schedule via the ai-engineer MCP `get_schedule`; GitHub Universe 2026 schedule if published; normalize to the seed format in ptc1 T2 | Claude | Tonight |
| Speaker evidence: public talk pages, repos, company, fund thesis, with source URLs | Claude | Tonight |
| The two consenting middle-hop people (open Q2) | Karthik | Before 11:00 Sat |
| Rehearsal x3 and a recorded run | Karthik | 16:30 to 17:15 Sat |

## Hour budget (if pre-building is not allowed)

| Block | Work |
|---|---|
| 11:00 to 12:15 | ptc1 build + gate |
| 12:15 to 13:30 | ptc2 build + gate |
| 13:30 to 15:00 | ptc3 build + gate |
| 15:00 to 16:00 | Panel, fixes (ptc*b) |
| 16:00 to 16:30 | Deploy to Daytona, load real seed |
| 16:30 to 17:15 | Rehearse, record fallback |

## ASSUMPTIONS AND OPEN QUESTIONS

| ID | Item | Default if unanswered |
|---|---|---|
| A1 | Hackathon rules on code written before the event are not published | Ask organizers at 09:00. If pre-build is allowed, build tonight; if not, follow the hour budget. Spec and data prep are fine either way. |
| A3 | Consent grants are authorization, which the gate table puts at crypto tier | RESOLVED 2026-10-23: ptc1 is crypto tier (Astra review + full panel); ptc2 and ptc3 standard. |
| A5 | EmbeddingGemma and Perplexity embeddings | Cut from v1 (debate: Sol cut list item 2). No full-text search either: the target picker filters client side (Astra C6). Stretch chunk ptc4 if time is left. |
| A6 | Opener LLM | Anthropic Messages API, model from env `WARMOPEN_LLM_MODEL`, default `claude-haiku-5-5`, via stdlib `urllib`. |
| A8 | Q2: who are the two consenting middle-hop people | Seed placeholders `owner_a`, `owner_b`; swap names at 10:30 Sat. |
| A10 | Gigi is a real company | No Gigi name or branding anywhere in the repo or UI. |
| A11 | JEV fit score is not a calibrated probability | UI label "uncalibrated fit", never "probability" or "chance". Frozen test enforces the key name. |

| A12 | Replay fallback needs no network | RESOLVED: recorded mode is stdlib-only and runs on the laptop offline (ptc3 C1). Phone hotspot is the first fallback. |
