Warm Open finds public warm routes to conference speakers and brokers private reachability with separate owner grants for reachability and route reveal. It stores conference facts, requests, grants, offers, and agent actions in FalkorDB; owner token hashes, private evidence, names, and pending routes stay in each owner's private graph. With Python 3.11+, the `falkordb` client, `pytest`, and a running FalkorDB, run `FALKORDB_HOST=localhost FALKORDB_PORT=6379 python3 -m pytest -q tests/test_ptc1_core.py` from this directory. Load a seed with `load_seed(GraphStore.connect(), seed)` from `warmopen.seed` and `warmopen.graphstore`. Request ids are bearer access for this demo. Each request permits one owner-rooted route reveal; revoking consent later does not retract that revealed route.

Limits: one server process, one GraphStore; the lock is not shared across processes.

`extract_features(store, request_id)` in `warmopen.features` returns abstract
numbers and fixed goal/route labels. Link counts count distinct undirected
person links on the returned public routes. Missing or unmatched goal facts
produce ordered gaps. `broker.revealed_route` reads only an approved snapshot.

`score_fit(store, request_id, jev)` in `warmopen.scoring` makes one decision call,
validates both answers, and returns an **uncalibrated fit** band and value, or
abstains. Supports cite public graph evidence, route edges first. The first
ordered gap supplies the single `would_improve` suggestion; no gaps means none.
`generate_openers(store, request_id, llm)` in `warmopen.openers` returns exactly
three cues with public evidence ids and graph URLs, using templates on failure.
Private evidence stays excluded after reveal. For a cue with no evidence, display
**No source: general opener**. A valid citation does not prove generated text is
supported. Present the cited claim with each cue in the UI.

Clients in `warmopen.jev` and `warmopen.llm` use urllib. Pass keys from environment
variables to their factories; imports and construction make no network calls.
The writer model uses `WARMOPEN_LLM_MODEL`, default `claude-haiku-5-5`.
JEV choice questions use `criteria` maps, confirmed by the live probe in
`docs/jev-probe.json`. Tests never invoke either provider.

Run the full gate with `python3 -m pytest -q tests` against live FalkorDB.
Without the client/server, run `python3 -m compileall -q warmopen`; this checks
syntax only and does not replace the live gate.

Load and serve with `python3 -m warmopen.cli load data/seed.json`, then
`python3 -m warmopen.cli serve --host 0.0.0.0 --port 8080`. The requester page
is `/`; owner approvals are at `/owner?owner=<owner-id>` in a second browser.
The supplied public seed has no consented attendees; the data owner supplies
the curated demo seed. See [the runbook](docs/RUNBOOK.md) for sandbox setup,
the full demo loop, and fallbacks.

Use `serve --record recordings/demo` to save API responses. Copy the recording
to the laptop, then run `python3 -S -m warmopen.cli serve --replay recordings/demo`
for stdlib-only offline replay. Both pages show **Recorded run**. Replay matches
method, path, and JSON body. Restart replay to reset consumed responses.
