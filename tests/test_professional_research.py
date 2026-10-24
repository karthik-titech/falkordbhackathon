"""Professional research must preserve identity, provenance, and social exclusions."""

import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("speaker_research", Path(__file__).parents[1] / "scripts" / "research_github_profiles.py")
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


def test_research_rejects_social_urls_and_noncontiguous_name_matches():
    assert not research._public_http_url("https://www.linkedin.com/in/example")
    assert not research._public_http_url("https://x.com/example")
    assert not research._name_verified("John Maeda", "John Smith spoke first. The next speaker was Jane Maeda.")
    assert research._name_verified("John Maeda", "John Maeda builds developer tools.")


def test_verified_bio_adds_cited_topics_but_conference_text_does_not(store, seed, tmp_path, monkeypatch):
    from warmopen.seed import load_seed

    load_seed(store, seed)
    url = "https://example.org/kay-bio"
    manifest = tmp_path / "manifest.json"
    row = {"id": "vc_kay", "name": "Kay Investor", "conference_ids": ["ghu"],
           "professional_urls": [url], "sources": [{"url": url, "type": "professional_bio_or_employer"}]}
    manifest.write_text(json.dumps([row]))
    monkeypatch.setattr(research, "_public_http_url", lambda value: value == url)
    monkeypatch.setattr(research, "_fetch", lambda value: {"ok": True, "text": "Kay Investor researches Graph databases and developer tools."})
    result = research.research_profiles(store, manifest)
    assert result["people"]["vc_kay"]["status"] == "complete"
    assert store.query("event", "MATCH (:Person {id:'vc_kay'})-[:HAS_PROFILE]->(p:ProfessionalProfile) RETURN p.url").result_set == [[url]]
    rows = store.query("event", "MATCH (:Person {id:'vc_kay'})-[r:INTERESTED_IN]->(:Topic {id:'graphs'}) WITH r MATCH (e:Evidence) WHERE e.id = r.evidence_id RETURN e.url, e.visibility").result_set
    assert [url, "public"] in rows

    row["id"], row["name"] = "eng_lee", "Lee Buyer"
    row["sources"][0]["type"] = "official_conference_article"
    manifest.write_text(json.dumps([row]))
    monkeypatch.setattr(research, "_fetch", lambda value: {"ok": True, "text": "Lee Buyer attends Graph databases sessions."})
    result = research.research_profiles(store, manifest)
    assert result["people"]["eng_lee"]["status"] == "conference_only"
    assert store.query("event", "MATCH (:Person {id:'eng_lee'})-[:HAS_PROFILE]->(p) RETURN p").result_set == []
    assert store.query("event", "MATCH (:Person {id:'eng_lee'})-[r:INTERESTED_IN]->() RETURN r").result_set == []


def test_professional_excerpt_excludes_contact_fields_and_unrelated_personal_details():
    text = "Kay Investor is a software engineer. Contact: kay@example.org or +1 212 555 0100. Loves gardening."
    excerpt = research._excerpt("Kay Investor", text, [])
    assert "software engineer" in excerpt
    assert "@" not in excerpt
    assert "555" not in excerpt
    assert "gardening" not in excerpt
