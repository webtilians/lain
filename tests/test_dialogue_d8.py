"""D8: long-horizon retrieval, epistemic provenance, privacy and explicit relay."""
import io
import json

import pytest

from server.world_core import llm_dialogue
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.beliefs import load_belief
from server.world_core.database import add_memory, get_connection, save_agent
from server.world_core.episodic_memory import (
    remember_agent_report,
    relay_shareable_memory,
    retrieve_memories,
)
from server.world_core.free_conversation import say_to_player_conversation
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_conversation import (
    initialize_conversation_turns,
    start_player_conversation,
)
from server.world_core.simulation import Simulation


def open_k_conversation():
    sim = Simulation()
    for actor in (sim.player, sim.k.agent, sim.nora.agent):
        actor.location = "STATION"
        save_agent(actor)
    initialize_conversation_turns()
    contact, _ = create_or_get_interaction(
        "PLAYER_1", "AGENT_K",
        "PLAYER_INITIATED_CONVERSATION", "UNKNOWN", sim.minute,
    )
    greeting = start_player_conversation("AGENT_K", sim.minute)
    return sim, contact, greeting


def test_old_relevant_memory_is_retrieved_beyond_latest_twelve():
    sim, contact, greeting = open_k_conversation()
    original = "El nombre de la contraseña centinela era ESTRELLA-52."
    response = say_to_player_conversation(
        "AGENT_K", original, greeting["turn_id"], sim.minute,
    )
    for number in range(40):
        add_memory("AGENT_K", f"Ruido cotidiano sobre una ventana {number}.")
    context = AgentContextBuilder().build(
        "AGENT_K", contact.id, retrieval_query="¿Cuál es la contraseña centinela?",
    )
    assert len(context["memory"]) == 12
    assert any(original in memory for memory in context["memory"])
    relevant = next(
        item for item in context["memory_records"]
        if original in item["text"]
    )
    assert relevant["source_kind"] == "PLAYER_TESTIMONY"
    assert relevant["source_actor_id"] == "PLAYER_1"
    assert relevant["origin_turn_id"] == response["turn_id"] - 1
    # The room itself cannot expose another agent's remembered secret.
    nora = AgentContextBuilder().build(
        "AGENT_NORA", retrieval_query="contraseña centinela",
    )
    assert all("ESTRELLA-52" not in m for m in nora["memory"])


def test_private_player_testimony_cannot_be_relayed_by_proximity():
    sim, contact, greeting = open_k_conversation()
    original_belief = load_belief("AGENT_NORA", "NODE_07")
    say_to_player_conversation(
        "AGENT_K", "Solo para ti: RIO-827.",
        greeting["turn_id"], sim.minute,
    )
    with get_connection() as conn:
        owned = conn.execute(
            """
            SELECT a.id, p.source_kind, p.shareable
            FROM agent_memory a
            JOIN agent_memory_provenance p ON p.memory_id = a.id
            WHERE a.agent_id = ? ORDER BY a.id DESC LIMIT 1
            """,
            ("AGENT_K",),
        ).fetchone()
    assert owned[1:] == ("PLAYER_TESTIMONY", 0)
    with pytest.raises(ValueError, match="PRIVATE_OR_UNKNOWN_MEMORY"):
        relay_shareable_memory(
            "AGENT_K", "AGENT_NORA", owned[0], sim.minute,
        )
    assert not AgentContextBuilder().build("AGENT_NORA")["memory"]
    assert load_belief("AGENT_NORA", "NODE_07") == original_belief


def test_explicit_ai_report_relay_is_attributed_and_idempotent():
    sim, contact, greeting = open_k_conversation()
    old_belief = load_belief("AGENT_NORA", "NODE_07")
    shared_id = remember_agent_report(
        "AGENT_K", "He oído el rumor de la puerta azul.",
        sim.minute, shareable=True,
    )
    recipient_id = relay_shareable_memory(
        "AGENT_K", "AGENT_NORA", shared_id, sim.minute,
    )
    repeated = relay_shareable_memory(
        "AGENT_K", "AGENT_NORA", shared_id, sim.minute,
    )
    assert recipient_id == repeated
    nora = AgentContextBuilder().build("AGENT_NORA")
    relayed = next(
        item for item in nora["memory_records"]
        if "puerta azul" in item["text"]
    )
    assert relayed["source_kind"] == "RELAYED_TESTIMONY"
    assert relayed["source_actor_id"] == "AGENT_K"
    assert relayed["parent_memory_id"] == shared_id
    assert load_belief("AGENT_NORA", "NODE_07") == old_belief
    with pytest.raises(ValueError, match="PRIVATE_OR_UNKNOWN_MEMORY"):
        relay_shareable_memory(
            "AGENT_NORA", "AGENT_K", recipient_id, sim.minute,
        )
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM agent_memory_relays WHERE original_memory_id = ?",
            (shared_id,),
        ).fetchone()[0]
    assert count == 1


def test_relay_requires_colocated_ai_actors():
    sim, contact, greeting = open_k_conversation()
    memory_id = remember_agent_report(
        "AGENT_K", "El sonido procede del pasillo.",
        sim.minute, shareable=True,
    )
    sim.nora.agent.location = "OLD_DISTRICT"
    save_agent(sim.nora.agent)
    with pytest.raises(ValueError, match="RELAY_ACTORS_NOT_COLOCATED"):
        relay_shareable_memory("AGENT_K", "AGENT_NORA", memory_id, sim.minute)
    with pytest.raises(ValueError, match="RELAY_ACTORS_NOT_COLOCATED"):
        relay_shareable_memory("AGENT_K", "PLAYER_1", memory_id, sim.minute)


def test_llm_receives_only_owner_attributed_relevant_memory(monkeypatch):
    sim, contact, greeting = open_k_conversation()
    say_to_player_conversation(
        "AGENT_K", "Mi contraseña centinela es ESTRELLA-52.",
        greeting["turn_id"], sim.minute,
    )
    for number in range(24):
        add_memory("AGENT_K", f"Conversación secundaria {number}.")
    add_memory("AGENT_NORA", "SECRETO_PRIVADO_NORA_456")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-test")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://127.0.0.1:1234/v1/chat/completions",
    )

    def provider(request, timeout):
        raw = request.data.decode("utf-8")
        assert "SECRETO_PRIVADO_NORA_456" not in raw
        context = json.loads(
            json.loads(raw)["messages"][1]["content"]
        )["agent_context"]
        remembered = [
            record for record in context["memory_records"]
            if "ESTRELLA-52" in record["text"]
        ]
        assert remembered and remembered[0]["source_kind"] == "PLAYER_TESTIMONY"
        assert remembered[0]["source_actor_id"] == "PLAYER_1"
        return io.BytesIO(
            json.dumps({
                "choices": [{"message": {"content": "Me lo dijiste tú, no lo comprobé."}}]
            }).encode("utf-8")
        )

    monkeypatch.setattr(llm_dialogue, "urlopen", provider)
    reply = say_to_player_conversation(
        "AGENT_K", "¿Recuerdas mi contraseña centinela?",
        greeting["turn_id"] + 2, sim.minute,
    )
    assert reply["line"] == "Me lo dijiste tú, no lo comprobé."
