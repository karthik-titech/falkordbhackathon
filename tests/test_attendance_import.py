"""Attendance import preflight, ownership and consent boundaries."""

import copy
import json

import pytest


def _manifest(import_id="roster_a", attendees=None, conference_id="import_conf"):
    if attendees is None:
        attendees = [{"person_id": "me", "basis": "public_professional", "confirmed": True,
                      "source": {"url": "https://example.org/attendees",
                                 "claim": "Requester Me is confirmed for the conference.",
                                 "observed_at": "2026-10-24"}}]
    return {"schema_version": 1, "import_id": import_id,
            "conference": {"id": conference_id, "name": "Import Demo Conference",
                           "starts": "2099-05-10", "ends": "2099-05-12"},
            "attendees": copy.deepcopy(attendees)}


def _record(person_id, name=None, confirmed=True, basis="public_professional", suffix=None):
    suffix = suffix or person_id
    item = {"person_id": person_id, "basis": basis, "confirmed": confirmed,
            "source": {"url": f"https://example.org/attendees/{suffix}",
                       "claim": f"{suffix} has an attendance update for the conference.",
                       "observed_at": "2026-10-24"}}
    if name is not None:
        item["name"] = name
    return item


def test_check_mode_preflights_without_writing_and_import_is_idempotent(loaded):
    from warmopen.attendance_import import import_attendees

    manifest = _manifest(attendees=[_record("me"),
                                   _record("new_attendee", "New Attendee", basis="opted_in")])
    preview = import_attendees(loaded, manifest, check=True)
    assert preview == {"new_conference": 1, "new_people": 1, "new_evidence": 2,
                       "new_attendance": 2, "updated_attendance": 0,
                       "retracted_attendance": 0, "active_attendance": 2}
    assert loaded.query(loaded.event(), "MATCH (:Conference {id: 'import_conf'}) RETURN count(*)").result_set[0][0] == 0
    assert loaded.query(loaded.event(), "MATCH (:Person {id: 'new_attendee'}) RETURN count(*)").result_set[0][0] == 0

    imported = import_attendees(loaded, manifest)
    assert imported == preview
    person = loaded.query(loaded.event(),
                          "MATCH (p:Person {id: 'new_attendee'}) RETURN p.name, p.kind, p.consented").result_set
    assert person == [["New Attendee", "attendee", False]]
    existing = loaded.query(loaded.event(),
                            "MATCH (p:Person {id: 'me'}) RETURN p.name, p.kind, p.consented").result_set
    assert existing == [["Requester Me", "attendee", True]]
    assert import_attendees(loaded, manifest) == {
        "new_conference": 0, "new_people": 0, "new_evidence": 0,
        "new_attendance": 0, "updated_attendance": 0,
        "retracted_attendance": 0, "active_attendance": 2}


def test_cli_import_check_prints_counts_only(loaded, tmp_path, monkeypatch, capsys):
    from warmopen.cli import main
    from warmopen.graphstore import GraphStore

    manifest = _manifest()
    file = tmp_path / "attendees.json"
    file.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(GraphStore, "connect", classmethod(lambda _cls: loaded))
    main(["import-attendees", str(file), "--check"])
    output = capsys.readouterr().out
    assert json.loads(output) == {"new_conference": 1, "new_people": 0, "new_evidence": 1,
                                  "new_attendance": 1, "updated_attendance": 0,
                                  "retracted_attendance": 0, "active_attendance": 1}
    assert "Requester Me" not in output and "example.org" not in output
    assert loaded.query(loaded.event(),
                        "MATCH (:Conference {id: 'import_conf'}) RETURN count(*)").result_set[0][0] == 0


def test_snapshot_retracts_only_its_attendance_and_retains_people_and_evidence(loaded):
    from warmopen.attendance_import import import_attendees

    first = _manifest(attendees=[_record("me"), _record("owner_a")])
    import_attendees(loaded, first)
    other_source = _manifest(import_id="roster_b", attendees=[_record("owner_b", suffix="owner-b")])
    import_attendees(loaded, other_source)

    update = _manifest(attendees=[_record("me")])
    counts = import_attendees(loaded, update)
    assert counts["retracted_attendance"] == 1
    rows = loaded.query(loaded.event(),
                        "MATCH (p:Person)-[r:ATTENDS]->(:Conference {id: 'import_conf'}) "
                        "RETURN p.id, r.import_id ORDER BY p.id, r.import_id").result_set
    assert rows == [["me", "roster_a"], ["owner_b", "roster_b"]]
    assert loaded.query(loaded.event(), "MATCH (:Person {id: 'owner_a'}) RETURN count(*)").result_set[0][0] == 1
    evidence = loaded.query(loaded.event(),
                            "MATCH (e:Evidence) WHERE e.import_id = 'roster_a' RETURN count(e)").result_set[0][0]
    assert evidence == 2


def test_exact_unowned_attendance_is_left_unchanged_without_adoption(loaded):
    from warmopen.attendance_import import _evidence_id, import_attendees

    manifest = _manifest()
    import_attendees(loaded, manifest)
    eid = _evidence_id("roster_a", "import_conf", "me")
    loaded.query(loaded.event(),
                "MATCH (:Person {id: 'me'})-[r:ATTENDS]->(:Conference {id: 'import_conf'}) "
                "REMOVE r.import_id")
    loaded.query(loaded.event(), "MATCH (e:Evidence {id: $id}) REMOVE e.import_id, e.conference_id",
                 {"id": eid})
    result = import_attendees(loaded, manifest)
    assert result["new_attendance"] == 0 and result["new_evidence"] == 0
    row = loaded.query(loaded.event(),
                       "MATCH (:Person {id: 'me'})-[r:ATTENDS]->(:Conference {id: 'import_conf'}) "
                       "RETURN r.import_id, r.evidence_id").result_set
    assert row == [[None, eid]]


