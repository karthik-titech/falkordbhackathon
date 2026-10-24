**1. Contradictions and integration conflicts**

| Severity | Finding |
|---|---|
| **P2** | **The normal authentication error fails the frozen API assertion.** `_authenticate` raises `"Invalid owner token"`; HTTP handling returns its text. The test forbids the substring `"tok"`, including the word `"token"`. T3 needs explicit meeting-error sanitization while retaining status mapping. [consent.py:33](warmopen/consent.py:33), [app.py:254](warmopen/app.py:254), [test:112](tests/test_ptc4_met_memory.py:112). |

**2. Frozen assertions**

| Case | Normative assertion |
|---|---|
| Direct route | Initially no route; exact return object with computed meeting tie; route becomes `[me, eng_lee]`, category `met`, evidence `None`. [test:26](tests/test_ptc4_met_memory.py:26). |
| Public continuation | After removing the requester’s repository link, meeting `owner_a` creates `[me, owner_a, vc_kay]`; categories are `met`, `co_speaker`; public evidence remains `ev_talk_pair`. [test:39](tests/test_ptc4_met_memory.py:39). |
| Privacy | Without `request_id`, the serialized event dump remains equal; two other requester searches remain empty; the requester’s private dump contains the met person. This does not authenticate callers or prove which graphs were read. [test:55](tests/test_ptc4_met_memory.py:55). |
| Validation | Wrong-owner and missing tokens raise `PermissionError`; unknown, self, and private-only targets raise `ValueError`. No assertion checks absence of writes on failure. [test:68](tests/test_ptc4_met_memory.py:68). |
| Idempotence | Two identical calls without `request_id` leave identical private dumps. Event-log idempotence is not asserted. [test:83](tests/test_ptc4_met_memory.py:83). |
| HTTP | Wrong token yields 403 with no `"tok"` substring; success yields 200, expected tie and live mode; unauthenticated request creation returns the meeting route and display name. GET refresh and browser behavior are not exercised. [test:92](tests/test_ptc4_met_memory.py:92). |

**3. Missing tasks**

| Priority | Required addition |
|---|---|

**4. Ambiguities**

| Question | Evidence |
|---|---|

**5. Risks**

| Severity | Trigger and consequence |
|---|---|
| **P2** | A concurrent meeting can change route numbering during a scoring call. Features capture route choices before the provider call; `_introducer` resolves the returned ID against a fresh search afterward. The selected ID can then name a different path. [scoring.py:118](warmopen/scoring.py:118), [scoring.py:136](warmopen/scoring.py:136), [scoring.py:104](warmopen/scoring.py:104). |
