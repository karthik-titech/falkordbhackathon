"""Shared fixtures for the Warm Open frozen contract (ptc1, ptc2, ptc3).

Source: specs.ptc/PLAN.md, joint Claude + Sol design debate 2026-10-23.
Tests run against a live FalkorDB (FALKORDB_HOST / FALKORDB_PORT); each test
uses a random graph prefix and drops its graphs afterwards.
"""
import copy
import os
import uuid

import pytest

SEED = {
    "people": [
        {"id": "me", "name": "Requester Me", "handle": "me", "kind": "attendee", "consented": True, "owner_token": "tok-me"},
        {"id": "owner_a", "name": "Owner A", "handle": "owner_a", "kind": "attendee", "consented": True, "owner_token": "tok-a"},
        {"id": "owner_b", "name": "Owner B", "handle": "owner_b", "kind": "attendee", "consented": True, "owner_token": "tok-b"},
        {"id": "vc_kay", "name": "Kay Investor", "handle": "kay", "kind": "speaker", "consented": False},
        {"id": "eng_lee", "name": "Lee Buyer", "handle": "lee", "kind": "speaker", "consented": False},
        {"id": "topic_twin", "name": "Topic Twin", "handle": "twin", "kind": "attendee", "consented": True, "owner_token": "tok-t"},
    ],
    "topics": [{"id": "agents", "name": "Agents"}, {"id": "graphs", "name": "Graph databases"}],
    "talks": [
        {"id": "t_kay", "title": "Funding agent infrastructure", "conference": "aie", "starts": "2026-10-24T14:00", "room": "A",
         "speakers": ["vc_kay"], "topics": ["agents"], "evidence": "ev_talk_kay"},
        {"id": "t_pair", "title": "Graphs for agents", "conference": "ghu", "starts": "2026-10-28T11:00", "room": "B",
         "speakers": ["owner_a", "vc_kay"], "topics": ["graphs"], "evidence": "ev_talk_pair"},
    ],
    "repos": [{"id": "r_tool", "full_name": "example/agent-tool"}],
    "companies": [{"id": "c_buyer", "name": "Buyer Corp", "needs": ["observability"], "evidence": "ev_company_needs"}],
    "funds": [{"id": "f_kay", "name": "Kay Ventures", "stages": ["seed", "series_a"], "sectors": ["devtools"], "evidence": "ev_fund_thesis"}],
    "startups": [{"id": "s_me", "name": "My Startup", "stage": "pre_seed", "sectors": ["devtools"],
                  "product_category": "observability", "founders": ["me"]}],
    "edges": [
        {"type": "CONTRIBUTED_TO", "from": "me", "to": "r_tool", "evidence": "ev_repo_me"},
        {"type": "CONTRIBUTED_TO", "from": "owner_a", "to": "r_tool", "evidence": "ev_repo_a"},
        {"type": "WORKS_AT", "from": "eng_lee", "to": "c_buyer", "role": "VP Engineering", "evidence": "ev_lee_role"},
        {"type": "PARTNER_AT", "from": "vc_kay", "to": "f_kay", "evidence": "ev_fund_thesis"},
        {"type": "INTERESTED_IN", "from": "me", "to": "agents"},
        {"type": "INTERESTED_IN", "from": "topic_twin", "to": "agents"},
    ],
    "evidence": [
        {"id": "ev_talk_kay", "url": "https://example.org/aie/kay", "claim": "Kay speaks on funding agent infrastructure", "observed_at": "2026-10-20", "visibility": "public"},
        {"id": "ev_talk_pair", "url": "https://example.org/ghu/pair", "claim": "Owner A and Kay co-present Graphs for agents", "observed_at": "2026-10-20", "visibility": "public"},
        {"id": "ev_repo_me", "url": "https://example.org/r/me", "claim": "Me contributed to agent-tool", "observed_at": "2026-10-19", "visibility": "public"},
        {"id": "ev_repo_a", "url": "https://example.org/r/a", "claim": "Owner A contributed to agent-tool", "observed_at": "2026-10-19", "visibility": "public"},
        {"id": "ev_lee_role", "url": "https://example.org/lee", "claim": "Lee is VP Engineering at Buyer Corp", "observed_at": "2026-10-18", "visibility": "public"},
        {"id": "ev_company_needs", "url": "https://example.org/buyer/jobs", "claim": "Buyer Corp is hiring for observability", "observed_at": "2026-10-18", "visibility": "public"},
        {"id": "ev_fund_thesis", "url": "https://example.org/kay/thesis", "claim": "Kay Ventures invests in seed and Series A devtools", "observed_at": "2026-10-17", "visibility": "public"},
        {"id": "ev_private_b", "url": "https://example.org/private/b", "claim": "Owner B worked with Carol", "observed_at": "2026-10-10", "visibility": "private"},
    ],
    "private": {
        "owner_b": {"people": [{"id": "carol_hidden", "name": "Carol Hidden"}], "knows": [
            {"from": "owner_b", "to": "carol_hidden", "category": "colleague",
             "features": {"shared_repos": 3, "same_company": True}, "owner_strength": None, "evidence": "ev_private_b"},
            {"from": "carol_hidden", "to": "eng_lee", "category": "friend",
             "features": {}, "owner_strength": 0.8, "evidence": "ev_private_b"},
            {"from": "owner_b", "to": "dave_hidden", "category": "met",
             "features": {"met_today": True}, "owner_strength": None, "evidence": None},
            {"from": "dave_hidden", "to": "erin_hidden", "category": "friend",
             "features": {}, "owner_strength": 0.9, "evidence": None},
            {"from": "erin_hidden", "to": "vc_kay", "category": "friend",
             "features": {}, "owner_strength": 0.9, "evidence": None},
        ]},
    },
}

HIDDEN_IDS = ("carol_hidden", "dave_hidden", "erin_hidden")
# AMENDMENT 2026-10-23 (Astra plan review 3.2): private names and private claims must not leak either.
HIDDEN_TEXT = HIDDEN_IDS + ("Carol", "ev_private_b", "worked with Carol")


@pytest.fixture
def seed():
    return copy.deepcopy(SEED)


@pytest.fixture
def store():
    from warmopen.graphstore import GraphStore

    host = os.environ.get("FALKORDB_HOST", "localhost")
    port = int(os.environ.get("FALKORDB_PORT", "6379"))
    s = GraphStore.connect(host=host, port=port, prefix="t" + uuid.uuid4().hex[:10] + "_")
    try:
        yield s
    finally:
        s.drop_all()


@pytest.fixture
def loaded(store, seed):
    from warmopen.seed import load_seed

    load_seed(store, seed)
    return store
