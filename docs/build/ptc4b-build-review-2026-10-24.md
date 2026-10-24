P0: None found.

**P1: Recording/replay still exposes requester-private meetings.** Locations: [app.py:283](warmopen/app.py:283), [app.py:258](warmopen/app.py:258), [app.py:202](warmopen/app.py:202).

Recording saves authenticated responses unchanged. Replay matches method, path, and body without checking the caller’s token. Its sticky request cache preserves that exposure.

Reproduced with the real HTTP handler and an in-memory store and recording sink:

1. Alice’s authenticated request view includes her private `met` route.
2. Replay returns that recording without a token: **200, private route present**.
3. Another owner’s token receives the same cached route: **200, private route present**.

Exclude private-memory responses and derived results from replayable recordings, or enforce caller authorization during replay. Removing only `met` edges would leave names and score-derived disclosures.

| Reviewed path | Result |
|---|---|
| POST requests; GET request detail | Live authorization fix holds |
| Score; openers | Missing and other-owner tokens caused zero private-memory reads |
| Reachability; reveal | Separate grants and offer binding remain enforced |
| Owner pending | Authenticated; explicit fields exclude meeting routes |
| Recording/replay | **P1 remains open** |
| UI tokens | SessionStorage only; polling, score, and openers send the request creator’s token |

P2: No additional confirmed findings.


**VERDICT: FIX-FIRST**
