"""Requester-owned follow-up actions, never public relationship claims."""
from datetime import datetime, timedelta, timezone
import hashlib
import re

from .directory import conference_people
from .profile_sessions import read_profile_session, _safe_session_graph


def _auth(store, session, token):
    read_profile_session(store, session, token)
    return _safe_session_graph(store, session)


def list_actions(store, session, token, conference):
    graph = _auth(store, session, token)
    rows = store.query(graph,
        "MATCH (:Person {id:'you'})-[:HAS_ACTION]->(a:FollowUp)-[:ABOUT]->(p:Contact) "
        "WHERE a.conference_id=$conference "
        "RETURN a.id, p.public_id, p.name, a.channel, a.status, a.due_at, a.note, a.created_at "
        "ORDER BY a.created_at DESC LIMIT 100", {"conference": conference}).result_set
    keys = ('id', 'target', 'target_name', 'channel', 'status', 'due_at', 'note', 'created_at')
    return [dict(zip(keys, row)) for row in rows]


def interpret_action(store, conference, text, selected_target=None, now=None):
    if not isinstance(text, str) or not text.strip() or len(text) > 800:
        raise ValueError('Use a short follow-up request, up to 800 characters.')
    if re.search(r"\b(?:don't|do not|cancel|delete|remove)\b", text, re.I):
        raise ValueError('No action saved. Use Mark done to close an existing follow-up.')
    if not re.search(r'\b(?:follow[ -]?up|remind|message|email|text)\b', text, re.I):
        raise ValueError('Try: Remind me to follow up with a person on LinkedIn.')
    roster = conference_people(store, conference)
    people = {p['id']: p['name'] for role in ('confirmed_attendees', 'scheduled_speakers') for p in roster[role]}
    normalized = ' ' + re.sub(r'[^\w]+', ' ', text.casefold()).strip() + ' '
    matches = [pid for pid, name in people.items() if ' ' + re.sub(r'[^\w]+', ' ', name.casefold()).strip() + ' ' in normalized]
    if not matches:
        matches = [pid for pid, name in people.items() if ' ' + name.split()[0].casefold() + ' ' in normalized]
    if not matches and re.search(r'\b(?:them|him|her|this person)\b', text, re.I) and selected_target in people:
        matches = [selected_target]
    if len(matches) != 1:
        raise ValueError('Please use one person’s full name from this conference so I save the right follow-up.')
    target = matches[0]
    channels = [key for key, pattern in {'linkedin': r'linked\s*in', 'email': r'\be[ -]?mail\b', 'text': r'\b(?:text|sms)\b'}.items() if re.search(pattern, text, re.I)]
    if len(channels) > 1:
        raise ValueError('Please choose one channel: LinkedIn, email, or text.')
    channel = channels[0] if channels else 'unspecified'
    now = now or datetime.now(timezone.utc)
    due = ''
    relative = re.search(r'\bin (\d{1,3}) (minute|hour|day)s?\b', text, re.I)
    if relative:
        due = (now + timedelta(**{relative[2].lower() + 's': int(relative[1])})).isoformat()
    connected = bool(re.search(r'\b(?:we|I)\s+(?:already\s+)?connected\s+(?:on|via)\s+linked\s*in', text, re.I))
    return {'target': target, 'target_name': people[target], 'channel': channel, 'due_at': due,
            'note': text.strip(), 'connected_on_linkedin': connected}


def save_action(store, session, token, conference, text, request_id, selected_target=None, due_at=None):
    graph = _auth(store, session, token)
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', request_id):
        raise ValueError('A valid action request ID is required.')
    action = interpret_action(store, conference, text, selected_target)
    if due_at:
        if not isinstance(due_at, str) or len(due_at) > 40:
            raise ValueError('Choose a valid reminder time.')
        try:
            due = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
            if due.tzinfo is None: raise ValueError()
            action['due_at'] = due.astimezone(timezone.utc).isoformat()
        except ValueError:
            raise ValueError('Choose a reminder time with a timezone.') from None
    action_id = 'followup_' + hashlib.sha256((session + ':' + request_id).encode()).hexdigest()[:28]
    now = datetime.now(timezone.utc).isoformat()
    with store.lock:
        existing = store.query(graph, 'MATCH (a:FollowUp {id:$id}) RETURN a.note', {'id': action_id}).result_set
        if existing:
            if existing[0][0] != action['note']: raise ValueError('This request was already used. Start a new action.')
        else:
            count = store.query(graph, 'MATCH (a:FollowUp) RETURN count(a)').result_set[0][0]
            if count >= 100: raise ValueError('This session already has 100 follow-ups.')
            store.query(graph,
                "MATCH (you:Person {id:'you'}) "
                "MERGE (p:Contact {public_id:$target}) SET p.name=$name "
                "CREATE (a:FollowUp {id:$id, conference_id:$conference, channel:$channel, "
                "status:'pending', due_at:$due, note:$note, created_at:$now}) "
                "CREATE (you)-[:HAS_ACTION]->(a)-[:ABOUT]->(p)",
                {'id': action_id, 'target': action['target'], 'name': action['target_name'], 'conference': conference,
                 'channel': action['channel'], 'due': action['due_at'], 'note': action['note'], 'now': now})
            if action['connected_on_linkedin']:
                store.query(graph,
                    "MATCH (you:Person {id:'you'}), (p:Contact {public_id:$target}) "
                    "MERGE (you)-[r:CONNECTED_ON {platform:'linkedin'}]->(p) "
                    "SET r.basis='requester_reported', r.observed_at=$now",
                    {'target': action['target'], 'now': now})
    return {'items': list_actions(store, session, token, conference), 'saved_id': action_id,
            'reply': f"Saved: follow up with {action['target_name']} via {action['channel'] if action['channel'] != 'unspecified' else 'your preferred channel'}."}


def complete_action(store, session, token, conference, action_id):
    graph = _auth(store, session, token)
    if not isinstance(action_id, str) or not re.fullmatch(r'followup_[a-f0-9]{28}', action_id):
        raise ValueError('Invalid follow-up action.')
    store.query(graph, "MATCH (a:FollowUp {id:$id}) WHERE a.conference_id=$conference SET a.status='done'",
                {'id': action_id, 'conference': conference})
    return {'items': list_actions(store, session, token, conference)}
