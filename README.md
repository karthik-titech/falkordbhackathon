# falkordbhackathon

FalkorDB Hackathon repo: Patch the Conference, San Francisco, 2026-10-24. FalkorDB track.

The app finds a warm way to meet a conference speaker (an investor or a sales prospect), with consent at every hop. FalkorDB holds the shared conference graph and one private graph per consenting attendee. Agents (seeker, broker, scorer, writer) hand off through graph nodes, and every answer can be traced to a graph path and a public source. The product name is still to be chosen; the UI shows "Name to come".

## Build log

Work prepared the evening before the event (2026-10-23, organizers confirmed pre-building is allowed):
specs and test contracts, public data prep (AI Engineer World's Fair 2026 schedule and speaker list, GitHub Universe 2026 talks), and the core build: graph store and seed loader, consent grants, the no-names reachability broker, route reveal, JEV fit scoring, sourced openers, the HTTP server, the requester and owner pages, and record and replay.

Work done at the event (2026-10-24): slide-style UI, local Docker FalkorDB setup, meeting memory (log a meeting into your own private graph; four review rounds to close privacy leaks), the one-page split screen with the owner's phone panel, and the product-name placeholder. In progress: JEV-chosen opener style and next move, investor-hook openers, and a four-way "who should I meet" view.

Every chunk is built against a pinned test contract, then gated on a live FalkorDB with hidden checks and independent review before it lands.

## How it works

The app finds public warm routes to conference speakers and brokers private reachability with separate owner grants for reachability and route reveal. It stores conference facts, requests, grants, offers, and agent actions in FalkorDB; owner token hashes, private evidence, names, and pending routes stay in each owner's private graph. Request ids are bearer access for this demo, except for a requester's own meeting memory, which every call must unlock with the requester's token. Each request permits one owner-rooted route reveal; revoking consent later does not retract that revealed route.

Limits: one server process, one GraphStore; the lock is not shared across processes.

`extract_features(store, request_id)` in `warmopen.features` returns abstract numbers and fixed goal/route labels. Missing or unmatched goal facts produce ordered gaps. `broker.revealed_route` reads only an approved snapshot.

`score_fit(store, request_id, jev)` in `warmopen.scoring` makes one decision call to the TypeSafe JEV model, validates the answers, and returns an **uncalibrated fit** band and value, or abstains. JEV receives abstract features only: numbers, booleans and fixed labels, never names, URLs or free text. Supports cite public graph evidence, route edges first.

`generate_openers(store, request_id, llm)` in `warmopen.openers` returns exactly three cues with public evidence ids and URLs taken from the graph, using templates on failure. Private evidence stays excluded after reveal. A valid citation does not prove generated text is supported, so the UI shows the cited claim with each cue.

Clients in `warmopen.jev` and `warmopen.llm` use urllib. Pass keys from environment variables; imports and construction make no network calls. The writer model uses `WARMOPEN_LLM_MODEL`, default `claude-haiku-5-5`. JEV choice questions use `criteria` maps, confirmed by the live probe in `docs/jev-probe.json`. Tests never invoke either provider.

## Run it

1. Start FalkorDB: `docker run -d --name falkordb -p 6379:6379 -p 3000:3000 falkordb/falkordb` (the FalkorDB Browser at http://localhost:3000 shows the live graph).
2. With Python 3.11+ and the `falkordb` client: `FALKORDB_HOST=localhost python3 -m pytest -q tests`.
3. Load and serve: `python3 -m warmopen.cli load <seed.json>`, then `python3 -m warmopen.cli serve --host 0.0.0.0 --port 8080`. The requester page with the owner's phone panel is `/`; a standalone owner page is at `/owner?owner=<owner-id>`.

The public seed in `data/` has no consented attendees; the demo seed with consenting owners is supplied separately. See [the runbook](docs/RUNBOOK.md) for the demo loop and fallbacks.

Use `serve --record recordings/demo` to save API responses, then `python3 -S -m warmopen.cli serve --replay recordings/demo` for stdlib-only offline replay. Responses to authenticated calls replay only to the same token. Both pages show **Recorded run**.

## License

Apache License 2.0. See [LICENSE](LICENSE).
