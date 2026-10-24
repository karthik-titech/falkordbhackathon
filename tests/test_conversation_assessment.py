"""Public conversation fit is evidence-gated and model inputs stay abstract."""

import copy
import json

import pytest


def _sourced_seeking_seed(seed):
    data = copy.deepcopy(seed)
    data["conferences"] = [{"id": "ghu", "name": "Graph Gathering"}]
    data["startups"][0]["evidence"] = "conversation_startup"
    data["startups"][0]["seeking"] = ["graphs"]
    data["edges"].append({"type": "FOUNDED", "from": "me", "to": "s_me",
                          "evidence": "conversation_startup"})
    data["evidence"].append({"id": "conversation_startup", "url": "https://example.org/startup/seeking",
                             "claim": "My Startup is seeking graph expertise", "observed_at": "2030-05-01",
                             "visibility": "public"})
    return data


def _decision(choice_type="mirror", confidence=0.8, fit_choice="high"):
    probabilities = {"high": 0.6, "medium": 0.3, "low": 0.1,
                     "INSUFFICIENT_EVIDENCE": 0.0}
    answers = {}
    for name in ("conversation_fit", "mirror_fit", "missing_piece_fit", "unexpected_connection_fit"):
        answers[name] = {"choice": fit_choice, "confidence": confidence,
                         "probabilities": probabilities}
    answers["connection_type"] = {
        "choice": choice_type, "confidence": confidence,
        "probabilities": {"mirror": 0.8, "missing_piece": 0.1,
                          "unexpected_connection": 0.05, "unknown": 0.05},
    }
    answers["opener"] = {"choice": "candidate_1", "confidence": confidence,
                         "probabilities": {"candidate_1": 0.8, "candidate_2": 0.1,
                                           "candidate_3": 0.1, "INSUFFICIENT_EVIDENCE": 0.0}}
    return {"answers": answers}


def test_own_topic_context_never_borrows_a_demo_route(loaded):
    from warmopen.conversation import public_pair_context

    context = public_pair_context(loaded, None, "vc_kay", interest_topic_ids=["graphs"])
    assert context["connection_type"] == "mirror"
    assert context["features"]["source_listed"] is False
    assert context["features"]["cited_route_count"] == 0
    assert context["reason"] == "The target has cited work matching your selected interests."


def test_category_gates_prefer_sourced_seeking_then_mirror_then_route(store, seed):
    from warmopen.conversation import public_pair_context
    from warmopen.seed import load_seed

    load_seed(store, _sourced_seeking_seed(seed))
    missing = public_pair_context(store, "me", "vc_kay")
    assert missing["connection_type"] == "missing_piece"
    assert missing["features"]["seeking_overlap_count"] == 1
    assert missing["features"]["cited_route_count"] > 0

    mirror = public_pair_context(store, None, "vc_kay", interest_topic_ids=["graphs"])
    assert mirror["connection_type"] == "mirror"
    assert mirror["features"]["cited_route_count"] == 0

    store.query(store.event(), "MATCH (s:Startup {id: 's_me'}) SET s.seeking = []")
    unexpected = public_pair_context(store, "me", "vc_kay")
    assert unexpected["connection_type"] == "unexpected_connection"
    assert unexpected["reason_code"] == "cited_warm_route"


