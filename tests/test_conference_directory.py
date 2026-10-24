"""Public conference directory keeps attendance separate from cited schedules."""

import copy


def _directory_seed(seed):
    data = copy.deepcopy(seed)
    data["conferences"] = [{
        "id": "directory_2026", "name": "Directory Summit", "starts": "2030-05-10",
        "ends": "2030-05-11",
    }]
    data["talks"].extend([
        {"id": "directory_talk", "title": "Graph connections", "conference": "directory_2026",
         "starts": "2030-05-10T11:00", "speakers": ["owner_a"], "evidence": "directory_schedule"},
        {"id": "uncited_directory_talk", "title": "Uncited appearance", "conference": "directory_2026",
         "speakers": ["vc_kay"]},
    ])
    data["edges"].extend([
        {"type": "ATTENDS", "from": "owner_a", "to": "directory_2026", "confirmed": True,
         "evidence": "directory_attendance"},
        {"type": "ATTENDS", "from": "vc_kay", "to": "directory_2026", "confirmed": True,
         "evidence": "directory_local_url"},
        {"type": "ATTENDS", "from": "topic_twin", "to": "directory_2026", "confirmed": False,
         "evidence": "directory_attendance"},
    ])
    data["evidence"].extend([
        {"id": "directory_attendance", "url": "https://example.org/attending/owner-a",
         "claim": "Owner A confirmed attendance", "observed_at": "2030-05-01", "visibility": "public"},
        {"id": "directory_schedule", "url": "https://example.org/talks/directory",
         "claim": "Owner A is scheduled to speak about graph connections", "observed_at": "2030-05-01",
         "visibility": "public"},
        {"id": "directory_talk_only", "url": "https://example.org/talks/uncited",
         "claim": "A talk is listed without a cited speaker relationship", "observed_at": "2030-05-01",
         "visibility": "public"},
        {"id": "directory_local_url", "url": "http://127.0.0.1/private",
         "claim": "A confirmed attendance claim with a non-public source", "observed_at": "2030-05-01",
         "visibility": "public"},
    ])
    return data


def test_people_endpoint_separates_attendance_from_cited_speakers_and_flags_overlap(store, seed):
    from warmopen.app import _live
    from warmopen.seed import load_seed

    load_seed(store, _directory_seed(seed))
    store.query(store.event(),
                "MATCH (t:Talk {id: 'uncited_directory_talk'}), "
                "(e:Evidence {id: 'directory_talk_only'}) "
                "MERGE (t)-[:SUPPORTED_BY]->(e)")
    result = _live(store, "GET", "/api/conferences/directory_2026/people", None, None, None, None)
    assert [person["id"] for person in result["confirmed_attendees"]] == ["owner_a"]
    assert [person["id"] for person in result["scheduled_speakers"]] == ["owner_a"]
    assert result["overlap_person_ids"] == ["owner_a"]
    assert result["confirmed_attendees"][0]["overlap"] is True
    assert result["scheduled_speakers"][0]["overlap"] is True
    assert result["scheduled_speakers"][0]["talks"] == [
        {"id": "directory_talk", "title": "Graph connections", "starts": "2030-05-10T11:00"}]
    assert "directory_attendance" in result["evidence"]
    assert "directory_schedule" in result["evidence"]
    assert "directory_local_url" not in result["evidence"]


def test_directory_returns_legacy_talk_conferences_and_sourced_catalog_dates(loaded):
    from warmopen.directory import list_conferences

    items = {item["id"]: item for item in list_conferences(loaded)}
    assert "ghu" in items
    assert items["ghu"]["starts"] is None and items["ghu"]["ends"] is None
    assert items["github_universe_2026"]["name"] == "GitHub Universe 2026"
    assert items["github_universe_2026"]["starts"] == "2026-10-28"
    assert items["github_universe_2026"]["ends"] == "2026-10-29"
    assert items["github_universe_2026"]["official_url"] == "https://githubuniverse.com"
    assert items["github_universe_2026"]["confirmed_attendees_count"] == 0


def test_conference_node_dates_without_a_public_source_are_hidden(store, seed):
    from warmopen.directory import list_conferences
    from warmopen.seed import load_seed

    data = copy.deepcopy(seed)
    data["conferences"] = [{"id": "unsourced_dates", "name": "Un sourced event",
                            "starts": "2030-01-01", "ends": "2030-01-02"}]
    load_seed(store, data)
    item = next(item for item in list_conferences(store) if item["id"] == "unsourced_dates")
    assert item["starts"] is None and item["ends"] is None


def test_directory_endpoints_are_read_only_public_and_do_not_open_private_graph(loaded, monkeypatch):
    from warmopen.app import _live

    monkeypatch.setattr(loaded, "private", lambda *_: (_ for _ in ()).throw(AssertionError("private graph access")))
    before = loaded.dump("event")
    listing = _live(loaded, "GET", "/api/conferences", None,
                    "ignored-token", lambda _: (_ for _ in ()).throw(AssertionError("provider call")),
                    lambda _: (_ for _ in ()).throw(AssertionError("writer call")))
    directory = _live(loaded, "GET", "/api/conferences/ghu/people", None,
                      "ignored-token", lambda _: (_ for _ in ()).throw(AssertionError("provider call")),
                      lambda _: (_ for _ in ()).throw(AssertionError("writer call")))
    assert loaded.dump("event") == before
    assert listing["items"]
    assert directory["confirmed_attendees"] == []
    assert directory["scheduled_speakers"]
