"""Opening lines should use matched context, never dump article text."""
from warmopen.conversation import _opener_candidates


def context():
    return {"source": None, "target": "target", "public_names": {"target": "Andrea Griffiths"},
            "routes": [], "opener_evidence_ids": ["article", "topic"],
            "opener_topic_matches": {"topic": ["security"]},
            "topic_names": {"security": "Agent security"}}


def test_shared_interest_beats_article_navigation_and_retains_citation():
    evidence = {"article": {"url": "https://example.org/article", "claim": "GitHub Universe More on GitHub Universe 10 technical talks I am excited about"},
                "topic": {"url": "https://example.org/bio", "claim": "Andrea works on agent security."}}
    result = _opener_candidates(context(), evidence, [{"evidence_id": "article", "excerpt": "Navigation and a very long article"}])
    assert result[0]["text"] == "Hey Andrea, I'm interested in Agent security too—what are you working on right now?"
    assert result[0]["evidence_ids"] == ["topic"]
    assert all("I read:" not in item["text"] and "Navigation" not in item["text"] for item in result)
    assert all(len(item["text"]) < 180 for item in result)


def test_long_talk_title_is_not_dumped_into_spoken_line():
    value = context()
    value["opener_topic_matches"] = {}
    value["opener_evidence_ids"] = ["talk"]
    result = _opener_candidates(value, {"talk": {"url": "https://example.org/talk", "claim": 'Andrea presented "' + 'An extremely long session title ' * 8 + '"'}}, [])
    assert result[0]["text"].startswith("Hey Andrea, your session caught my eye")
    assert result[0]["evidence_ids"] == ["talk"]
    assert len(result[0]["text"]) < 150