def test_conversation_decision_uses_abstract_features_and_weighted_score(loaded):
    from warmopen.conversation import assess_conversation

    captured = []

    def provider(payload):
        captured.append(payload)
        return _decision()

    result = assess_conversation(loaded, "ghu", None, "vc_kay", jev=provider,
                                 interest_topic_ids=["graphs"])
    assert result["connection_type"] == "mirror"
    assert result["assessment"]["label"] == "uncalibrated conversation fit"
    assert result["assessment"]["score"] == 75
    assert result["assessment"]["model_confidence"] == 0.8
    assert result["assessment"]["abstained"] is False
    assert result["assessment"]["status"] == "assessed"
    assert result["assessment"]["rough_score"] is None
    assert result["assessment"]["estimate_kind"] == "model_assessment"
    assert result["assessment"]["limitations"] == ["No cited public route was found."]
    assert result["categories"][0]["supported"] is True
    assert result["categories"][0]["score"] == 75
    assert result["categories"][1]["supported"] is False
    assert result["categories"][1]["score"] is None
    assert result["ranked_openers"][0]["rank"] == 1
    encoded = json.dumps(captured[0], sort_keys=True)
    for hidden in ("vc_kay", "graphs", "example.org", "Funding agent infrastructure",
                   "Claim", "url"):
        assert hidden not in encoded
    assert set(captured[0]["state"]) == {
        "topic_overlap_count", "seeking_overlap_count", "cited_route_count", "best_hops",
        "supported_edge_count", "professional_evidence_count", "source_listed", "target_listed",
        "public_context_count", "public_context_match_count", "opener_candidates", "mentions",
    }
    assert captured[0]["state"]["mentions"] == {
        "mentions_available": False, "professional_mention_count": 0,
        "positive_mention_count": 0, "neutral_mention_count": 0,
        "critical_mention_count": 0, "unclear_mention_count": 0,
        "recent_mention_count": 0, "mention_source_count": 0,
    }
    fallback = assess_conversation(loaded, "ghu", None, "vc_kay",
                                   interest_topic_ids=["graphs"])
    assert fallback["assessment"]["score"] is None
    assert fallback["assessment"]["rough_score"] == 39
    assert fallback["assessment"]["estimate_kind"] == "rule_based_starting_estimate"


def test_confidence_and_category_gates_abstain(loaded):
    from warmopen.conversation import assess_conversation

    low = assess_conversation(loaded, "ghu", None, "vc_kay",
                              jev=lambda _: _decision(confidence=0.4),
                              interest_topic_ids=["graphs"])
    assert low["assessment"]["score"] is None
    assert low["assessment"]["abstained"] is True
    assert low["assessment"]["status"] == "low_confidence"

    inconsistent = assess_conversation(
        loaded, "ghu", None, "vc_kay",
        jev=lambda _: _decision(choice_type="unexpected_connection"),
        interest_topic_ids=["graphs"])
    assert inconsistent["assessment"]["score"] is None
    assert inconsistent["assessment"]["status"] == "category_inconsistent"
    assert all(item["score"] is None for item in inconsistent["categories"])


def test_no_cited_pair_context_skips_provider_and_refresh_is_explicit(store, seed, monkeypatch):
    from warmopen.conversation import assess_conversation
    from warmopen.seed import load_seed

    data = copy.deepcopy(seed)
    data["conferences"] = [{"id": "conversation_empty", "name": "Empty Conference"}]
    data["evidence"].append({"id": "empty_attendance", "url": "https://example.org/empty/attending",
                             "claim": "The person confirmed attendance", "observed_at": "2030-05-01",
                             "visibility": "public"})
    data["edges"].append({"type": "ATTENDS", "from": "eng_lee", "to": "conversation_empty",
                          "confirmed": True, "evidence": "empty_attendance"})
    load_seed(store, data)
    monkeypatch.setattr(store, "private", lambda *_: pytest.fail("conversation read private graph"))
    calls = []
    before = store.dump("event")
    result = assess_conversation(store, "conversation_empty", "me", "eng_lee",
                                 jev=lambda payload: calls.append(payload), refresh=True,
                                 brightdata=lambda url: pytest.fail("refresh used uncited URL"))
    assert calls == []
    assert result["assessment"]["status"] == "no_supported_basis"
    assert result["refresh"]["status"] == "no_sources"
    assert len(result["ranked_openers"]) == 3
    assert result["ranked_openers"][0]["text"] == "What brought you to this conference?"
    assert all(item["evidence_id"] is None for item in result["ranked_openers"])
    assert store.dump("event") == before


