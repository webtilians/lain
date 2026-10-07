"""D7 player free-text turns; the input is testimony, never an action.

This module intentionally calls World Core's existing conversation boundary
and persists the utterance, NPC response, memory and audit event atomically.
"""
from .agent_context import AgentContextBuilder
from .database import get_connection
from .episodic_memory import (
    initialize_memory_provenance,
    save_episodic_memory,
)
from .llm_dialogue import generate_dialogue_reply
from .character_sheets import generated_role_context
from .station_echo import actor_received_case_report
from .generated_entities import (
    create_entity_from_turn, initialize_generated_entities, suggest_entity,
    trace_reality,
)
from .player_claims import initialize_player_claims, record_player_claim
from .general_claims import initialize_general_claims, record_general_claim
from .player_conversation import (
    PLAYER_ID,
    conversation_payload,
    initialize_conversation_turns,
    require_conversation,
)


MAX_PLAYER_MESSAGE_LENGTH = 500


def validate_player_message(message: str) -> str:
    if not isinstance(message, str):
        raise ValueError("INVALID_PLAYER_MESSAGE")
    line = message.strip()
    if (
        not line
        or len(line) > MAX_PLAYER_MESSAGE_LENGTH
        or len(line.encode("utf-8")) > 2000
        or any(ord(char) < 32 or ord(char) == 127 for char in line)
    ):
        raise ValueError("INVALID_PLAYER_MESSAGE")
    return line


def _latest_turn(conn, interaction_id: str):
    return conn.execute(
        """
        SELECT id, speaker_id FROM player_conversation_turns
        WHERE interaction_id = ? ORDER BY id DESC LIMIT 1
        """,
        (interaction_id,),
    ).fetchone()


def _is_identical_retry(
    conn,
    interaction_id: str,
    after_turn_id: int,
    player_line: str,
    player_id: str = "PLAYER_1",
) -> bool:
    # Only the immediate next player+agent pair may be replayed.
    # Never report success for a different text or an arbitrarily old turn.
    rows = conn.execute(
        """
        SELECT id, speaker_id, text, source
        FROM player_conversation_turns
        WHERE interaction_id = ? AND id > ?
        ORDER BY id LIMIT 3
        """,
        (interaction_id, after_turn_id),
    ).fetchall()
    return (
        len(rows) == 2
        and rows[0][1] == player_id
        and rows[0][2] == player_line
        and rows[0][3] == "PLAYER_FREE_TEXT"
        and rows[1][1] != player_id
    )


def _say_in_zone_chat(player_id, actor_id, actor_name, player_line, reply_text, location):
    """Talking to someone is done aloud: both lines also go to the zone chat, as any other."""
    from . import online
    from .echoes import is_echo
    from .zone_chat import first_name
    if not online.enabled() or not location or is_echo(actor_id):
        return
    with get_connection() as conn:
        row = conn.execute("SELECT name FROM agents WHERE id=?", (player_id,)).fetchone()
    online.post_chat(player_id, row[0] if row else player_id, player_line, location)
    online.post_chat(actor_id, first_name(actor_name), reply_text, location)


