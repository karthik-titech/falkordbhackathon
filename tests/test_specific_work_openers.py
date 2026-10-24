"""Specific-work openers require an attributed, cited publication or talk."""
from warmopen.conversation import _opener_candidates, _specific_work


def _context():
    return {"source": None, "target": "target", "public_names": {"target": "Andrea Griffiths"},
            "routes": [], "opener_evidence_ids": ["work", "topic"],
            "opener_topic_matches": {"topic": ["agents"]}, "topic_names": {"agents": "Agents"}}


def test_attributed_paper_beats_generic_interest_and_keeps_citation():
    evidence = {"work": {"claim": 'Andrea Griffiths published the paper "Reliable Agent Memory"', "url": "https://example.org/paper"},
                "topic": {"claim": "Andrea researches agents", "url": "https://example.org/bio"}}
    result = _opener_candidates(_context(), evidence, [])
    assert 'your paper “Reliable Agent Memory”' in result[0]["text"]
    assert "what surprised you most" in result[0]["text"]
    assert result[0]["evidence_ids"] == ["work"]
    assert len(result[0]["text"]) < 180


def test_post_requires_attribution_not_just_a_status_url():
    assert _specific_work({"claim": 'Someone else wrote the post "Open source agents"', "url": "https://x.com/other/status/123"}, "Andrea Griffiths") is None
    assert _specific_work({"claim": 'Andrea Griffiths posted "Open source agents"', "url": "https://x.com/andrea/status/123"}, "Andrea Griffiths") == ("post", "Open source agents")


def test_verified_blog_byline_uses_title_without_navigation_or_body_dump():
    evidence = {"claim": "Public conference page names Andrea Griffiths in this context: 10 technical talks I’m excited about at GitHub Universe 2026 - The GitHub Blog Andrea Griffiths · @AndreaGriffiths11 October 1, 2026 | 5 minutes Share: A long article body follows."}
    assert _specific_work(evidence, "Andrea Griffiths") == ("article", "10 technical talks I’m excited about at GitHub Universe 2026")
    assert _specific_work(evidence, "Another Speaker") is None


def test_present_tense_scheduled_talk_is_a_specific_reference():
    evidence = {"claim": 'Andrea Griffiths (GitHub), Shishir Tewari (Procore) present "Build once, run on any agent: a practical guide to agent skills" at GitHub Universe 2026'}
    assert _specific_work(evidence, "Andrea Griffiths") == ("session", "Build once, run on any agent: a practical guide to agent skills")
