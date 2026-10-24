P0: None found.

**P1: Meeting recordings still disclose private meetings.** [app.py:132](warmopen/app.py:132) returns an authenticated meeting result without setting `auth_sha256`. The recording writer saves it at [app.py:295](warmopen/app.py:295), and replay accepts untagged records at [app.py:209](warmopen/app.py:209).

Reproduced through the HTTP handler with an in-memory store and recording sink: replaying `POST /api/meetings` with a matching requester/person body returned **200 and `category: "met"`**, both anonymously and with another owner’s token. This lets callers confirm guessed private meeting pairs.

Tag successful meeting recordings with the authenticated requester’s token hash, or exclude them from replay. Add anonymous and wrong-owner regression cases.

The four targeted paths pass:

| Check | Result |
|---|---|
| Creation, view, score, openers | Record the token hash; omit the raw header token |
| Replay and sticky view | Reject missing/wrong tokens and the digest presented as a token |
| Hash comparison | No bypass found for tagged records |
| Offline CLI | Runs under `-S`; no third-party imports |
| Earlier consent rules | No additional regression found |
| Frozen files | All 13 match their frozen copies |

P2: No additional confirmed findings.


**VERDICT: FIX-FIRST**
