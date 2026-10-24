"""ptc5b frozen contract: hook wording matches its evidence.

Source: gate-seat check on real data 2026-10-24 (Garry Tan's Coinbase fact
comes from his bio, not a news story, yet the opener said "Did you see
Coinbase's news?") and AI& panel ptc8 DeepSeek PP-4 (personal_interest had no
style-specific ending for openers 2 and 3).
Rule: INVESTED_IN edges carry announced (bool). announced -> "Did you see
<company>'s news? Great company."; otherwise -> "I saw <fund> backed <company>.
Great company." personal_interest openers 2 and 3 end "How did you get into it?".
"""
import copy

from test_ptc8_hooked_openers import HookJEV, _hooked_seed, _invest, _load


def _seed(seed, announced):
    data = _hooked_seed(seed)
    for edge in data["edges"]:
        if edge["type"] == "INVESTED_IN":
            edge["announced"] = announced
    return data


def test_announced_investment_says_news(store, seed):
    from warmopen.openers import generate_openers
    from warmopen.scoring import score_fit

    s = _load(store, _seed(seed, True))
    rid = _invest(s)
    score_fit(s, rid, HookJEV())
    text = generate_openers(s, rid, None)[0]["text"]
    assert "Did you see Port Co's news? Great company." in text


def test_unannounced_investment_names_the_fund(store, seed):
    from warmopen.openers import generate_openers
    from warmopen.scoring import score_fit

    s = _load(store, _seed(seed, False))
    rid = _invest(s)
    score_fit(s, rid, HookJEV())
    text = generate_openers(s, rid, None)[0]["text"]
    assert "news" not in text.lower()
    assert "I saw Kay Ventures backed Port Co. Great company." in text
    assert text.endswith("Is anyone from their team here?")


def test_personal_interest_ending_for_other_openers(store, seed):
    from warmopen.openers import generate_openers
    from warmopen.scoring import score_fit

    s = _load(store, copy.deepcopy(_seed(seed, True)))
    rid = _invest(s)
    score_fit(s, rid, HookJEV(cue="personal_interest"))
    cited = [o for o in generate_openers(s, rid, None) if o["evidence_id"]]
    assert cited and all(o["text"].endswith("How did you get into it?") for o in cited)
