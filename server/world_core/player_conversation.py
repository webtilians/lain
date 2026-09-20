from .beliefs import load_belief
from .database import get_connection
from .agent_context import AgentContextBuilder
from .dialogue_engine import DeterministicDialogueEngine
from .interactions import (
    find_open_interaction,
)


PLAYER_ID = "PLAYER_1"

CONVERSATION_TOPIC = (
    "PLAYER_INITIATED_CONVERSATION"
)

CHOICES = {
    "ASK_IDENTITY": "¿Quién eres?",
    "ASK_SIGNAL": "¿Qué sabes de NODE_07?",
    "TELL_OBSERVED": "He observado la señal.",
}


def initialize_conversation_turns() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            player_conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interaction_id TEXT NOT NULL,
                speaker_id TEXT NOT NULL,
                text TEXT NOT NULL,
                source TEXT NOT NULL,
                minute INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_player_conversation_turns
            ON player_conversation_turns (
                interaction_id, id
            )
            """
        )
        conn.commit()


def require_conversation(actor_id: str):
    with get_connection() as conn:
        player = conn.execute(
            """
            SELECT location
            FROM agents
            WHERE id = ?
            """,
            (PLAYER_ID,),
        ).fetchone()
        actor = conn.execute(
            """
            SELECT name, location, controller_type
            FROM agents
            WHERE id = ?
            """,
            (actor_id,),
        ).fetchone()

    if player is None:
        raise ValueError("PLAYER_NOT_FOUND")
    if actor is None:
        raise ValueError("ACTOR_NOT_FOUND")
    if actor_id == PLAYER_ID:
        raise ValueError("CANNOT_TALK_TO_SELF")
    if actor[2] == "HUMAN":
        raise ValueError("INVALID_CONVERSATION_TARGET")
    if player[0] != actor[1]:
        raise ValueError("ACTOR_NOT_PRESENT")

    interaction = find_open_interaction(
        initiator_id=PLAYER_ID,
        recipient_id=actor_id,
        topic=CONVERSATION_TOPIC,
    )

    if interaction is None:
        raise ValueError("NO_OPEN_CONVERSATION")

    return interaction, actor[0]


def player_observed_signal() -> bool:
    belief = load_belief(
        PLAYER_ID,
        "NODE_07",
    )
    return (
        belief is not None
        and belief.source in {
            "DIRECT_PERCEPTION",
            "ACTIVE_INVESTIGATION",
        }
    )


def available_choices() -> list[dict]:
    result = [
        {
            "id": "ASK_IDENTITY",
            "text": '1. "¿Quién eres?"',
        },
        {
            "id": "ASK_SIGNAL",
            "text": '2. "¿Qué sabes de NODE_07?"',
        },
    ]

    if player_observed_signal():
        result.append(
            {
                "id": "TELL_OBSERVED",
                "text": '3. "He observado la señal."',
            }
        )

    result.append(
        {
            "id": "LEAVE",
            "text": "Alejarse",
        }
    )
    return result


def conversation_payload(
    interaction_id: str,
    actor_id: str,
    actor_name: str,
) -> dict:
    initialize_conversation_turns()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, speaker_id, text
            FROM player_conversation_turns
            WHERE interaction_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (interaction_id,),
        ).fetchone()

    if row is None:
        raise ValueError("CONVERSATION_NOT_STARTED")
    if row[1] != actor_id:
        raise ValueError("CONVERSATION_AWAITING_AGENT")

    return {
        "interaction_id": interaction_id,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "turn_id": row[0],
        "line": row[2],
        "choices": available_choices(),
    }


def start_player_conversation(
    actor_id: str,
    minute: int,
) -> dict:
    interaction, actor_name = require_conversation(actor_id)
    initialize_conversation_turns()

    with get_connection() as conn:
        # An initial line must be inserted only once, even with two callers.
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """
            SELECT id
            FROM player_conversation_turns
            WHERE interaction_id = ?
            LIMIT 1
            """,
            (interaction.id,),
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO player_conversation_turns (
                    interaction_id,
                    speaker_id,
                    text,
                    source,
                    minute
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    interaction.id,
                    actor_id,
                    "Te escucho. ¿Qué quieres saber?",
                    "DETERMINISTIC_DIALOGUE",
                    minute,
                ),
            )
            conn.commit()

    return conversation_payload(
        interaction.id,
        actor_id,
        actor_name,
    )


def build_agent_reply(
    actor_id: str,
    actor_name: str,
    choice_id: str,
    interaction_id: str,
) -> str:
    # Identity and evidence are read from this agent's persisted context,
    # never from the client or the objective world state.
    context = AgentContextBuilder().build(
        agent_id=actor_id,
        interaction_id=interaction_id,
    )
    return DeterministicDialogueEngine().generate(
        context=context,
        choice_id=choice_id,
    )


def reply_to_player_conversation(
    actor_id: str,
    choice_id: str,
    after_turn_id: int,
    minute: int,
) -> dict:
    interaction, actor_name = require_conversation(actor_id)

    if choice_id not in CHOICES:
        raise ValueError("UNKNOWN_DIALOGUE_CHOICE")
    if choice_id == "TELL_OBSERVED" and not player_observed_signal():
        raise ValueError("EVIDENCE_NOT_AVAILABLE")

    initialize_conversation_turns()

    with get_connection() as conn:
        # Serialize concurrent requests before checking the turn identifier.
        # Both turns, memory and event commit (or roll back) together.
        conn.execute("BEGIN IMMEDIATE")
        latest = conn.execute(
            """
            SELECT id, speaker_id
            FROM player_conversation_turns
            WHERE interaction_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (interaction.id,),
        ).fetchone()

        if latest is None:
            raise ValueError("CONVERSATION_NOT_STARTED")
        if latest[0] != after_turn_id:
            return conversation_payload(
                interaction.id,
                actor_id,
                actor_name,
            )
        if latest[1] != actor_id:
            raise ValueError("NOT_PLAYER_TURN")

        player_line = CHOICES[choice_id]
        agent_line = build_agent_reply(
            actor_id,
            actor_name,
            choice_id,
            interaction.id,
        )

        conn.execute(
            """
            INSERT INTO player_conversation_turns (
                interaction_id,
                speaker_id,
                text,
                source,
                minute
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                interaction.id,
                PLAYER_ID,
                player_line,
                "PLAYER_CHOICE",
                minute,
            ),
        )
        conn.execute(
            """
            INSERT INTO player_conversation_turns (
                interaction_id,
                speaker_id,
                text,
                source,
                minute
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                interaction.id,
                actor_id,
                agent_line,
                "DETERMINISTIC_DIALOGUE",
                minute,
            ),
        )
        conn.execute(
            """
            INSERT INTO agent_memory (agent_id, memory)
            VALUES (?, ?)
            """,
            (
                actor_id,
                f"During conversation {interaction.id}, "
                f"{PLAYER_ID} said: {player_line}",
            ),
        )
        conn.execute(
            """
            INSERT INTO events (minute, actor_id, action, target, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (minute, PLAYER_ID, "DIALOGUE_CHOICE", interaction.id, choice_id),
        )
        # The connection context commits every part of this reply together.

    return conversation_payload(
        interaction.id,
        actor_id,
        actor_name,
    )


def pause_player_conversation(
    actor_id: str,
    interaction_id: str,
    minute: int,
) -> dict:
    """Pause the player's own conversation without deleting its transcript."""
    initialize_conversation_turns()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT initiator_id, recipient_id, topic, status
            FROM interactions WHERE id = ?
            """,
            (interaction_id,),
        ).fetchone()
        if (
            row is None
            or row[0] != PLAYER_ID
            or row[1] != actor_id
            or row[2] != CONVERSATION_TOPIC
            or row[3] not in {"OPEN", "PAUSED"}
        ):
            raise ValueError("CONVERSATION_NOT_AVAILABLE")
        if row[3] == "OPEN":
            conn.execute(
                """
                UPDATE interactions
                SET status = 'PAUSED', updated_minute = ?
                WHERE id = ? AND status = 'OPEN'
                """,
                (minute, interaction_id),
            )

    return {"interaction_id": interaction_id, "status": "PAUSED"}
