# Local demo runbook

## Public trial

Start the no-signup trial:

```sh
docker compose up --build
```

Open <http://localhost:8080>. Choose a conference, then enter your own
LinkedIn and X links or skip to the directory. With explicit consent, Continue
uses Bright Data to retrieve professional profile information and match interests
to conference topics. The directory labels
confirmed attendees and scheduled speakers separately. The public graph
explorer at `/explore` needs no credentials and does not authenticate as a
speaker or send an introduction. The web port is bound to the local machine.
A public organizer URL needs a separate HTTPS deployment.

Profile enrichment needs `BRIGHTDATA_API_KEY`. Additional public website research
uses `BRIGHTDATA_ZONE`, and indexed public mention search uses
`BRIGHTDATA_SERP_ZONE`. Pass secrets through the process environment or a private
deployment secret facility; the public image contains none. Missing configuration
produces an unavailable status rather than fabricated research. The profile
Scraper API does not require a zone. Use names and company information to verify
profile candidates before importing any links; never guess social handles.

Stop the trial with `Ctrl-C`. Docker Compose keeps its graph data in a named
volume when containers stop.

## Load sourced attendance

Use a permitted organizer roster or public professional announcements. See
[attendee import](attendee-import.md) for the manifest format and its rules.
Keep the manifest outside the repository if it contains private information.

Stop the app before importing into its graph:

```sh
docker compose stop web
docker compose run --rm -v "$ATTENDEE_MANIFEST:/input/attendees.json:ro" web python -m warmopen.cli import-attendees /input/attendees.json --check
```

Review the validation summary. To apply the complete snapshot, run the same
command without `--check`, then restart the app:

```sh
docker compose run --rm -v "$ATTENDEE_MANIFEST:/input/attendees.json:ro" web python -m warmopen.cli import-attendees /input/attendees.json
docker compose up -d web
```

Attendance records establish only conference attendance. They do not add
relationships or grant access to anyone's private graph. Do not invent
attendance, consent or relationship evidence.

## Configure a full consent demo

The requester and owner pages are available at `/workspace` and `/owner`. A full demo
requires conference data plus consenting owner records and credentials supplied
by the data owner. Keep those files and credentials outside the public speaker
dataset and repository. The owner page accepts its owner's token; each owner
must separately approve reachability and route reveal.

An optional Decisions service can be configured for uncalibrated fit. The
service reads `DECISIONS_API_KEY` from its environment; pass the value through
the deployment's secret environment facility, never as a literal in a command
or file. Without that service, the app keeps graph-based ordering and abstains
from scoring. Opening lines can still use sourced templates.

For a full journey, select a requester, target and goal; inspect a supported
route; ask an owner for reachability; have that owner approve; ask again; then
request route reveal and approve it separately. Review the sources and fit
label before sending an intro request. Sending records an app request and does
not send an external message. Each request permits one owner-rooted reveal;
grants expire after 15 minutes.

Private first-hop meeting information is used only when the request opts into
memory and the same API call includes the requester's token. Request IDs act as
bearer access in this demo. A route already revealed remains visible in that
request if consent is later revoked.

## Record and replay a demo

Recordings can contain request IDs, source facts and approved route details.
Keep them local and use only a consented demo. Start a live recording with a
new, empty directory. Stop the public-trial server first and choose a new
recording path if that directory already contains files:

```sh
docker compose stop web
mkdir recordings/demo
docker compose run --rm --service-ports -v "$PWD/recordings/demo:/recordings" web python -m warmopen.cli serve --host 0.0.0.0 --port 8080 --record /recordings
```

Stop the live service before replay:

```sh
docker compose stop web
docker compose run --no-deps --rm --service-ports -v "$PWD/recordings/demo:/recordings:ro" web python -S -m warmopen.cli serve --host 0.0.0.0 --port 8080 --replay /recordings
```

Replay needs no graph or Decisions service. Repeat the recorded actions,
including target and conference selections. Authenticated calls require the
same token used during recording; recording files contain a credential hash,
not the token. Both pages display **Recorded run**.

