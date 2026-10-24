"""Per-session own-profile graphs stay private and require the returned token."""

import hashlib

import pytest

from warmopen.profile_sessions import create_profile_session, read_profile_session


def test_profile_session_creates_private_you_node_sourced_topics_and_token_hash_only(store):
    session = create_profile_session(store, [{
        "id": "agents",
        "name": "AI agents",
        "sources": [{"url": "https://linkedin.com/in/owner", "platform": "linkedin"}],
    }])

    assert session["id"]
    assert session["token"]
    assert session["node_id"] == "you"
    assert session["name"] == "You"
    assert session["interests"] == [{
        "id": "agents",
        "name": "AI agents",
        "evidence_ids": session["interests"][0]["evidence_ids"],
        "sources": [{"url": "https://linkedin.com/in/owner", "platform": "linkedin"}],
    }]
    assert len(session["interests"][0]["evidence_ids"]) == 1

    private_graph = store.private(session["id"])
    person_rows = store.query(private_graph, "MATCH (p:Person {id: $id}) RETURN p.name", {"id": "you"}).result_set
    assert person_rows == [["You"]]
    edge_rows = store.query(
        private_graph,
        "MATCH (p:Person {id: $person})-[r:INTERESTED_IN]->(t:Topic) "
        "RETURN t.id, t.name, r.evidence_id",
        {"person": "you"},
    ).result_set
    assert edge_rows == [["agents", "AI agents", session["interests"][0]["evidence_ids"][0]]]
    evidence_rows = store.query(
        private_graph,
        "MATCH (e:Evidence) RETURN e.url, e.claim, e.visibility",
    ).result_set
    assert evidence_rows == [[
        "https://linkedin.com/in/owner",
        "Own profile professional text includes a conference topic label.",
        "private",
    ]]
    credential_rows = store.query(
        private_graph,
        "MATCH (c:ProfileSessionCredential {id: $id}) RETURN c.token_sha256",
        {"id": session["id"]},
    ).result_set
    assert credential_rows == [[hashlib.sha256(session["token"].encode("utf-8")).hexdigest()]]
    assert session["token"] not in repr(store.dump(graph=private_graph))
    assert store.query(store.event(), "MATCH (p:Person {id: $id}) RETURN p.name", {"id": "you"}).result_set == []


def test_read_profile_session_authenticates_then_returns_only_its_own_private_context(store):
    created = create_profile_session(store, [{
        "id": "graphs",
        "name": "Graph databases",
        "sources": [{"url": "https://x.com/owner", "platform": "x"}],
    }])
    read = read_profile_session(store, created["id"], created["token"])
    assert read == {
        "id": created["id"],
        "node_id": "you",
        "name": "You",
        "interests": created["interests"],
    }


@pytest.mark.parametrize(("session_id", "token"), [
    ("missing-session", "wrong-token"),
    ("../event", "wrong-token"),
])
def test_unknown_sessions_and_invalid_tokens_raise_permission_error(store, session_id, token):
    with pytest.raises(PermissionError):
        read_profile_session(store, session_id, token)


def test_wrong_token_does_not_read_private_topic_context(store):
    created = create_profile_session(store, [{
        "id": "agents",
        "name": "AI agents",
        "sources": [{"url": "https://x.com/owner", "platform": "x"}],
    }])
    with pytest.raises(PermissionError):
        read_profile_session(store, created["id"], created["token"] + "wrong")
