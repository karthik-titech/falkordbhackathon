"""A failed profile fetch still gives the requester an empty private You node."""

from warmopen.app import _live
from warmopen.brightdata_profiles import ProfileProviderError
from warmopen.profile_sessions import read_profile_session


def test_provider_failure_does_not_block_private_you_node_creation(store, seed):
    from warmopen.seed import load_seed

    load_seed(store, seed)
    def unavailable(*args):
        raise ProfileProviderError("provider_unavailable")

    result = _live(store, "POST", "/api/profile/enrich", {
        "conference_id": "aie", "consent": True,
        "linkedin": "https://www.linkedin.com/in/owner",
    }, None, None, None, profile_client=unavailable)
    assert result["status"] == "provider_error"
    session = result["profile_session"]
    saved = read_profile_session(store, session["id"], session["token"])
    assert saved["name"] == "You"
    assert saved["interests"] == []
    assert store.query(store.event(), "MATCH (n:Person {id: 'you'}) RETURN n").result_set == []
