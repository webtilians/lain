"""D9: per-recipient, source-attributed *player statements*, not world facts.

Narrow deterministic support for explicit personal attributes without a
custom rule for each topic: 'mi [topic] es [value]' or 'mi [topic] se llama
[value]'. Older versions remain in the transcript; the latest explicit
statement wins for a direct question about the same topic. Unknown or
ambiguous phrasing is left to ordinary episodic retrieval (no fabricated
structured fact).
"""
import re
import unicodedata

from .database import get_connection


WORDS = r"A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_-"
TOPIC_WORD = rf"[{WORDS}]+"
TOPIC = rf"(?P<topic>{TOPIC_WORD}(?:\s+{TOPIC_WORD}){{0,3}})"
VALUE = rf"(?P<value>[{WORDS}](?:[{WORDS}\s-]{{0,79}}[{WORDS}])?)"

# Avoid accidentally interpreting "mi perro es..." embedded inside a
# quote, question or subordinate clause as a statement by the player.
_ASSIGNMENT = re.compile(
    rf"^\s*mi\s+{TOPIC}\s+"
    rf"(?P<verb>ahora\s+se\s+llama|se\s+llama|ahora\s+es|es)\s+"
    rf"{VALUE}\s*[.!]?\s*$",
    re.IGNORECASE,
)
_DIRECT_QUESTION = re.compile(
    rf"^\s*[¿]?\s*(?:cu[aá]l\s+es|c[oó]mo\s+se\s+llama)"
    rf"\s+mi\s+{TOPIC}\s*[?]?\s*$",
    re.IGNORECASE,
)
_QUESTION_ABOUT = re.compile(
    rf"^\s*[¿]?\s*(?:recuerdas|qu[eé]\s+sabes)\s+"
    rf"(?:lo\s+)?(?:que\s+te\s+dije\s+)?(?:sobre|de)\s+"
    rf"mi\s+{TOPIC}\s*[?]?\s*$",
    re.IGNORECASE,
)
BANNED_TOPICS = frozenset({
    "contrasena", "clave", "codigo", "password", "pin",
})


def _clean(value: str) -> str:
    norm = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in norm if not unicodedata.combining(c))


def _topic_key(topic: str) -> str:
    words = [word for word in _clean(topic).split()
             if word not in {"actual", "ahora", "nueva", "nuevo"}]
    return " ".join(words).strip()


def parse_personal_statement(text: str):
    if not isinstance(text, str):
        return None
    match = _ASSIGNMENT.fullmatch(text)
    if match is None:
        return None
    topic = match.group("topic").strip()
    key = _topic_key(topic)
    value = match.group("value").strip().rstrip(".!")
    if not key or key in BANNED_TOPICS or not value:
        return None
    if len(value) > 80 or any(token in value.casefold().split()
        for token in ("porque", "aunque", "pero", "cuando", "entonces")):
        return None
    return key, topic, value, text.strip()


def requested_topic(query: str | None) -> str | None:
    if not query:
        return None
    match = _DIRECT_QUESTION.fullmatch(query)
    if match is None:
        match = _QUESTION_ABOUT.fullmatch(query)
    if match is None:
        return None
    key = _topic_key(match.group("topic"))
    return key if key and key not in BANNED_TOPICS else None


def initialize_general_claims() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_player_general_claims (
                recipient_id TEXT NOT NULL,
                speaker_id TEXT NOT NULL,
                topic_key TEXT NOT NULL,
                topic_label TEXT NOT NULL,
                reported_value TEXT NOT NULL,
                reported_text TEXT NOT NULL,
                origin_turn_id INTEGER NOT NULL,
                received_minute INTEGER NOT NULL,
                source_kind TEXT NOT NULL,
                PRIMARY KEY (recipient_id, speaker_id, topic_key)
            )
            """
        )


def record_general_claim(
    conn, recipient_id: str, player_text: str,
    player_turn_id: int, minute: int,
) -> None:
    claim = parse_personal_statement(player_text)
    if claim is None:
        return
    key, topic, value, statement = claim
    conn.execute(
        """
        INSERT INTO agent_player_general_claims
        (recipient_id, speaker_id, topic_key, topic_label, reported_value,
         reported_text, origin_turn_id, received_minute, source_kind)
        VALUES (?, 'PLAYER_1', ?, ?, ?, ?, ?, ?, 'PLAYER_TESTIMONY')
        ON CONFLICT(recipient_id, speaker_id, topic_key)
        DO UPDATE SET
            topic_label=excluded.topic_label,
            reported_value=excluded.reported_value,
            reported_text=excluded.reported_text,
            origin_turn_id=excluded.origin_turn_id,
            received_minute=excluded.received_minute,
            source_kind=excluded.source_kind
        WHERE excluded.origin_turn_id > agent_player_general_claims.origin_turn_id
        """,
        (recipient_id, key, topic, value, statement, player_turn_id, minute),
    )


def get_general_claims(agent_id: str, query: str | None) -> list[dict]:
    topic = requested_topic(query)
    if topic is None:
        return []
    initialize_general_claims()
    with get_connection() as conn:
        current = conn.execute(
            """
            SELECT topic_label, reported_value, reported_text,
                   origin_turn_id, received_minute, source_kind
            FROM agent_player_general_claims
            WHERE recipient_id = ? AND speaker_id = 'PLAYER_1'
              AND topic_key = ?
            """,
            (agent_id, topic),
        ).fetchone()

        # D7 and D8 saves may contain pre-index player statements. This
        # migration is read-only, bounded and filtered to this recipient.
        legacy = conn.execute(
            """
            SELECT t.id, t.text, t.minute
            FROM player_conversation_turns t
            JOIN interactions i ON i.id = t.interaction_id
            WHERE i.recipient_id = ? AND i.initiator_id = 'PLAYER_1'
              AND i.topic = 'PLAYER_INITIATED_CONVERSATION'
              AND t.speaker_id = 'PLAYER_1'
            ORDER BY t.id DESC LIMIT 1000
            """,
            (agent_id,),
        ).fetchall()

    for turn_id, text, minute in legacy:
        claim = parse_personal_statement(text)
        if claim is not None and claim[0] == topic:
            if current is None or turn_id > current[3]:
                current = (
                    claim[1], claim[2], claim[3], turn_id, minute,
                    "LEGACY_PLAYER_TESTIMONY",
                )
            break
    if current is None:
        return []
    return [{
        "topic_key": topic,
        "topic_label": current[0],
        "reported_value": current[1],
        "reported_text": current[2],
        "origin_turn_id": current[3],
        "received_minute": current[4],
        "source_kind": current[5],
        "source_actor_id": "PLAYER_1",
    }]
