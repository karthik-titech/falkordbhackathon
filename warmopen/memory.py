"""Owner-authenticated meetings stored only in the owner's private graph."""

from .consent import _authenticate
from .ties import tie_strength


def log_meeting(store, requester, requester_token, person):
    with store.lock:
        _authenticate(store, requester, requester_token)
        rows = store.query(store.event(),
                           "MATCH (p:Person {id: $id}) WHERE p.kind IS NOT NULL "
                           "RETURN p.name", {"id": person}).result_set
        if not rows or person == requester:
            raise ValueError("Meeting needs another public person")
        strength, source = tie_strength({"met_today": True})
        store.query(store.private(requester),
                    "MERGE (a:Person {id: $requester}) "
                    "MERGE (b:Person {id: $person}) SET b.name = $name "
                    "MERGE (a)-[r:KNOWS {category: 'met'}]->(b) "
                    "SET r.strength = $strength, r.strength_source = $source, "
                    "r.evidence_id = null",
                    {"requester": requester, "person": person, "name": rows[0][0],
                     "strength": strength, "source": source})
        return {"requester": requester, "person": person, "category": "met", "tie": strength}
