P0: None found.

**P1: Shared request IDs expose requester-private meetings to other callers.** Locations: [app.py:65](warmopen/app.py:65), [app.py:143](warmopen/app.py:143), [app.py:152](warmopen/app.py:152), [app.py:161](warmopen/app.py:161).

Failing scenario:

1. Alice creates a request with her valid token, enabling `use_own_memory`, then asks Bob for an introduction.
2. Bob’s authenticated pending list gives him Alice’s request ID.
3. Bob calls `GET /api/requests/<id>` without Alice’s token. The response includes Alice’s private `met` edges and route names.
4. Bob can also POST `/score`. It reads Alice’s memory, sends derived features to JEV, and returns the selected introducer. Later meetings can appear through the same request ID.

Confirmed with an in-memory store fixture running the real handler, path, feature, and scoring code. Both missing and wrong tokens returned the meeting edge; unauthenticated scoring selected its destination.

C2 is implemented literally. However, combining it with ptc1’s bearer-request rule conflicts with ptc4’s privacy goal and C5: Bob receives meeting information without Alice’s reachability or reveal grants. Request-ID guessing is unnecessary.

Fix: require requester authentication before any request view, scoring, or opener operation consumes own memory. Update the UI to supply that credential on those calls.

P2: No additional confirmed findings.


**VERDICT: FIX-FIRST**
