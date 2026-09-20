from .beliefs import load_belief
from .database import (
    add_memory,
    get_connection,
    record_event,
)
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
) -> str:
    if choice_id == "ASK_IDENTITY":
        return (
            f"Puedes llamarme {actor_name}. "
            "¿Qué necesitas saber?"
        )

    if choice_id == "ASK_SIGNAL":
        belief = load_belief(
            actor_id,
            "NODE_07",
        )
        if belief is None:
            return "No tengo información suficiente sobre esa señal."
        if belief.source in {
            "DIRECT_PERCEPTION",
            "ACTIVE_INVESTIGATION",
        }:
            return (
                "He examinado esa señal personalmente. "
                "Su comportamiento merece atención."
            )
        return (
            "He recibido información sobre esa señal, "
            "pero todavía tendría que contrastarla."
        )

    if choice_id == "TELL_OBSERVED":
        return (
            "Entiendo. Tendré en cuenta tu testimonio, "
            "pero necesito contrastarlo por mi cuenta."
        )

    raise ValueError("UNKNOWN_DIALOGUE_CHOICE")


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
        conn.commit()

    add_memory(
        actor_id,
        (
            f"During conversation {interaction.id}, "
            f"{PLAYER_ID} said: {player_line}"
        ),
    )

    record_event(
        minute=minute,
        actor_id=PLAYER_ID,
        action="DIALOGUE_CHOICE",
        target=interaction.id,
        details=choice_id,
    )

    return conversation_payload(
        interaction.id,
        actor_id,
        actor_name,
    )
