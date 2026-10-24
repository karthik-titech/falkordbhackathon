# Conference connection planner

Explore public connections around conference speakers and plan a consent-based
introduction. The app keeps the intended speaker fixed as you explore possible
ways to meet them.

## Try it

Run the no-signup public trial with Docker Compose:

```sh
docker compose up --build
```

Open <http://localhost:8080> and choose a conference. Add your own LinkedIn
and X profile links or skip that step to try the demo without signup. With your
explicit consent, Bright Data retrieves public professional information and
matches it to conference topics. You can review the interests and separately
choose what you are looking for. This does not establish your graph identity.

Browse confirmed attendees and scheduled speakers under separate labels. The
bundled data is a sourced speaker dataset, not a confirmed attendee roster.
The conference people map centers on a selected profile and shows sourced public
connections. Click a person to explore their neighborhood and inspect the sources.
Graph distance describes connections within the conference graph, not physical
location. A searchable list remains available alongside the map.
The public connection explorer is available at `/explore`; selecting a profile
there does not authenticate as that person or send an introduction. No provider
credentials or private demo data are needed for the public trial.

Select a target to see whether the evidence supports a mirror, missing piece,
or unexpected connection. Research and assessment run only when requested.
Click **Help me start a conversation** to get three ranked opening lines first,
with public sources where available. Conversation fit is uncalibrated. When the
model cannot assess a match, a separately labeled rough starting estimate uses
available evidence counts; it is not a prediction of friendship.
Public post tone is summarized as context, not a verified assessment of a person.

## Plan a conference conversation

Choose a target and conference. If you confirm that you are physically near the
target, the app offers sourced opening lines. Otherwise, it finds supported
relationship paths of up to six degrees through confirmed attendees. If you
could not connect, it can show future conferences with confirmed target
attendance and an attending connection. Each attendance fact needs a public
source; shared attendance does not establish a relationship.

Private reachability and route details require the relevant person's consent.
Each owner approves reachability and route reveal separately. Private meeting
memory is available only when the requester's valid token accompanies that call.
Request IDs are bearer access in this demo. An approved route remains visible
after consent is later revoked.

Where scoring is available, the app labels it **uncalibrated fit**. The decision
service receives abstract numbers, booleans and fixed labels, never names,
identifiers, URLs or free text. Missing or unavailable scoring falls back to
graph-based ordering. Opening lines include public source links and claims so
you can check their support.

## More information

- [Target journey and privacy](docs/architecture.md)
- [Conference attendance imports](docs/attendee-import.md)
- [Local demo runbook](docs/RUNBOOK.md)

## License

Apache License 2.0. See [LICENSE](LICENSE).
