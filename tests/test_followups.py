"""Voice-created actions must remain private, authenticated, and person-specific."""
import pytest
from warmopen.profile_sessions import create_profile_session
from warmopen.followups import save_action, list_actions, complete_action, interpret_action


def test_followup_round_trip_and_user_reported_connection_are_private(loaded):
    session = create_profile_session(loaded, [])
    public_before = loaded.dump()
    command = 'Remind me to follow up with Kay Investor via LinkedIn as we connected on LinkedIn'
    result = save_action(loaded, session['id'], session['token'], 'ghu', command, 'request_123456')
    item = result['items'][0]
    assert item['target'] == 'vc_kay'
    assert item['channel'] == 'linkedin'
    assert item['status'] == 'pending'
    assert item['due_at'] == ''
    graph = loaded.private(session['id'])
    path = loaded.query(graph, "MATCH p=(:Person {id:'you'})-[:HAS_ACTION]->(:FollowUp)-[:ABOUT]->(:Contact) RETURN p").result_set
    assert len(path) == 1
    assert loaded.query(graph, "MATCH ()-[r:CONNECTED_ON]->() RETURN r.basis").result_set == [['requester_reported']]
    assert loaded.dump() == public_before
    with pytest.raises(PermissionError): list_actions(loaded, session['id'], 'bad-token', 'ghu')
    other = create_profile_session(loaded, [])
    with pytest.raises(PermissionError): list_actions(loaded, session['id'], other['token'], 'ghu')
    repeated = save_action(loaded, session['id'], session['token'], 'ghu', command, 'request_123456')
    assert len(repeated['items']) == 1
    done = complete_action(loaded, session['id'], session['token'], 'ghu', item['id'])
    assert done['items'][0]['status'] == 'done'


def test_action_does_not_silently_use_selected_person_for_unknown_name(loaded):
    with pytest.raises(ValueError, match='full name'):
        interpret_action(loaded, 'ghu', 'Remind me to follow up with Unlisted Stranger on LinkedIn', 'vc_kay')
    assert interpret_action(loaded, 'ghu', 'Remind me to follow up with them by email', 'vc_kay')['target'] == 'vc_kay'
    with pytest.raises(ValueError): interpret_action(loaded, 'ghu', "Don't remind me to follow up with Kay Investor")
    with pytest.raises(ValueError): interpret_action(loaded, 'ghu', 'Follow up with Kay Investor by email and text')


def test_timed_followup_uses_explicit_timezone_and_filters_conference(loaded):
    session = create_profile_session(loaded, [])
    result = save_action(loaded, session['id'], session['token'], 'ghu', 'Follow up with Kay Investor by email', 'timed_request', due_at='2026-10-25T10:00:00-07:00')
    assert result['items'][0]['due_at'] == '2026-10-25T17:00:00+00:00'
    assert list_actions(loaded, session['id'], session['token'], 'other_conference') == []
    with pytest.raises(ValueError, match='timezone'):
        save_action(loaded, session['id'], session['token'], 'ghu', 'Follow up with Kay Investor', 'other_request', due_at='2026-10-25T10:00:00')
