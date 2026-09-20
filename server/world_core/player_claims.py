"""D8-r1: explicit, source-attributed player claims for reliable recall.

A player's statement is a claim *to one NPC*, not a world fact and not
an account credential. Keep the most recently reported value for a
narrowly recognized in-game password label, including legacy free turns.
No password is generated or inferred when the player did not provide one.
"""
import re
import unicodedata

from .database import get_connection


PASSWORD_ASSIGNMENT = re.compile(
    r"\b(?:mi\s+)?(?:nueva\s+|actual\s+)?contrase(?:ñ|n)a"
    r"(?:\s+(?:nueva|actual|ahora))?\s*(?:es|:|=)\s*"
    r"[\"'«]?([A-Za-z0-9][A-Za-z0-9_-]{2,63})(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
PASSWORD_QUESTION = re.compile(
    r"\b(?:contrase(?:ñ|n)a|password)\b",
    re.IGNORECASE,
)


def asks_about_password(text: str) -> bool:
    return bool(PASSWORD_QUESTION.search(text))


def extract_password_claim(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    match = PASSWORD_ASSIGNMENT.search(text)
    return match.group(1) if match else None


def initialize_player_claims() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_player_claims (
                recipient_id TEXT NOT NULL,
                speaker_id TEXT NOT NULL,
                claim_key TEXT NOT NULL,
                claim_value TEXT NOT NULL,
                origin_turn_id INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                source_kind TEXT NOT NULL,
                PRIMARY KEY (recipient_id, speaker_id, claim_key)
            )
            """
        )


def record_player_claim(
    conn,
    recipient_id: str,
    player_text: str,
    player_turn_id: int,
    minute: int,
) -> None:
    value = extract_password_claim(player_text)
    if value is None:
        return
    # Never upgrade a player's words to node_beliefs or agent observations.
    conn.execute(
        """
        INSERT INTO agent_player_claims (
            recipient_id, speaker_id, claim_key, claim_value,
            origin_turn_id, minute, source_kind
        )
        VALUES (?, 'PLAYER_1', 'IN_GAME_PASSWORD', ?, ?, ?, 'PLAYER_TESTIMONY')
        ON CONFLICT(recipient_id, speaker_id, claim_key)
        DO UPDATE SET
            claim_value = excluded.claim_value,
            origin_turn_id = excluded.origin_turn_id,
            minute = excluded.minute,
            source_kind = excluded.source_kind
        WHERE excluded.origin_turn_id > agent_player_claims.origin_turn_id
        """,
        (recipient_id, value, player_turn_id, minute),
    )


def _legacy_password_claim(agent_id: str):
    """Read D7/D8 save files without changing their old transcripts.

    Only first-person, explicit password assignment by the player counts.
    A phrase like 'esta es mi contraseña' with no actual value does NOT.
    """
    with get_connection() as conn:
        # Never look at conversations with another recipient.
        row = conn.execute(
            """
            SELECT t.id, t.text, t.minute
            FROM player_conversation_turns t
            JOIN interactions i ON i.id = t.interaction_id
            WHERE i.recipient_id = ?
              AND i.initiator_id = 'PLAYER_1'
              AND i.topic = 'PLAYER_INITIATED_CONVERSATION'
              AND t.speaker_id = 'PLAYER_1'
            ORDER BY t.id DESC LIMIT 1000
            """,
            (agent_id,),
        ).fetchall()
    for turn_id, text, minute in row:
        value = extract_password_claim(text)
        if value is not None:
            return (turn_id, value, minute)
    return None


def get_player_claims(
    agent_id: str, query: str | None = None,
) -> list[dict]:
    if not asks_about_password(query or ""):
        return []
    initialize_player_claims()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT claim_value, origin_turn_id, minute, source_kind
            FROM agent_player_claims
            WHERE recipient_id = ?
              AND speaker_id = 'PLAYER_1'
              AND claim_key = 'IN_GAME_PASSWORD'
            """,
            (agent_id,),
        ).fetchone()
    legacy = _legacy_password_claim(agent_id)
    if legacy is not None and (row is None or legacy[0] > row[1]):
        row = (legacy[1], legacy[0], legacy[2], "LEGACY_PLAYER_TESTIMONY")
    if row is None:
        return []
    return [{
        "claim_key": "IN_GAME_PASSWORD",
        "claim_value": row[0],
        "origin_turn_id": row[1],
        "minute": row[2],
        "source_kind": row[3],
        "source_actor_id": "PLAYER_1",
    }]
