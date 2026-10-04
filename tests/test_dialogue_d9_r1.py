"""D9-r1 regression from the user's screenshot: dog statement must not trigger
an old password/NODE_07 answer even when old dialogue is still persisted."""
import pytest

from server.world_core import llm_dialogue
from server.world_core.database import get_connection, save_agent
from server.world_core.free_conversation import say_to_player_conversation
from server.world_core.interactions import create_or_get_interaction
from server.world_core.general_claims import get_general_claims
from server.world_core.player_conversation import (
    initialize_conversation_turns, start_player_conversation,
)
from server.world_core.simulation import Simulation


def _contact():
    sim = Simulation()
    for agent in (sim.player, sim.k.agent, sim.nora.agent):
        agent.location = "STATION"
        save_agent(agent)
    initialize_conversation_turns()
    interaction, _ = create_or_get_interaction(
        "PLAYER_1", "AGENT_K",
        "PLAYER_INITIATED_CONVERSATION", "UNKNOWN", sim.minute,
    )
    greeting = start_player_conversation("AGENT_K", sim.minute)
    return sim, interaction, greeting


def test_fresh_dog_statement_ignores_stale_password_and_node_hallucination(
    monkeypatch,
):
    sim, interaction, greeting = _contact()
    old = say_to_player_conversation(
        "AGENT_K", "Mi contraseña es nube12.",
        greeting["turn_id"], sim.minute,
    )
    # Simulate the same mistaken old AI line already stored in the user's
    # world.db from an earlier build. Old history must not be erased.
    old_false_line = (
        "Me dijiste que tu contraseña era nube12, pero no tengo "
        "una clave verificada para NODE_07."
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO player_conversation_turns
            (interaction_id, speaker_id, text, source, minute)
            VALUES (?, 'AGENT_K', ?, 'LLM_DIALOGUE', ?)
            """,
            (interaction.id, old_false_line, sim.minute),
        )
        last = conn.execute(
            "SELECT MAX(id) FROM player_conversation_turns "
            "WHERE interaction_id = ?", (interaction.id,),
        ).fetchone()[0]
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")

    def old_model(*args, **kwargs):
        raise AssertionError("A fresh explicit statement must not reach the LLM")

    monkeypatch.setattr(llm_dialogue, "_provider_reply", old_model)
    result = say_to_player_conversation(
        "AGENT_K", "Mi perro se llama Tango", last, sim.minute,
    )
    assert result["response_source"] == "CURRENT_TESTIMONY"
    assert "perro se llama Tango" in result["line"]
    assert "nube12" not in result["line"]
    assert "NODE_07" not in result["line"]

    with get_connection() as conn:
        turns = conn.execute(
            "SELECT speaker_id, text, source "
            "FROM player_conversation_turns WHERE interaction_id = ? "
            "ORDER BY id", (interaction.id,),
        ).fetchall()
    assert turns[-2] == ("PLAYER_1", "Mi perro se llama Tango", "PLAYER_FREE_TEXT")
    assert turns[-1][2] == "CURRENT_TESTIMONY"
    assert old_false_line in [row[1] for row in turns]
    assert get_general_claims(
        "AGENT_K", "¿Cómo se llama mi perro?"
    )[0]["reported_value"] == "Tango"
    assert get_general_claims(
        "AGENT_NORA", "¿Cómo se llama mi perro?"
    ) == []


def test_updated_dog_name_ack_and_direct_recall_remain_separate():
    sim, interaction, greeting = _contact()
    first = say_to_player_conversation(
        "AGENT_K", "Mi perro se llama Tango",
        greeting["turn_id"], sim.minute,
    )
    assert first["response_source"] == "CURRENT_TESTIMONY"
    second = say_to_player_conversation(
        "AGENT_K", "Mi perro ahora se llama Lupo",
        first["turn_id"], sim.minute,
    )
    assert second["response_source"] == "CURRENT_TESTIMONY"
    assert "Lupo" in second["line"]
    answer = say_to_player_conversation(
        "AGENT_K", "¿Qué nombre tiene mi perro?",
        second["turn_id"], sim.minute,
    )
    assert answer["response_source"] == "GROUNDED_RECALL"
    assert "Lupo" in answer["line"]
    assert "Tango" not in answer["line"]


def test_a_new_password_statement_no_longer_triggers_old_node_response(
    monkeypatch,
):
    sim, interaction, greeting = _contact()
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setattr(
        llm_dialogue, "_provider_reply",
        lambda *args, **kwargs: (
            "Debes usar Killo13 para acceder a NODE_07."
        ),
    )
    result = say_to_player_conversation(
        "AGENT_K", "Mi contraseña es nube12",
        greeting["turn_id"], sim.minute,
    )
    assert result["response_source"] == "CURRENT_TESTIMONY"
    assert "Killo13" not in result["line"]
    assert "NODE_07" not in result["line"]
