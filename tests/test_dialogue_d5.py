"""D5: private context, conversation state, idempotency and atomic records."""
import pytest

from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import add_memory, get_connection, save_agent
from server.world_core.interactions import (
    create_or_get_interaction,
    get_interaction,
)
from server.world_core.player_conversation import (
    initialize_conversation_turns,
    start_player_conversation,
    reply_to_player_conversation,
    pause_player_conversation,
)
from server.world_core.simulation import Simulation
from server.world_core.beliefs import save_belief
from server.world_core.models import NodeBelief


def colocated_contact():
    simulation = Simulation()
    simulation.player.location = "STATION"
    simulation.k.agent.location = "STATION"
    simulation.nora.agent.location = "STATION"
    for agent in (simulation.player, simulation.k.agent, simulation.nora.agent):
        save_agent(agent)
    initialize_conversation_turns()
    interaction, _ = create_or_get_interaction(
        "PLAYER_1",
        "AGENT_K",
        "PLAYER_INITIATED_CONVERSATION",
        "UNKNOWN",
        simulation.minute,
    )
    return simulation, interaction


def test_context_is_bounded_and_private():
    _, interaction = colocated_contact()
    for number in range(25):
        add_memory("AGENT_K", f"private-{number}")
    context = AgentContextBuilder(memory_limit=4).build(
        "AGENT_K", interaction.id,
    )
    assert context["memory"] == [
        f"private-{number}" for number in range(21, 25)
    ]
    assert AgentContextBuilder().build("AGENT_NORA")["memory"] == []
    with pytest.raises(ValueError, match="INVALID_CONTEXT_LIMIT"):
        AgentContextBuilder(memory_limit=0)


def test_agent_remembers_player_statement_without_leaking_to_nora():
    sim, interaction = colocated_contact()
    save_belief(
        NodeBelief(
            agent_id="PLAYER_1",
            node_id="NODE_07",
            believed_location="STATION",
            believed_strength=0.6,
            confidence=0.85,
            source="DIRECT_PERCEPTION",
            updated_minute=sim.minute,
        )
    )
    first = start_player_conversation("AGENT_K", sim.minute)
    first_reply = reply_to_player_conversation(
        "AGENT_K", "TELL_OBSERVED", first["turn_id"], sim.minute,
    )
    assert "testimonio" in first_reply["line"]
    second_reply = reply_to_player_conversation(
        "AGENT_K", "TELL_OBSERVED", first_reply["turn_id"], sim.minute,
    )
    assert "Recuerdo" in second_reply["line"]
    assert not any(
        "He observado la señal" in memory
        for memory in AgentContextBuilder().build("AGENT_NORA")["memory"]
    )
    with get_connection() as conn:
        turns = conn.execute(
            """
            SELECT COUNT(*) FROM player_conversation_turns
            WHERE interaction_id = ?
            """,
            (interaction.id,),
        ).fetchone()[0]
    assert turns == 5


def test_duplicate_reply_creates_no_extra_memory_or_event():
    sim, interaction = colocated_contact()
    first = start_player_conversation("AGENT_K", sim.minute)
    response = reply_to_player_conversation(
        "AGENT_K", "ASK_IDENTITY", first["turn_id"], sim.minute,
    )
    duplicate = reply_to_player_conversation(
        "AGENT_K", "ASK_IDENTITY", first["turn_id"], sim.minute,
    )
    assert duplicate["turn_id"] == response["turn_id"]
    with get_connection() as conn:
        turns = conn.execute(
            "SELECT COUNT(*) FROM player_conversation_turns WHERE interaction_id = ?",
            (interaction.id,),
        ).fetchone()[0]
        memories = conn.execute(
            "SELECT COUNT(*) FROM agent_memory WHERE agent_id = 'AGENT_K'",
        ).fetchone()[0]
        events = conn.execute(
            "SELECT COUNT(*) FROM events WHERE action = 'DIALOGUE_CHOICE' AND target = ?",
            (interaction.id,),
        ).fetchone()[0]
    assert (turns, memories, events) == (3, 1, 1)


def test_pause_and_resume_reuses_original_transcript():
    sim, interaction = colocated_contact()
    first = start_player_conversation("AGENT_K", sim.minute)
    paused = pause_player_conversation(
        "AGENT_K", interaction.id, sim.minute,
    )
    assert paused["status"] == "PAUSED"
    assert get_interaction(interaction.id).status == "PAUSED"
    with pytest.raises(ValueError, match="NO_OPEN_CONVERSATION"):
        start_player_conversation("AGENT_K", sim.minute)

    reopened, created = create_or_get_interaction(
        "PLAYER_1",
        "AGENT_K",
        "PLAYER_INITIATED_CONVERSATION",
        "UNKNOWN",
        sim.minute + 10,
    )
    assert not created
    assert reopened.id == interaction.id
    assert reopened.status == "OPEN"
    assert (
        start_player_conversation("AGENT_K", sim.minute)["turn_id"]
        == first["turn_id"]
    )


def test_player_cannot_pause_another_agents_conversation():
    sim, interaction = colocated_contact()
    with pytest.raises(ValueError, match="CONVERSATION_NOT_AVAILABLE"):
        pause_player_conversation("AGENT_NORA", interaction.id, sim.minute)


def test_failed_memory_insert_rolls_back_both_turns_and_event():
    sim, interaction = colocated_contact()
    first = start_player_conversation("AGENT_K", sim.minute)
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TRIGGER fail_d5_memory
            BEFORE INSERT ON agent_memory
            WHEN NEW.agent_id = 'AGENT_K'
            BEGIN
                SELECT RAISE(ABORT, 'simulated memory failure');
            END
            """
        )
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError, match="simulated memory failure"):
        reply_to_player_conversation(
            "AGENT_K", "ASK_IDENTITY", first["turn_id"], sim.minute,
        )
    with get_connection() as conn:
        turn_count = conn.execute(
            "SELECT COUNT(*) FROM player_conversation_turns WHERE interaction_id = ?",
            (interaction.id,),
        ).fetchone()[0]
        event_count = conn.execute(
            "SELECT COUNT(*) FROM events WHERE action = 'DIALOGUE_CHOICE' AND target = ?",
            (interaction.id,),
        ).fetchone()[0]
    assert (turn_count, event_count) == (1, 0)
