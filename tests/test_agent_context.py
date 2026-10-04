import pytest

from server.world_core.agent_context import (
    AgentContextBuilder,
)
from server.world_core.database import (
    add_memory,
    get_connection,
    save_agent,
)
from server.world_core.interactions import (
    create_or_get_interaction,
)
from server.world_core.player_conversation import (
    initialize_conversation_turns,
)
from server.world_core.simulation import (
    Simulation,
)


def test_context_keeps_player_conversation_private_to_recipient():
    simulation = Simulation()
    simulation.player.location = "STATION"
    simulation.k.agent.location = "STATION"
    simulation.nora.agent.location = "STATION"

    interaction, created = create_or_get_interaction(
        initiator_id="PLAYER_1",
        recipient_id="AGENT_K",
        topic="PLAYER_INITIATED_CONVERSATION",
        source_goal="UNKNOWN",
        minute=10,
    )
    assert created is True

    initialize_conversation_turns()

    with get_connection() as conn:
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
                "AGENT_K",
                "Te escucho. ¿Qué quieres saber?",
                "DETERMINISTIC_DIALOGUE",
                10,
            ),
        )
        conn.commit()

    add_memory(
        "AGENT_K",
        "During conversation CONTACT_PLAYER_1_AGENT_K_10, PLAYER_1 said: He observado la señal.",
    )

    builder = AgentContextBuilder()
    k_context = builder.build(
        "AGENT_K",
        interaction.id,
    )
    nora_context = builder.build("AGENT_NORA")

    assert k_context["conversation"]["id"] == interaction.id
    assert len(k_context["conversation"]["turns"]) == 1
    assert "He observado" in k_context["memory"][0]
    assert nora_context["conversation"] is None
    assert nora_context["memory"] == []

    with pytest.raises(ValueError, match="INTERACTION_NOT_AVAILABLE"):
        builder.build("AGENT_NORA", interaction.id)


def test_context_excludes_other_agents_private_location_and_world_state():
    simulation = Simulation()
    simulation.k.agent.location = "STATION"
    simulation.nora.agent.location = "OLD_DISTRICT"
    save_agent(simulation.k.agent)
    save_agent(simulation.nora.agent)

    context = AgentContextBuilder().build("AGENT_K")

    assert context["situation"]["location"] == "STATION"
    assert "AGENT_NORA" not in context["situation"]
    assert "nodes" in context["beliefs"]
    assert "world_state" not in context
