# Warm Open demo

Run live on Daytona. Use a phone hotspot first if venue wifi fails. Run laptop
replay second if the preview URL is unavailable. Replay needs Python 3.11+ and
the repo plus recording files. It needs no FalkorDB, provider keys, packages, or
external web assets.

## Prepare Daytona

Use the existing `warm-open-ptc` sandbox with FalkorDB and its approved Python
environment. Copy the repo there, excluding credentials and harness files.
Use the environment's Python (for example, activate `/opt/wo/bin/activate`).
The server uses the existing `falkordb` client. Do not install packages for replay.

| Variable | Use |
|---|---|
| `FALKORDB_HOST` | Live graph host, usually `127.0.0.1` within the sandbox |
| `FALKORDB_PORT` | Graph port, default `6379` |
| `TYPESAFE_JEV_API_KEY` | Optional live fit provider; absent means `jev_unavailable` |
| `ANTHROPIC_API_KEY` | Optional opener provider; absent means templates |
| `WARMOPEN_LLM_MODEL` | Optional Anthropic model override |
| `WARMOPEN_SEED` | Startup seed path, default `data/seed.json` |
| `PORT` | Sandbox script HTTP port, default `8080` |

Set credentials through the sandbox's environment controls. Never put provider
keys in files or command arguments. Owner tokens are entered only on the owner
page and kept in that browser tab's sessionStorage, separate from API recordings.

The data owner must supply `data/seed.json` with a requester and consenting
owners. The supplied `data/seed_public.json` has conference facts but no consented
attendees or private routes. It can validate speaker loading; it cannot run the
approval demo alone. Keep the curated seed local if it contains owner tokens or
private data. Do not invent consent or relationship evidence.

Load and start explicitly:

```sh
python3 -m warmopen.cli load data/seed.json
python3 -m warmopen.cli serve --host 0.0.0.0 --port 8080
```

Or use the startup script, which loads the seed only if the event graph is empty:

```sh
sh scripts/run_sandbox.sh
```

Expose port 8080 through the Daytona preview URL. Open that URL on the laptop.
Open `/owner?owner=<owner-id>` in a second browser and enter the owner's token.
Use one server process and one GraphStore for the server. Do not start a second
writer against the same graph namespace.

## Rehearse and record

Start a new recording directory for each rehearsal. Stop the prior server first:

```sh
python3 -m warmopen.cli serve --host 0.0.0.0 --port 8080 --record recordings/demo
```

1. Pick requester, target, and Invest or Product sales proposal. Select Find a path.
2. Inspect the public path and select an edge to open its evidence.
3. Select Ask owners. Each answer hides intermediate names.
4. In the second browser, approve reachability. In the first, select Ask owners again.
5. In the second browser, approve reveal. In the first, select that owner's Reveal.
6. Inspect the revealed route, select Score fit, then Openers. Read the source claims.
7. Select Send intro request. Confirm requested state and all four agents in the timeline.

The revealed route starts at the owner. The UI keeps the requester at the left,
without inventing a requester-to-owner graph hop. Only one reveal is allowed.
Grants expire after 15 minutes. Renew them in the owner page for a later rehearsal.

Every API response, including errors and polls, is saved as a numbered JSON file.
Headers and owner tokens are not recorded. Files contain request ids, source facts,
and any approved revealed names. Use only a consented demo run and keep recordings
local. Copy the completed `recordings/demo` directory to the laptop before the demo.

## Offline fallback

Enter the same requester token on the replay laptop for meeting and memory-aware
steps. Enter each owner's token on that owner's page for pending requests and
grant approvals in replay mode. Recordings contain only token hashes.

From the repo on the laptop:

```sh
python3 -S -m warmopen.cli serve --host 127.0.0.1 --port 8080 --replay recordings/demo
```

Open `http://127.0.0.1:8080` and the owner page in the second browser. Every JSON
response sets mode to recorded; both pages display **Recorded run**. Replay
matches method, path, and parsed JSON body, independent of object key order.
Repeat the same picks and actions as the rehearsal. Request ids come from the
recorded creation response. A different pick or missing recording returns
`not in recording`. Restart the server to reset replay consumption.

Each matching response is consumed in filename order. Request-detail polling
keeps returning its last response after exhaustion; other endpoints are finite,
including owner pending polls. Every authenticated response requires the same
requester or owner token used during recording.
Replay presents the saved responses, including any saved failed approvals. It
does not create grants or contact a database or provider.

## Pre-demo checklist

- Load the curated seed with the CLI and verify printed graph counts.
- Verify owner ids and tokens in a second browser, and test both grant scopes.
- Run `python3 -m pytest -q tests` in Daytona against live FalkorDB.
- Confirm public sources, fit wording, three opener cards, and timeline polling.
- Rehearse at 1280 px and phone width. Select source links and test one reveal only.
- Record the full loop; copy it locally and rehearse replay with external network off.
- Keep the phone hotspot ready, then use laptop replay if the preview remains unavailable.

Local checks without a graph or network:

```sh
python3 -m compileall -q warmopen
python3 -S -m scripts.check_offline
grep -rnE '<script[^>]+src="https?:|<link[^>]+href="https?:' warmopen/static
grep -rniE 'probability|innerHTML' warmopen/static
```

The two grep checks must print nothing (exit 1 means no match). Compilation and
offline checks do not replace the live graph gate or the two-browser rehearsal.
