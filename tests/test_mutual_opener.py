"""Mutual-person openers use only fully cited two-edge public paths."""

import copy
import json


def _seed_with_mutual_pair(seed):
    data = copy.deepcopy(seed)
    data["conferences"] = [{"id": "mutual_event", "name": "Mutual Event"}]
    data["people"].extend([
        {"id": "mutual_source", "name": "Alex Source", "kind": "attendee", "consented": False},
        {"id": "mutual_mediator", "name": "Morgan Mutual", "kind": "speaker", "consented": False},
        {"id": "mutual_target", "name": "Taylor Target", "kind": "speaker", "consented": False},
    ])
    data["talks"].extend([
        {"id": "mutual_talk_source", "title": "Systems Design", "conference": "mutual_event",
         "speakers": ["mutual_source", "mutual_mediator"], "evidence": "mutual_source_evidence"},
        {"id": "mutual_talk_target", "title": "Applied Graphs", "conference": "mutual_event",
         "speakers": ["mutual_mediator", "mutual_target"], "evidence": "mutual_target_evidence"},
    ])
    data["evidence"].extend([
        {"id": "mutual_source_evidence", "url": "https://example.org/event/source-talk",
         "claim": "Alex Source and Morgan Mutual presented Systems Design",
         "observed_at": "2026-10-20", "visibility": "public"},
        {"id": "mutual_target_evidence", "url": "https://example.org/event/target-talk",
         "claim": "Morgan Mutual and Taylor Target presented Applied Graphs",
         "observed_at": "2026-10-20", "visibility": "public"},
    ])
    return data


def test_two_cited_co_speaker_edges_create_a_mutual_opener(store, seed):
    from warmopen.app import _live
    from warmopen.seed import load_seed

    load_seed(store, _seed_with_mutual_pair(seed))
    captured = []

    def provider(payload):
        captured.append(payload)
        return None

    result = _live(store, "POST", "/api/conferences/mutual_event/conversation",
                   {"source": "mutual_source", "target": "mutual_target"},
                   None, provider, None)
    opener = result["ranked_openers"][0]
    assert opener["mutual_name"] == "Morgan Mutual"
    assert opener["mutual_person_id"] == "mutual_mediator"
    assert opener["text"] == (
        "I noticed we've both presented with Morgan Mutual. How do you know them?")
    assert set(opener["evidence_ids"]) == {"mutual_source_evidence", "mutual_target_evidence"}
    assert set(opener["evidence_ids"]) <= set(result["evidence"])
    assert result["opener_status"] == "mutual_route_first"
    abstract = json.dumps(captured[0], sort_keys=True)
    for ui_only in ("Morgan Mutual", "mutual_mediator", "mutual_source_evidence",
                    "mutual_target_evidence", "example.org"):
        assert ui_only not in abstract


def test_source_free_mode_never_invents_a_mutual_person(loaded):
    from warmopen.app import _live

    result = _live(loaded, "POST", "/api/conferences/ghu/conversation",
                   {"target": "vc_kay"}, None, None, None)
    assert all("mutual_name" not in item for item in result["ranked_openers"])
    assert all("How do you know them?" not in item["text"]
               for item in result["ranked_openers"])


def test_mutual_opener_requires_citations_on_both_route_edges():
    from warmopen.conversation import _opener_candidates

    evidence = {"first_edge": {"id": "first_edge", "url": "https://example.org/first",
                               "claim": "A cited public claim", "visibility": "public"}}
    context = {
        "source": "source", "target": "target", "public_names": {"middle": "Morgan"},
        "routes": [{"hops": 2, "persons": ["source", "middle", "target"], "edges": [
            {"category": "co_speaker", "evidence_id": "first_edge", "other_evidence_id": None},
            {"category": "co_speaker", "evidence_id": None, "other_evidence_id": None},
        ]}],
        "opener_evidence_ids": ["first_edge"], "opener_topic_matches": {},
    }
    candidates = _opener_candidates(context, evidence, [])
    assert all("mutual_person_id" not in item for item in candidates)
