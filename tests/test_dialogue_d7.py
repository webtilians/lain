"""D7 regression tests: free text remains private testimony and durable history."""
import io
import json

import pytest

from server.world_core import llm_dialogue
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.beliefs import load_belief
from server.world_core.database import (
    add_memory,
    get_connection,
    save_agent,
)
from server.world_core.free_conversation import (
    say_to_player_conversation,
    validate_player_message,
)
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_conversation import (
    initialize_conversation_turns,
    pause_player_conversation,
    start_player_conversation,
)
from server.world_core.simulation import Simulation


def start_contact(recipient="AGENT_K"):
    sim = Simulation()
    for agent in (sim.player, sim.k.agent, sim.nora.agent):
        agent.location = "STATION"
        save_agent(agent)
    initialize_conversation_turns()
    interaction, _ = create_or_get_interaction(
        "PLAYER_1",
        recipient,
        "PLAYER_INITIATED_CONVERSATION",
        "UNKNOWN",
        sim.minute,
    )
    first = start_player_conversation(recipient, sim.minute)
    return sim, interaction, first


def test_free_text_is_persisted_as_player_testimony_without_world_facts():
    sim, interaction, first = start_contact()
    initial_belief = load_belief("AGENT_K", "NODE_07")
    statement = "Mi palabra secreta de prueba es AZUL-743."
    response = say_to_player_conversation(
        "AGENT_K", statement, first["turn_id"], sim.minute,
    )
    assert response["turn_id"] > first["turn_id"]
    assert response["response_source"] == "DETERMINISTIC_FALLBACK"

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT speaker_id, text, source
            FROM player_conversation_turns
            WHERE interaction_id = ? ORDER BY id
            """,
            (interaction.id,),
        ).fetchall()
        memories = conn.execute(
            "SELECT memory FROM agent_memory WHERE agent_id = 'AGENT_K'"
        ).fetchall()
        events = conn.execute(
            """
            SELECT action, details FROM events
            WHERE target = ? AND action = 'DIALOGUE_SAY'
            """,
            (interaction.id,),
        ).fetchall()
    assert rows[1] == ("PLAYER_1", statement, "PLAYER_FREE_TEXT")
    assert rows[2][0] == "AGENT_K"
    assert any(statement in row[0] for row in memories)
    assert events == [("DIALOGUE_SAY", "FREE_TEXT")]
    assert load_belief("AGENT_K", "NODE_07") == initial_belief

    nora = AgentContextBuilder().build("AGENT_NORA")
    assert nora["memory"] == []
    assert nora["conversation"] is None


def test_free_text_duplicate_and_conflicting_retry():
    sim, interaction, first = start_contact()
    reply = say_to_player_conversation(
        "AGENT_K", "Un mensaje privado.", first["turn_id"], sim.minute,
    )
    duplicate = say_to_player_conversation(
        "AGENT_K", "Un mensaje privado.", first["turn_id"], sim.minute,
    )
    assert reply["turn_id"] == duplicate["turn_id"]
    with pytest.raises(ValueError, match="STALE_TURN"):
        say_to_player_conversation(
            "AGENT_K", "Texto distinto.", first["turn_id"], sim.minute,
        )
    with get_connection() as conn:
        counts = (
            conn.execute(
                "SELECT COUNT(*) FROM player_conversation_turns WHERE interaction_id = ?",
                (interaction.id,),
            ).fetchone()[0],
            conn.execute(
                "SELECT COUNT(*) FROM agent_memory WHERE agent_id = 'AGENT_K'"
            ).fetchone()[0],
            conn.execute(
                "SELECT COUNT(*) FROM events WHERE action = 'DIALOGUE_SAY'"
            ).fetchone()[0],
        )
    assert counts == (3, 1, 1)


@pytest.mark.parametrize(
    "text",
    ["", " \t ", "x" * 501, "a\nb", "a\rb", "a\x00b", 42],
)
def test_invalid_player_messages_are_rejected(text):
    with pytest.raises(ValueError, match="INVALID_PLAYER_MESSAGE"):
        validate_player_message(text)


def test_free_text_requires_open_contact_and_colocation():
    sim, interaction, first = start_contact()
    with pytest.raises(ValueError, match="NO_OPEN_CONVERSATION"):
        say_to_player_conversation(
            "AGENT_NORA", "Mensaje solo para K.", first["turn_id"], sim.minute,
        )
    pause_player_conversation("AGENT_K", interaction.id, sim.minute)
    with pytest.raises(ValueError, match="NO_OPEN_CONVERSATION"):
        say_to_player_conversation(
            "AGENT_K", "Hola otra vez.", first["turn_id"], sim.minute,
        )


def test_free_text_reaches_local_llm_without_leaking_other_agent_memory(
    monkeypatch,
):
    sim, interaction, first = start_contact()
    add_memory("AGENT_NORA", "SECRETO_SOLO_NORA_341")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-test-model")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://127.0.0.1:1234/v1/chat/completions",
    )
    captured = []

    def fake_network(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        data = json.loads(payload["messages"][1]["content"])
        captured.append(data)
        assert data["player_utterance"] == "Recuerda la clave LUNA-19."
        assert "SECRETO_SOLO_NORA_341" not in request.data.decode("utf-8")
        return io.BytesIO(
            json.dumps(
                {"choices": [{"message": {"content": "Recordaré la clave LUNA-19."}}]}
            ).encode("utf-8")
        )

    monkeypatch.setattr(llm_dialogue, "urlopen", fake_network)
    answer = say_to_player_conversation(
        "AGENT_K",
        "Recuerda la clave LUNA-19.",
        first["turn_id"],
        sim.minute,
    )
    assert answer["line"] == "Recordaré la clave LUNA-19."
    assert answer["response_source"] == "LLM_DIALOGUE"
    assert len(captured) == 1
    context = AgentContextBuilder().build("AGENT_K", interaction.id)
    assert any("LUNA-19" in m for m in context["memory"])
    assert "SECRETO_SOLO_NORA_341" not in json.dumps(context)


def test_free_text_history_survives_pausing_and_resuming():
    sim, interaction, first = start_contact()
    answer = say_to_player_conversation(
        "AGENT_K", "Recuerda ESTRELLA-52.", first["turn_id"], sim.minute,
    )
    pause_player_conversation("AGENT_K", interaction.id, sim.minute)
    reopened, created = create_or_get_interaction(
        "PLAYER_1", "AGENT_K",
        "PLAYER_INITIATED_CONVERSATION", "UNKNOWN", sim.minute + 10,
    )
    assert not created
    assert reopened.id == interaction.id
    greeting = start_player_conversation("AGENT_K", sim.minute + 10)
    assert greeting["turn_id"] > answer["turn_id"]
    assert greeting["line"].startswith("Nos volvemos")
    context = AgentContextBuilder().build("AGENT_K", interaction.id)
    assert any("ESTRELLA-52" in m for m in context["memory"])
    assert any(
        turn["text"] == "Recuerda ESTRELLA-52."
        for turn in context["conversation"]["turns"]
    )
