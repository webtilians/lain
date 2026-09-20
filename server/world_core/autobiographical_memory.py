"""D10 private autobiographical knowledge, projected from immutable turns.

A version describes what this recipient HEARD, not what is true now. Turn
IDs break same-minute ties. Unknown historical locations are never guessed.
"""
import re

from .database import get_connection
from .general_claims import _clean, parse_personal_statement, requested_topic


def timeline_request(query):
    text = _clean(query or '').strip().strip('¿?').strip()
    patterns = (
        (r'(?:como se llamaba|cual era) mi (.+?)(?: de antes| antes)?', 'previous'),
        (r'que te dije primero sobre mi (.+)', 'first'),
        (r'que te dije antes sobre mi (.+)', 'previous'),
        (r'(?:que te he dicho|que recuerdas|que ha cambiado) sobre mi (.+)', 'history'),
        (r'(?:como se llama|cual es|que nombre tiene) mi (.+?) ahora', 'current'),
    )
    for pattern, mode in patterns:
        match = re.fullmatch(pattern, text)
        if match:
            topic = requested_topic('¿Cuál es mi ' + match[1] + '?')
            if topic:
                return topic, mode
    topic = requested_topic(query)
    return (topic, 'current') if topic else None


def knowledge_timeline(agent_id, query):
    request = timeline_request(query)
    if request is None:
        return None
    topic, mode = request
    versions = []
    first = None
    count = 0
    with get_connection() as conn:
        # Existing saves are read directly. Only recipient-owned player
        # turns qualify; AI-generated lines cannot become testimony.
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='player_conversation_turns'"
        ).fetchone()
        if exists:
            rows = conn.execute('''
                SELECT t.id, t.text, t.minute, t.interaction_id
                FROM player_conversation_turns t
                JOIN interactions i ON i.id=t.interaction_id
                WHERE i.recipient_id=? AND i.initiator_id='PLAYER_1'
                  AND i.topic='PLAYER_INITIATED_CONVERSATION'
                  AND t.speaker_id='PLAYER_1'
                  AND t.source IN ('PLAYER_FREE_TEXT', 'PLAYER_CHOICE')
                ORDER BY t.id DESC
            ''', (agent_id,))
            for turn_id, text, minute, interaction_id in rows:
                claim = parse_personal_statement(text)
                if claim and claim[0] == topic:
                    count += 1
                    item = {
                        'owner_id': agent_id, 'topic_key': topic,
                        'reported_text': text, 'reported_value': claim[2],
                        'source_kind': 'PLAYER_TESTIMONY',
                        'source_actor_id': 'PLAYER_1',
                        'origin_turn_id': turn_id, 'received_minute': minute,
                        'interaction_id': interaction_id,
                    }
                    first = item
                    if len(versions) < 12:
                        versions.append(item)
    # Keep context bounded, including first and latest even for long histories.
    versions.reverse()
    selected = versions if count <= 12 else [first, *versions[-11:]]
    for item in selected:
        item['knowledge_status'] = 'CURRENT_TESTIMONY' if item is versions[-1] else 'EARLIER_TESTIMONY'
    return {'topic_key': topic, 'mode': mode, 'versions': selected,
            'total_versions': count, 'truncated': count > 12}


def temporal_reply(timeline):
    if not timeline:
        return None
    versions = timeline['versions']
    if not versions:
        return 'No recuerdo que me hayas contado ese dato a mí.'
    mode = timeline['mode']
    if mode == 'current':
        return f"Lo último que me dijiste fue: «{versions[-1]['reported_text']}»."
    if mode == 'previous':
        if len(versions) < 2:
            return 'Solo recuerdo una versión de lo que me contaste; no conozco una anterior.'
        return (f"Antes me dijiste: «{versions[-2]['reported_text']}». "
                f"Después me dijiste: «{versions[-1]['reported_text']}».")
    if mode == 'first':
        return f"Lo primero que me dijiste fue: «{versions[0]['reported_text']}»."
    return (f"Primero me dijiste: «{versions[0]['reported_text']}». "
            f"Lo último fue: «{versions[-1]['reported_text']}».")
