"""Conference match buckets use cited topics and public routes without a model."""

import copy


def _adjacent_topic_seed(seed):
    data = copy.deepcopy(seed)
    data["conferences"] = [{"id": "matches_event", "name": "Matches Event"}]
    data["topics"].extend([
        {"id": "building_agents", "name": "Building AI agents"},
        {"id": "agent_security", "name": "Agent security"},
    ])
    data["people"].append({"id": "matches_source", "name": "Source Builder",
                            "kind": "attendee", "consented": False})
    data["talks"].extend([
        {"id": "source_topic_talk", "title": "Building agents", "conference": "other_event",
         "speakers": ["matches_source"], "topics": ["building_agents"],
         "evidence": "source_topic_evidence"},
        {"id": "target_topic_talk", "title": "Agent security", "conference": "matches_event",
         "speakers": ["vc_kay"], "topics": ["agent_security"],
         "evidence": "target_topic_evidence"},
    ])
    data["evidence"].extend([
        {"id": "source_topic_evidence", "url": "https://example.org/matches/source",
         "claim": "Source Builder presented Building AI agents", "observed_at": "2026-10-20",
         "visibility": "public"},
        {"id": "target_topic_evidence", "url": "https://example.org/matches/target",
         "claim": "Kay Investor presented Agent security", "observed_at": "2026-10-20",
         "visibility": "public"},
    ])
    return data


def test_adjacent_topics_are_sourced_unexpected_matches(store, seed, monkeypatch):
    from warmopen.app import _live
    from warmopen.seed import load_seed

    load_seed(store, _adjacent_topic_seed(seed))
    monkeypatch.setattr(store, "private", lambda *_: (_ for _ in ()).throw(
        AssertionError("match classification read a private graph")))
    result = _live(store, "POST", "/api/conferences/matches_event/matches",
                   {"source": "matches_source"}, None, None, None)
    assert result["total_count"] == 1
    assert result["unclassified_count"] == 0
    match = result["items"][0]
    assert match["id"] == "vc_kay"
    assert match["category"] == "unexpected_connection"
    assert match["reason"] == "The cited professional topics are adjacent."
    assert match["topics"] == [{
        "source": {"id": "building_agents", "name": "Building AI agents"},
        "target": {"id": "agent_security", "name": "Agent security"},
        "relation": "related",
    }]
    assert set(match["evidence_ids"]) == {"source_topic_evidence", "target_topic_evidence"}
    assert set(match["evidence_ids"]) <= set(result["evidence"])


def test_exact_interest_and_seeking_keep_their_higher_priority_buckets(store, seed):
    from warmopen.proximity import conference_matches
    from warmopen.seed import load_seed

    load_seed(store, _adjacent_topic_seed(seed))
    mirror = conference_matches(store, "matches_event", interest_topic_ids=["agent_security"])
    assert mirror["items"][0]["category"] == "mirror"
    sought = conference_matches(store, "matches_event", seeking_topic_ids=["agent_security"])
    assert sought["items"][0]["category"] == "missing_piece"
