# Target-centered conference journey

The selected speaker stays the goal throughout the journey. Suggested
attendees are possible intermediaries, not replacement targets.

## Product flow

The public entry point starts with a conference directory. Visitors can enter
their own LinkedIn and X profile links or continue without them. Explicit consent
and Continue trigger Bright Data profile retrieval. Only professional fields are
used to match existing conference topics. Raw profile responses are not stored;
the browser keeps the resulting topic context and can clear it. Profile research
does not prove identity or create private-graph consent. Personal profile
enrichment calls are excluded from API recordings.

Conference pages separate confirmed attendance from scheduled speaking
appearances, with public source links. The public explorer compares two selected
graph profiles without treating either selection as the visitor's identity.
With personal interest topics, route evidence from an unrelated demonstration
profile is excluded. Users choose sought capabilities explicitly.

The conference map draws only sourced relationships, and displays a separate
outer group for people without a supported path in that view. Categories and
conversation scores abstain when their evidence requirements are not met.
Decisions receives counts and fixed labels, including bounded mention-tone
summaries; profile text, posts, names and URLs stay outside its input. Public
mentions are context rather than verified reputation or relationship evidence.

1. Choose the intended speaker and the conference.
2. If you confirm that you are physically near the speaker, review sourced
   opening lines. Conference attendance alone does not establish proximity.
3. Otherwise, explore supported relationship paths of up to six degrees through
   confirmed attendees.
4. If you could not connect, review future conferences with confirmed speaker
   attendance and attending connections who could support a warm approach.

## Evidence and permissions

Conference attendance needs a public professional source URL and claim. A
speaker listing in the public dataset is not proof of attendance at a specific
conference. Shared attendance does not establish friendship. Unknown attendance
produces an empty state rather than a predicted visit.

Public routes use supported graph relationships. A requester's private first hop
is available only when the request opts into meeting memory and the same API call
includes the requester's valid token. Other owners' private graphs require their
separate approval for reachability and route reveal. Authenticated recordings
remain bound to the credential hash.

Request IDs act as bearer access in this demo. A route approved for reveal stays
visible in that request if consent is later revoked. Each request allows one
owner-rooted route reveal.

## Decision and source handling

The decision service ranks anonymous route choices from abstract features such
as hop count, supported-edge count and confirmed attendance. Names, person or
conference identifiers, source URLs and claims are excluded from its input. Fit
is labeled **uncalibrated fit**; it is not a calibrated probability. If scoring
is missing, invalid or unavailable, the app uses a clearly identified graph
ordering.

Opening lines cite public graph evidence. A citation lets a person inspect the
supporting source; it does not by itself prove that every generated phrase is
supported. Private evidence is excluded from public opening lines.