def say_to_player_conversation(
    actor_id: str,
    text: str,
    after_turn_id: int,
    minute: int,
    player_id: str = "PLAYER_1",
) -> dict:
    player_line = validate_player_message(text)
    if not isinstance(after_turn_id, int) or after_turn_id <= 0:
        raise ValueError("INVALID_TURN_ID")

    interaction, actor_name = require_conversation(actor_id, player_id=player_id)
    initialize_conversation_turns()
    initialize_memory_provenance()
    initialize_player_claims()
    initialize_general_claims()
    initialize_generated_entities()

    with get_connection() as conn:
        latest = _latest_turn(conn, interaction.id)
        if latest is None:
            raise ValueError("CONVERSATION_NOT_STARTED")
        if latest[0] != after_turn_id:
            if _is_identical_retry(
                conn, interaction.id, after_turn_id, player_line, player_id=player_id
            ):
                return conversation_payload(
                    interaction.id, actor_id, actor_name, player_id=player_id
                )
            raise ValueError("STALE_TURN")
        if latest[1] != actor_id:
            raise ValueError("NOT_PLAYER_TURN")

    # The last player message is provided explicitly; old private memories
    # and previous turns are accessible only through this recipient's context.
    context = AgentContextBuilder().build(
        agent_id=actor_id,
        interaction_id=interaction.id,
        retrieval_query=player_line,
    )
    # Keep each actor's role and testimony inside ITS own context. These
    # metadata are provisional inclinations, never proof of a world event.
    from .echoes import is_echo
    if is_echo(actor_id):
        context["echo"] = actor_id
    role = generated_role_context(actor_id)
    if role is not None:
        context["role"] = role
        own_report = actor_received_case_report(actor_id)
        if own_report is not None:
            context["received_station_echo"] = own_report
    reply = generate_dialogue_reply(
        context=context, choice_id="FREE_TEXT", choice_text=player_line,
    )
    # The NPC's own utterance (not the player's testimony) can suggest a
    # presence. Model calls happen outside the write transaction.
    if reply.source != "LLM_DIALOGUE":
        trace_reality("DIALOGUE_SOURCE_" + reply.source)
    proposal = (
        suggest_entity(
            actor_id, reply.text, location=context["situation"]["location"],
        )
        if reply.source == "LLM_DIALOGUE" else None
    )

    # Model inference must not hold a database write lock.
    created_entity_id = None
    fresh = False  # a retry of the same line is not said twice
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        state = conn.execute(
            "SELECT status FROM interactions WHERE id = ?",
            (interaction.id,),
        ).fetchone()
        if state is None or state[0] != "OPEN":
            raise ValueError("NO_OPEN_CONVERSATION")

        locations = dict(
            conn.execute(
                "SELECT id, location FROM agents WHERE id IN (?, ?)",
                (player_id, actor_id),
            ).fetchall()
        )
        if (
            player_id not in locations
            or actor_id not in locations
            or locations[player_id] != locations[actor_id]
        ):
            raise ValueError("ACTOR_NOT_PRESENT")

        latest = _latest_turn(conn, interaction.id)
        if latest is None:
            raise ValueError("CONVERSATION_NOT_STARTED")
        if latest[0] != after_turn_id:
            if not _is_identical_retry(
                conn, interaction.id, after_turn_id, player_line, player_id=player_id
            ):
                raise ValueError("STALE_TURN")
        else:
            if latest[1] != actor_id:
                raise ValueError("NOT_PLAYER_TURN")
            fresh = True
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
                    "PLAYER_FREE_TEXT",
                    minute,
                ),
            )
            npc_turn = conn.execute(
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
            record_player_claim(
                conn,
                actor_id,
                player_line,
                player_turn.lastrowid,
                minute,
                player_id=player_id,
            )
            record_general_claim(
                conn,
                actor_id,
                player_line,
                player_turn.lastrowid,
                minute,
                player_id=player_id,
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
                    "DIALOGUE_SAY",
                    interaction.id,
                    "FREE_TEXT",
                ),
            )
            if proposal is not None:
                try:
                    created_entity_id = create_entity_from_turn(
                        conn, creator_id=actor_id,
                        origin_turn_id=npc_turn.lastrowid,
                        proposal=proposal, minute=minute,
                    )
                except ValueError as error:
                    # Show only stable internal reason codes when opt-in debug
                    # is active; never log user text or provider credentials.
                    trace_reality("REJECTED_" + str(error))
        # Player testimony never directly becomes an authoritative world fact.

    if created_entity_id is not None:
        # This message is emitted only after SQLite commits successfully.
        trace_reality("ENTITY_CREATED_" + created_entity_id)
    if fresh:
        _say_in_zone_chat(player_id, actor_id, actor_name, player_line, reply.text, locations.get(player_id))
    return conversation_payload(
        interaction.id, actor_id, actor_name, player_id=player_id
    )