def test_confirmed_false_retracts_owned_edge_but_keeps_evidence(loaded):
    from warmopen.attendance_import import import_attendees

    active = _manifest(attendees=[_record("me")])
    import_attendees(loaded, active)
    withdrawn = _manifest(attendees=[_record("me", confirmed=False, suffix="withdrawn")])
    result = import_attendees(loaded, withdrawn)
    assert result["retracted_attendance"] == 1
    assert loaded.query(loaded.event(),
                        "MATCH (:Person {id: 'me'})-[r:ATTENDS]->(:Conference {id: 'import_conf'}) "
                        "RETURN count(r)").result_set[0][0] == 0
    assert loaded.query(loaded.event(),
                        "MATCH (e:Evidence) WHERE e.import_id = 'roster_a' RETURN count(e)").result_set[0][0] == 1


def test_import_id_ownership_is_scoped_to_the_conference(loaded):
    from warmopen.attendance_import import import_attendees

    first = _manifest(import_id="same-source", attendees=[_record("me")], conference_id="conf_one")
    second = _manifest(import_id="same-source", attendees=[_record("owner_a")], conference_id="conf_two")
    import_attendees(loaded, first)
    import_attendees(loaded, second)
    withdrawn = _manifest(import_id="same-source", attendees=[], conference_id="conf_one")
    import_attendees(loaded, withdrawn)
    rows = loaded.query(loaded.event(),
                        "MATCH (p:Person)-[r:ATTENDS {import_id: 'same-source'}]->(c:Conference) "
                        "RETURN p.id, c.id").result_set
    assert rows == [["owner_a", "conf_two"]]


def test_conflicting_owner_name_dates_and_evidence_fail_before_any_write(loaded):
    from warmopen.attendance_import import import_attendees

    import_attendees(loaded, _manifest(attendees=[_record("me")]))
    conflict = _manifest(import_id="roster_other", attendees=[_record("me", suffix="other")])
    with pytest.raises(ValueError, match="owned by another source"):
        import_attendees(loaded, conflict)
    assert loaded.query(loaded.event(),
                        "MATCH (:Evidence {import_id: 'roster_other'}) RETURN count(*)").result_set[0][0] == 0

    wrong_name = _manifest(conference_id="another_conf",
                           attendees=[_record("me", name="Different Person")])
    with pytest.raises(ValueError, match="name conflicts"):
        import_attendees(loaded, wrong_name)
    assert loaded.query(loaded.event(),
                        "MATCH (:Conference {id: 'another_conf'}) RETURN count(*)").result_set[0][0] == 0

    changed_dates = _manifest(attendees=[_record("owner_a")])
    changed_dates["conference"]["starts"] = "2099-05-11"
    with pytest.raises(ValueError, match="dates conflict"):
        import_attendees(loaded, changed_dates)
    assert loaded.query(loaded.event(),
                        "MATCH (:Person {id: 'owner_a'}) RETURN count(*)").result_set[0][0] == 1


@pytest.mark.parametrize("mutate", [
    lambda m: m.update(private={"knows": []}),
    lambda m: m["attendees"][0].update(owner_token="not-a-token"),
    lambda m: m["attendees"][0]["source"].update(extra="unrelated raw data"),
    lambda m: m.update(schema_version=True),
])
def test_manifest_allowlist_rejects_private_seed_fields(mutate):
    from warmopen.attendance_import import validate_manifest

    manifest = _manifest()
    mutate(manifest)
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_social_profile_url_and_embedded_email_are_rejected():
    from warmopen.attendance_import import validate_manifest

    social = _manifest(attendees=[_record("me", suffix="social")])
    social["attendees"][0]["source"]["url"] = "https://linkedin.com/in/example"
    with pytest.raises(ValueError, match="social-profile"):
        validate_manifest(social)
    email = _manifest(attendees=[_record("me", suffix="email")])
    email["attendees"][0]["source"]["claim"] = "Contact me at person@example.org"
    with pytest.raises(ValueError, match="private or secret"):
        validate_manifest(email)


@pytest.mark.parametrize("url", ["http://127.0.0.1/attendees", "https://example.org/?%74oken=value"])
def test_private_hosts_and_encoded_credential_parameters_are_rejected(url):
    from warmopen.attendance_import import validate_manifest

    manifest = _manifest()
    manifest["attendees"][0]["source"]["url"] = url
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_json_duplicate_keys_and_cli_errors_do_not_echo_input(tmp_path, monkeypatch, capsys):
    from warmopen.cli import main
    from warmopen.graphstore import GraphStore

    file = tmp_path / "invalid.json"
    file.write_text('{"schema_version": 1, "schema_version": 1, "owner_token": "secret-value"}',
                    encoding="utf-8")
    monkeypatch.setattr(GraphStore, "connect", classmethod(
        lambda _cls: pytest.fail("manifest parsing should precede database connection")))
    with pytest.raises(SystemExit):
        main(["import-attendees", str(file)])
    error = capsys.readouterr().err
    assert "Attendance import failed" in error
    assert "schema_version" not in error and "secret-value" not in error and str(file) not in error