def test_unknown_category_never_turns_unrelated_target_facts_into_fit(loaded, monkeypatch):
    from warmopen import conversation

    original = conversation.public_pair_context
    context = original(loaded, None, "vc_kay", interest_topic_ids=["graphs"])
    context["connection_type"] = "unknown"
    context["features"]["topic_overlap_count"] = 0
    context["features"]["seeking_overlap_count"] = 0
    context["features"]["cited_route_count"] = 0
    context["features"]["professional_evidence_count"] = 5
    context["topic_matches"] = {"shared": [], "seeking": []}
    monkeypatch.setattr(conversation, "public_pair_context", lambda *_args, **_kwargs: context)
    calls = []
    result = conversation.assess_conversation(
        loaded, "ghu", None, "vc_kay", jev=lambda payload: calls.append(payload),
        interest_topic_ids=["graphs"])
    assert calls == []
    assert result["assessment"]["score"] is None
    assert result["assessment"]["status"] == "no_supported_basis"
    assert result["assessment"]["rough_score"] == 30
    assert result["assessment"]["estimate_kind"] == "rule_based_starting_estimate"
    assert result["assessment"]["abstained"] is True
    assert all(item["score"] is None for item in result["categories"])
    assert all(item["rough_score"] == 0 for item in result["categories"])


def test_no_source_or_topics_still_returns_rough_estimate_and_openers(loaded):
    from warmopen.conversation import assess_conversation

    result = assess_conversation(
        loaded, "ghu", None, "vc_kay",
        jev=lambda _payload: pytest.fail("unknown context must abstain before model call"))
    assert result["connection_type"] == "unknown"
    assert result["assessment"]["score"] is None
    assert result["assessment"]["abstained"] is True
    assert result["assessment"]["rough_score"] >= 20
    assert result["assessment"]["rough_score_label"] == (
        "starting estimate from available conference information")
    assert len(result["ranked_openers"]) == 3
    assert any(item["evidence_id"] for item in result["ranked_openers"])


def test_conversation_topics_are_ranked_by_supported_scores(store, seed):
    from warmopen.conversation import assess_conversation
    from warmopen.seed import load_seed

    load_seed(store, _sourced_seeking_seed(seed))

    def provider(_payload):
        result = _decision(choice_type="missing_piece")
        result["answers"]["missing_piece_fit"]["probabilities"] = {
            "high": 0.8, "medium": 0.1, "low": 0.1, "INSUFFICIENT_EVIDENCE": 0.0}
        result["answers"]["mirror_fit"]["probabilities"] = {
            "high": 0.1, "medium": 0.1, "low": 0.8, "INSUFFICIENT_EVIDENCE": 0.0}
        return result

    result = assess_conversation(store, "ghu", "me", "vc_kay", jev=provider,
                                 interest_topic_ids=["graphs"])
    ranked = {item["type"]: item["rank"] for item in result["categories"]}
    scores = {item["type"]: item["score"] for item in result["categories"]}
    assert scores["missing_piece"] > scores["mirror"]
    assert ranked["missing_piece"] < ranked["mirror"]


def test_mentions_are_fetched_only_on_explicit_refresh_and_model_gets_counts(loaded):
    from warmopen.conversation import assess_conversation

    calls = []

    def fetch(name, conference):
        calls.append((name, conference))
        return {
            "status": "ok",
            "items": [{"url": "https://x.com/speaker/status/123", "title": "A post",
                       "excerpt": "Some public professional context", "published_at": "2026-10-20",
                       "tone": "positive", "platform": "x"}],
            "signals": {"mentions_available": True, "professional_mention_count": 2,
                        "positive_mention_count": 1, "neutral_mention_count": 1,
                        "critical_mention_count": 0, "unclear_mention_count": 0,
                        "recent_mention_count": 1, "mention_source_count": 1},
        }

    payloads = []
    no_refresh = assess_conversation(loaded, "ghu", None, "vc_kay", jev=lambda p: payloads.append(p),
                                     mentions=fetch, interest_topic_ids=["graphs"])
    assert calls == []
    assert no_refresh["mentions"]["status"] == "not_requested"

    refreshed = assess_conversation(loaded, "ghu", None, "vc_kay", jev=lambda p: payloads.append(p),
                                    mentions=fetch, refresh=True,
                                    interest_topic_ids=["graphs"])
    assert len(calls) == 1
    assert calls[0][0]
    assert calls[0][1]
    assert refreshed["mentions"]["items"][0]["title"] == "A post"
    model_state = json.dumps(payloads[-1]["state"], sort_keys=True)
    assert "A post" not in model_state
    assert "x.com" not in model_state
    assert payloads[-1]["state"]["mentions"]["professional_mention_count"] == 2
    assert refreshed["mentions"]["signals"]["critical_mention_count"] == 0