## FalkorDB Cloud

Set `FALKORDB_URL` in your private environment file to the full `falkors://` URL.
Docker Compose passes it only to the web service. When configured, the app uses
TLS and the `wo_event` public graph; owner graphs retain their separate namespaces.
The small `conference` setup graph remains a separate synthetic example.
Explicit host and port arguments still select the local database for isolated tests.

To copy an already-loaded local public event graph to the configured cloud database,
mount the private environment file read-only and run `python -m scripts.import_cloud`
from the repository inside the Docker image, with `CONFERENCE_ENV_FILE` pointing to
that file. The import merges bounded batches without copying private owner graphs.
Cloud startup skips the bundled seed load; import before starting the web service.
Unset `FALKORDB_URL` to use the local Compose database and automatic seed loading.


The public map bundles the official `@falkordb/canvas` 0.3.3 locally. Its 3D mode
requires WebGL2; a device without it gets a labeled 2D canvas. The SVG fallback
is used only if the component cannot initialize. Search and the accessible roster
remain available. The Node package build runs in Docker; no host packages or CDNs
are needed at runtime. The dependency lock and licenses are in the vendor folder.

The historical frozen product-name test pins the temporary placeholder. Once the
maintainer chose the product name, that exact placeholder assertion became stale;
keep the frozen file unchanged and report that failure separately from regressions.


## Professional speaker research

The Docker image includes `scripts/research_github_profiles.py`. Supply a private
manifest of verified public professional URLs and run it with `--report` pointing
to a mounted output directory. It fetches each eligible URL once, checks the
speaker's name, and writes cited profile/topic evidence and per-person research
status into FalkorDB. It uses ordinary public HTTP fetching, not the Bright Data
personal-profile scraper. Conference-only evidence is marked separately from an
individual professional bio. Personal social URLs are excluded from this batch.

## Voice playback

Opening lines and follow-up drafts have an on-demand Listen control. The server
uses the same configured OpenAI credential as Decisions, via `DECISIONS_API_KEY`;
the browser never receives the credential. Speech uses a separate Audio API call,
not the abstract-feature decision model. Requests contain only the selected text
(up to 800 characters), use a fixed voice/model, and return MP3 with no-store.
Speech requests and audio are excluded from app recordings. Playback does not
request microphone access. The UI labels the output as AI-generated voice.

The adapter currently uses `gpt-4o-mini-tts` on `/v1/audio/speech`. OpenAI documents
its shutdown on January 6, 2027; migrate this adapter to Realtime before then.
See [OpenAI speech documentation](https://developers.openai.com/api/docs/guides/text-to-speech).

## Voice-created follow-up actions

The conference page has a microphone and typed-command fallback. A bounded
20-second recording is transcribed by OpenAI (`gpt-transcribe`); the transcript
is shown and interpreted as a follow-up request. A unique named conference person
and one channel are required. Unknown or ambiguous names never silently resolve
to the currently selected person. The assistant replies and can read its reply.

Follow-ups live in the requester's token-authenticated private FalkorDB graph:
`(:Person {id:'you'})-[:HAS_ACTION]->(:FollowUp)-[:ABOUT]->(:Contact)`.
A spoken claim that the user connected on LinkedIn is stored privately as
`CONNECTED_ON` with `basis='requester_reported'`, never as a verified public edge.
Every read/write requires the same-call session credential. These calls and raw
recordings are excluded from app recordings; audio uploads are held in memory.
The session credential stays in browser session storage; retain that tab/session
to keep access. The public conference graph and Decisions payload stay separate.

Pending actions appear as orange squares in the local graph view and in My
follow-up actions. Mark done closes them. Relative intervals and today/tomorrow
can set a time; explicit local dates are converted to timezone-aware timestamps.
An optional calendar download carries a reminder; no background notifications,
LinkedIn messages, email, or SMS are sent by this feature.
