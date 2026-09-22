"""D11 experiences authored only by successful World Core operations.

No proximity witnesses, inferred participation, model writes or legacy backfill.
The caller owns the transaction; episode keys make retries idempotent.
"""
import json
import re
from .database import get_connection
from .general_claims import _clean


def initialize_experiences(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS agent_experiences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id TEXT NOT NULL,
        episode_key TEXT NOT NULL,
        kind TEXT NOT NULL,
        role TEXT NOT NULL,
        minute INTEGER NOT NULL,
        location TEXT NOT NULL,
        target TEXT,
        participants TEXT NOT NULL,
        source_event_id INTEGER,
        origin_turn_id INTEGER,
        UNIQUE(owner_id, episode_key)
    )''')
    conn.execute('''CREATE INDEX IF NOT EXISTS idx_experiences_owner
        ON agent_experiences(owner_id, minute, id)''')


def record_experience(conn, *, owner, key, kind, role, minute, location,
                      target=None, participants=(), event_id=None, turn_id=None):
    initialize_experiences(conn)
    people = sorted(set(participants))
    if owner not in people or not location:
        raise ValueError('INVALID_EXPERIENCE_PARTICIPANT')
    conn.execute('''INSERT OR IGNORE INTO agent_experiences
        (owner_id,episode_key,kind,role,minute,location,target,participants,
         source_event_id,origin_turn_id) VALUES (?,?,?,?,?,?,?,?,?,?)''',
        (owner, key, kind, role, minute, location, target,
         json.dumps(people), event_id, turn_id))


def record_encounter(conn, actor_id, minute, turn_id):
    people = ('PLAYER_1', actor_id)
    locations = dict(conn.execute('SELECT id,location FROM agents WHERE id IN (?,?)', people))
    if len(locations) != 2 or locations[people[0]] != locations[people[1]]:
        raise ValueError('ACTOR_NOT_PRESENT')
    for owner in people:
        record_experience(conn, owner=owner, key=f'encounter:{turn_id}',
            kind='ENCOUNTER', role='PARTICIPANT', minute=minute,
            location=locations[owner], participants=people, turn_id=turn_id)


def record_action_experience(conn, event_id, actor_id, action, target, minute, location):
    if action not in {'INVESTIGATE', 'OBSERVE'}:
        return
    record_experience(conn, owner=actor_id, key=f'action:{event_id}',
        kind=action, role='INVESTIGATOR' if action == 'INVESTIGATE' else 'OBSERVER',
        minute=minute, location=location, target=target,
        participants=(actor_id,), event_id=event_id)


def record_shared_attention(actions):
    """Accepted snapshots from ONE resolve_intents batch, never a time-window join.

    Observing the same target establishes shared attention, not access to
    another actor's findings. Movement within a batch invalidates pairing.
    """
    moved = {a['actor'] for a in actions if a['action'] == 'MOVE'}
    with get_connection() as conn:
        for investigation in actions:
            if investigation['action'] != 'INVESTIGATE':
                continue
            for other in actions:
                if (other['actor'] == investigation['actor']
                    or other['action'] not in {'OBSERVE', 'INVESTIGATE'}
                    or other['target'] != investigation['target']
                    or other['location'] != investigation['location']
                    or other['actor'] in moved or investigation['actor'] in moved):
                    continue
                people = (investigation['actor'], other['actor'])
                key = 'shared:' + ':'.join(str(i) for i in sorted((investigation['id'], other['id'])))
                for action in (investigation, other):
                    record_experience(conn, owner=action['actor'], key=key,
                        kind='SHARED_ATTENTION',
                        role='INVESTIGATOR' if action['action'] == 'INVESTIGATE' else 'OBSERVER',
                        minute=action['minute'], location=action['location'],
                        target=action['target'], participants=people,
                        event_id=action['id'])


def experience_request(query):
    text = _clean(query or '').strip().strip('¿?').strip()
    match = re.fullmatch(r'que paso la ultima vez que estuvimos en (?:la |el )?(.+)', text)
    if match:
        place = {'estacion': 'STATION', 'apartamento': 'APARTMENT',
                 'station': 'STATION', 'apartment': 'APARTMENT'}.get(match[1])
        return {'mode': 'encounter', 'location': place, 'unsupported': place is None}
    if re.fullmatch(r'estabas conmigo cuando investigamos (?:esa senal|la senal|node_\d+)', text):
        node = re.search(r'node_\d+', text)
        return {'mode': 'shared', 'target': node[0].upper() if node else None}
    if re.fullmatch(r'(?:eso|la senal|node_\d+) lo viste tu o te lo conte yo', text):
        node = re.search(r'node_\d+', text)
        return {'mode': 'source', 'target': node[0].upper() if node else None}
    return None


def experience_context(owner, query, interaction_id=None):
    request = experience_request(query)
    with get_connection() as conn:
        initialize_experiences(conn)
        clauses, params = ['owner_id=?'], [owner]
        if request and request.get('location'):
            clauses.append('location=?')
            params.append(request['location'])
        if request and request.get('target'):
            clauses.append('target=?')
            params.append(request['target'])
        if request and request['mode'] == 'encounter':
            # Latest encounter, not an unrelated solo event at the same place.
            clauses.append("kind='ENCOUNTER'")
            if interaction_id is not None:
                greeting = conn.execute("""SELECT MAX(id) FROM player_conversation_turns
                    WHERE interaction_id=? AND source='DETERMINISTIC_GREETING'""",
                    (interaction_id,)).fetchone()[0]
                if greeting is not None:
                    clauses.append('origin_turn_id < ?')
                    params.append(greeting)
        if request and request['mode'] == 'shared':
            clauses.append("kind='SHARED_ATTENTION'")
            clauses.append("instr(participants, '\"PLAYER_1\"') > 0")
        rows = conn.execute('''SELECT id,kind,role,minute,location,target,
            participants,source_event_id,origin_turn_id FROM agent_experiences
            WHERE ''' + ' AND '.join(clauses) + ' ORDER BY minute DESC,id DESC LIMIT 12', params).fetchall()
    records = [dict(zip(('id','kind','role','minute','location','target',
                        'participants','source_event_id','origin_turn_id'), row)) for row in rows]
    for record in records:
        record['participants'] = json.loads(record['participants'])
        record['owner_id'] = owner
        record['source_kind'] = 'WORLD_CORE_EXPERIENCE'
    return {'request': request, 'records': records}


def experience_reply(context):
    bundle = context.get('experiences', {})
    request = bundle.get('request')
    if not request:
        return None
    if request.get('unsupported'):
        return 'No puedo identificar ese lugar en mis recuerdos.'
    records = bundle['records']
    if request['mode'] == 'encounter':
        records = [r for r in records if 'PLAYER_1' in r['participants']]
        if not records:
            return 'No tengo registrado un encuentro contigo en ese lugar.'
        return f"La última vez que nos encontramos allí conversamos, en el minuto {records[0]['minute']}. No deduzco de ese encuentro que investigáramos juntos."
    if request['mode'] == 'shared' and not records:
        return 'No tengo registrada una investigación compartida contigo sobre esa señal.'
    target = request.get('target')
    if not target:
        targets = {r['target'] for r in records if r['target']}
        if len(targets) != 1:
            return '¿A qué señal te refieres? Necesito identificarla para distinguir lo que viví de lo que me contaste.'
        target = next(iter(targets))
    relevant = [r for r in records if r['target'] == target]
    if request['mode'] == 'shared':
        shared = [r for r in relevant if r['kind'] == 'SHARED_ATTENTION' and 'PLAYER_1' in r['participants']]
        if not shared:
            return 'No tengo registrada una investigación compartida contigo sobre esa señal.'
        role = 'investigué' if shared[0]['role'] == 'INVESTIGATOR' else 'observé'
        return f"Sí, yo {role} {target} durante esa experiencia compartida contigo, en el minuto {shared[0]['minute']}. Eso no me permite conocer tus conclusiones."
    direct = [r for r in relevant if r['kind'] in {'INVESTIGATE', 'OBSERVE', 'SHARED_ATTENTION'}]
    if direct:
        verb = 'investigué' if direct[0]['role'] == 'INVESTIGATOR' else 'observé'
        return f"Yo {verb} {target} personalmente, en el minuto {direct[0]['minute']}. Eso no demuestra que todo lo que me contaste sea cierto."
    for memory in reversed(context.get('memory_records', [])):
        if target.casefold() not in memory['text'].casefold():
            continue
        if memory['source_kind'] in {'DIRECT_PERCEPTION', 'ACTIVE_INVESTIGATION'}:
            return f"Tengo un recuerdo de observación o investigación propia de {target}; no depende solo de lo que me contaste."
        if memory['source_kind'] == 'PLAYER_TESTIMONY' and '?' not in memory['text'] and '¿' not in memory['text']:
            return f"Me hablaste de {target}, pero ese testimonio no demuestra que yo lo observara personalmente."
    return 'No tengo registrada una observación propia de esa señal; tampoco puedo afirmar sin un testimonio concreto que me lo contaras tú.'
