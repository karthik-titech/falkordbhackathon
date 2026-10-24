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
and X profile links or skip that step to try the demo without signup. Links stay
in your browser session; this version does not fetch those profiles or match
them to a graph identity.

Browse confirmed attendees and scheduled speakers under separate labels. The
bundled data is a sourced speaker dataset, not a confirmed attendee roster.
The public connection explorer is available at `/explore`; selecting a profile
there does not authenticate as that person or send an introduction. No provider
credentials or private demo data are needed for the public trial.

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
