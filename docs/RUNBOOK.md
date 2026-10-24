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
