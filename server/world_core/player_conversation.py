from .shared_experiences import record_encounter
from .i18n import t
from .beliefs import load_belief
from .database import get_connection
from .episodic_memory import initialize_memory_provenance, save_episodic_memory
from .agent_context import AgentContextBuilder
from .llm_dialogue import generate_dialogue_reply
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


def require_conversation(
    actor_id: str,
    allow_resuming: bool = False,
    player_id: str = "PLAYER_1",
):
    with get_connection() as conn:
        player = conn.execute(
            """
            SELECT location
            FROM agents
            WHERE id = ?
            """,
            (player_id,),
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
    if actor_id == player_id:
        raise ValueError("CANNOT_TALK_TO_SELF")
    if actor[2] == "HUMAN":
        raise ValueError("INVALID_CONVERSATION_TARGET")
    if player[0] != actor[1]:
        raise ValueError("ACTOR_NOT_PRESENT")

    interaction = find_open_interaction(
        initiator_id=player_id,
        recipient_id=actor_id,
        topic=CONVERSATION_TOPIC,
    )

    permitted_statuses = {"OPEN", "RESUMING"} if allow_resuming else {"OPEN"}
    if interaction is None or interaction.status not in permitted_statuses:
        raise ValueError("NO_OPEN_CONVERSATION")

    return interaction, actor[0]


def player_observed_signal(
    player_id: str = "PLAYER_1",
) -> bool:
    belief = load_belief(
        player_id,
        "NODE_07",
    )
    return (
        belief is not None
        and belief.source in {
            "DIRECT_PERCEPTION",
            "ACTIVE_INVESTIGATION",
        }
    )


def hint_layer(player_id: str, actor_id: str):
    """The layer this character can help with, if `pista` sent the player to them."""
    from . import hints
    if not actor_id:
        return None
    with get_connection() as conn:
        return hints.expert_layer(conn, player_id, actor_id)


def available_choices(
    player_id: str = "PLAYER_1",
    actor_id: str = "",
) -> list[dict]:
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

    if player_observed_signal(player_id=player_id):
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
    # Stored turns and game logic stay in Spanish; only what is shown changes.
    for choice in result:
        choice["text"] = t(choice["text"])
    layer = hint_layer(player_id, actor_id)
    if layer is not None:
        from . import hints
        result.insert(len(result) - 1, {"id": "ASK_HINT", "text": t(f'{len(result)}. "{hints.ask_line(layer)}"')})
    return result


def conversation_payload(
    interaction_id: str,
    actor_id: str,
    actor_name: str,
    player_id: str = "PLAYER_1",
) -> dict:
    initialize_conversation_turns()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, speaker_id, text, source
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

    line = t(row[2])
    if row[3] == "DETERMINISTIC_GREETING" and actor_id.startswith("RESIDENT_"):
        # The activity is translated on its own, then the sentence around it.
        line = resident_greeting(actor_id, actor_name, translate=True) or line
    return {
        "interaction_id": interaction_id,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "turn_id": row[0],
        "line": line,
        "response_source": row[3],
        "choices": available_choices(player_id=player_id, actor_id=actor_id),
    }


def resident_greeting(actor_id: str, actor_name: str, translate: bool = False, conn=None):
    """«Soy …. Ahora mismo: …. ¿Qué necesitas?», from the resident's current activity."""
    query = "SELECT activity FROM city_residents WHERE actor_id=?"
    if conn is not None:
        row = conn.execute(query, (actor_id,)).fetchone()
    else:
        with get_connection() as own:
            row = own.execute(query, (actor_id,)).fetchone()
    if row is None:
        return None
    activity = t(row[0]) if translate else row[0]
    text = f"Soy {actor_name}. Ahora mismo: {activity[:1].lower() + activity[1:]}. ¿Qué necesitas?"
    return t(text) if translate else text


def start_player_conversation(
    actor_id: str,
    minute: int,
    player_id: str = "PLAYER_1",
) -> dict:
    interaction, actor_name = require_conversation(
        actor_id, allow_resuming=True, player_id=player_id
    )
    initialize_conversation_turns()

    with get_connection() as conn:
        # Mark the session OPEN and append its greeting in one transaction.
        # If START is retried, the status is already OPEN and no duplicate
        # greeting is recorded. All previous turns remain in the database.
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute(
            "SELECT status FROM interactions WHERE id = ?",
            (interaction.id,),
        ).fetchone()
        if current is None or current[0] not in {"OPEN", "RESUMING"}:
            raise ValueError("NO_OPEN_CONVERSATION")

        existing = conn.execute(
            """
            SELECT id
            FROM player_conversation_turns
            WHERE interaction_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (interaction.id,),
        ).fetchone()

        if existing is None or current[0] == "RESUMING":
            greeting = (
                "Te escucho. ¿Qué quieres saber?"
                if existing is None
                else "Nos volvemos a encontrar. ¿Qué quieres contarme?"
            )
            if actor_id.startswith("RESIDENT_"):
                greeting = resident_greeting(actor_id, actor_name, conn=conn) or greeting
            greeting_turn = conn.execute(
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
                    greeting,
                    "DETERMINISTIC_GREETING",
                    minute,
                ),
            )
            record_encounter(
                conn, actor_id, minute, greeting_turn.lastrowid, player_id=player_id
            )
        if current[0] == "RESUMING":
            conn.execute(
                """
                UPDATE interactions SET status = 'OPEN', updated_minute = ?
                WHERE id = ? AND status = 'RESUMING'
                """,
                (minute, interaction.id),
            )

    return conversation_payload(
        interaction.id, actor_id, actor_name, player_id=player_id
    )


def build_agent_reply(
    actor_id: str,
    actor_name: str,
    choice_id: str,
    interaction_id: str,
):
    """Return text AND provenance from the agent's bounded context."""
    context = AgentContextBuilder().build(
        agent_id=actor_id,
        interaction_id=interaction_id,
        retrieval_query=CHOICES[choice_id],
    )
    return generate_dialogue_reply(
        context=context,
        choice_id=choice_id,
        # The model answers what the player read, in the player's language.
        choice_text=t(CHOICES[choice_id]),
    )


def reply_to_player_conversation(
    actor_id: str,
    choice_id: str,
    after_turn_id: int,
    minute: int,
    player_id: str = "PLAYER_1",
) -> dict:
    interaction, actor_name = require_conversation(actor_id, player_id=player_id)
    if choice_id == "ASK_HINT":
        return ask_for_hint(actor_id, actor_name, interaction.id, after_turn_id, minute, player_id)
    if choice_id not in CHOICES:
        raise ValueError("UNKNOWN_DIALOGUE_CHOICE")
    if choice_id == "TELL_OBSERVED" and not player_observed_signal(player_id=player_id):
        raise ValueError("EVIDENCE_NOT_AVAILABLE")
    initialize_conversation_turns()
    initialize_memory_provenance()

    # Reject ordinary retries before calling the model; avoid unnecessary
    # model costs. Repeat the check under a write lock to prevent double saves.
    with get_connection() as conn:
        latest = conn.execute(
            """
            SELECT id, speaker_id FROM player_conversation_turns
            WHERE interaction_id = ? ORDER BY id DESC LIMIT 1
            """,
            (interaction.id,),
        ).fetchone()
    if latest is None:
        raise ValueError("CONVERSATION_NOT_STARTED")
    if latest[0] != after_turn_id:
        return conversation_payload(
            interaction.id, actor_id, actor_name, player_id=player_id
        )
    if latest[1] != actor_id:
        raise ValueError("NOT_PLAYER_TURN")

    # Generating may take seconds. Never hold a SQLite write lock during
    # external model inference.
    reply = build_agent_reply(
        actor_id, actor_name, choice_id, interaction.id,
    )

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute(
            "SELECT status FROM interactions WHERE id = ?",
            (interaction.id,),
        ).fetchone()
        if current is None or current[0] != "OPEN":
            raise ValueError("NO_OPEN_CONVERSATION")
        positions = conn.execute(
            "SELECT id, location FROM agents WHERE id IN (?, ?)",
            (player_id, actor_id),
        ).fetchall()
        locations = {row[0]: row[1] for row in positions}
        if (
            player_id not in locations
            or actor_id not in locations
            or locations[player_id] != locations[actor_id]
        ):
            raise ValueError("ACTOR_NOT_PRESENT")
        latest = conn.execute(
            """
            SELECT id, speaker_id FROM player_conversation_turns
            WHERE interaction_id = ? ORDER BY id DESC LIMIT 1
            """,
            (interaction.id,),
        ).fetchone()
        if latest is None:
            raise ValueError("CONVERSATION_NOT_STARTED")
        if latest[0] == after_turn_id:
            if latest[1] != actor_id:
                raise ValueError("NOT_PLAYER_TURN")
            player_line = CHOICES[choice_id]
            player_turn = conn.execute(
                """
                INSERT INTO player_conversation_turns
                (interaction_id, speaker_id, text, source, minute)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    interaction.id,
                    player_id,
                    player_line,
                    "PLAYER_CHOICE",
                    minute,
                ),
            )
            conn.execute(
                """
                INSERT INTO player_conversation_turns
                (interaction_id, speaker_id, text, source, minute)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    interaction.id, actor_id, reply.text,
                    reply.source, minute,
                ),
            )
            save_episodic_memory(
                conn,
                actor_id,
                f"During conversation {interaction.id}, "
                f"{player_id} said: {player_line}",
                source_kind="PLAYER_TESTIMONY",
                source_actor_id=player_id,
                origin_turn_id=player_turn.lastrowid,
                minute=minute,
                shareable=False,
            )
            conn.execute(
                """
                INSERT INTO events
                (minute, actor_id, action, target, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    minute,
                    player_id,
                    "DIALOGUE_CHOICE",
                    interaction.id,
                    choice_id,
                ),
            )
        # Otherwise a concurrent request already committed this turn.
        # The caller receives the newest persisted response, without
        # duplicating turns, memories or events.

    return conversation_payload(
        interaction.id, actor_id, actor_name, player_id=player_id
    )


def ask_for_hint(actor_id: str, actor_name: str, interaction_id: str, after_turn_id: int,
                 minute: int, player_id: str) -> dict:
    """The expert `pista` sent the player to answers with the next hint, word for word (no model)."""
    from . import hints
    initialize_conversation_turns()
    initialize_memory_provenance()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT status FROM interactions WHERE id = ?", (interaction_id,)).fetchone()
        if current is None or current[0] != "OPEN":
            raise ValueError("NO_OPEN_CONVERSATION")
        locations = dict(conn.execute("SELECT id, location FROM agents WHERE id IN (?, ?)",
                                      (player_id, actor_id)).fetchall())
        if player_id not in locations or locations.get(actor_id) != locations[player_id]:
            raise ValueError("ACTOR_NOT_PRESENT")
        latest = conn.execute("SELECT id, speaker_id FROM player_conversation_turns WHERE interaction_id = ? "
                              "ORDER BY id DESC LIMIT 1", (interaction_id,)).fetchone()
        if latest is None:
            raise ValueError("CONVERSATION_NOT_STARTED")
        if latest[0] == after_turn_id:
            if latest[1] != actor_id:
                raise ValueError("NOT_PLAYER_TURN")
            layer = hints.expert_layer(conn, player_id, actor_id)
            if layer is None:
                raise ValueError("NO_HINT_HERE")
            question = hints.ask_line(layer)
            answer = hints.consult(conn, player_id, actor_id, minute)
            player_turn = conn.execute(
                "INSERT INTO player_conversation_turns (interaction_id, speaker_id, text, source, minute) "
                "VALUES (?, ?, ?, ?, ?)", (interaction_id, player_id, question, "PLAYER_CHOICE", minute))
            conn.execute(
                "INSERT INTO player_conversation_turns (interaction_id, speaker_id, text, source, minute) "
                "VALUES (?, ?, ?, ?, ?)", (interaction_id, actor_id, answer, "EXPERT_HINT", minute))
            save_episodic_memory(conn, actor_id, f"During conversation {interaction_id}, {player_id} asked me for help "
                                 f"with {hints.TITLES[layer]}.", source_kind="PLAYER_TESTIMONY",
                                 source_actor_id=player_id, origin_turn_id=player_turn.lastrowid, minute=minute,
                                 shareable=False)
            conn.execute("INSERT INTO events (minute, actor_id, action, target, details) VALUES (?, ?, ?, ?, ?)",
                         (minute, player_id, "HINT_FROM_EXPERT", actor_id, layer))
        # Otherwise a retry: the answer already saved is returned.
    return conversation_payload(interaction_id, actor_id, actor_name, player_id=player_id)


def pause_player_conversation(
    actor_id: str,
    interaction_id: str,
    minute: int,
    player_id: str = "PLAYER_1",
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
            or row[0] != player_id
            or row[1] != actor_id
            or row[2] != CONVERSATION_TOPIC
            or row[3] not in {"OPEN", "PAUSED", "RESUMING"}
        ):
            raise ValueError("CONVERSATION_NOT_AVAILABLE")
        if row[3] in {"OPEN", "RESUMING"}:
            conn.execute(
                """
                UPDATE interactions
                SET status = 'PAUSED', updated_minute = ?
                WHERE id = ? AND status IN ('OPEN', 'RESUMING')
                """,
                (minute, interaction_id),
            )

    return {"interaction_id": interaction_id, "status": "PAUSED"}
