"""D9 regression: general latest-wins player statements and private retrieval."""
import io
import json

import pytest

from server.world_core import semantic_query
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import add_memory, get_connection, save_agent
from server.world_core.free_conversation import say_to_player_conversation
from server.world_core.general_claims import (
    get_general_claims, parse_personal_statement, requested_topic,
)
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_conversation import (
    initialize_conversation_turns, start_player_conversation,
)
from server.world_core.simulation import Simulation


def contact(actor_id="AGENT_K"):
    sim = Simulation()
    for actor in (sim.player, sim.k.agent, sim.nora.agent):
        actor.location = "STATION"
        save_agent(actor)
    initialize_conversation_turns()
    interaction, _ = create_or_get_interaction(
        "PLAYER_1", actor_id, "PLAYER_INITIATED_CONVERSATION",
        "UNKNOWN", sim.minute,
    )
    greeting = start_player_conversation(actor_id, sim.minute)
    return sim, interaction, greeting


@pytest.mark.parametrize(
    ("statement", "expected_topic", "expected_value"),
    [
        ("Mi perro se llama Tango.", "perro", "Tango"),
        ("Mi perro ahora se llama Lupo.", "perro", "Lupo"),
        ("Mi color favorito es azul.", "color favorito", "azul"),
        ("Mi lugar favorito ahora es Málaga.", "lugar favorito", "Málaga"),
    ],
)
def test_generic_claim_parser(statement, expected_topic, expected_value):
    topic, _, value, quote = parse_personal_statement(statement)
    assert (topic, value, quote) == (
        expected_topic, expected_value, statement,
    )


@pytest.mark.parametrize(
    "statement",
    [
        "Mi contraseña es REAL-123.",
        "Mi perro es un espía porque controla NODE_07.",
        "¿Mi perro se llama Tango?",
        "Me dijeron que mi perro se llama Tango.",
        "Mi nombre es.",
    ],
)
def test_unqualified_statements_are_not_general_facts(statement):
    assert parse_personal_statement(statement) is None


@pytest.mark.parametrize(
    "question",
    [
        "¿Cómo se llama mi perro?",
        "¿Qué nombre tiene mi perro?",
        "¿Recuerdas lo que te dije sobre mi perro?",
    ],
)
def test_general_questions_retrieve_latest_player_testimony(question):
    sim, interaction, greeting = contact()
    earlier = say_to_player_conversation(
        "AGENT_K", "Mi perro se llama Tango.",
        greeting["turn_id"], sim.minute,
    )
    latest = say_to_player_conversation(
        "AGENT_K", "Mi perro ahora se llama Lupo.",
        earlier["turn_id"], sim.minute,
    )
    answer = say_to_player_conversation(
        "AGENT_K", question, latest["turn_id"], sim.minute,
    )
    assert answer["response_source"] == "GROUNDED_RECALL"
    assert "Lupo" in answer["line"]
    assert "Tango" not in answer["line"]
    assert "me dijiste" in answer["line"]
    claims = AgentContextBuilder().build(
        "AGENT_K", interaction.id, retrieval_query=question,
    )["general_claims"]
    assert len(claims) == 1
    assert claims[0]["reported_value"] == "Lupo"
    assert claims[0]["source_kind"] == "PLAYER_TESTIMONY"
    assert claims[0]["source_actor_id"] == "PLAYER_1"
    assert claims[0]["origin_turn_id"] == latest["turn_id"] - 1
    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM agent_player_general_claims "
            "WHERE recipient_id = 'AGENT_K' AND topic_key = 'perro'",
        ).fetchone()[0] == 1


def test_nora_only_sees_her_own_conflicting_statement():
    sim, _, k_start = contact()
    say_to_player_conversation(
        "AGENT_K", "Mi perro se llama Tango.",
        k_start["turn_id"], sim.minute,
    )
    assert get_general_claims(
        "AGENT_NORA", "¿Cómo se llama mi perro?",
    ) == []
    _, _, n_start = contact("AGENT_NORA")
    said = say_to_player_conversation(
        "AGENT_NORA", "Mi perro se llama Bimba.",
        n_start["turn_id"], sim.minute,
    )
    answer = say_to_player_conversation(
        "AGENT_NORA", "¿Qué nombre tiene mi perro?",
        said["turn_id"], sim.minute,
    )
    assert "Bimba" in answer["line"]
    assert "Tango" not in answer["line"]
    assert "Bimba" not in str(get_general_claims(
        "AGENT_K", "¿Cómo se llama mi perro?",
    ))


def test_d7_legacy_turn_read_without_modifying_prior_history():
    sim, interaction, greeting = contact()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO player_conversation_turns
                (interaction_id, speaker_id, text, source, minute)
            VALUES (?, 'PLAYER_1', 'Mi color favorito es violeta.',
                    'PLAYER_FREE_TEXT', ?)
            """,
            (interaction.id, sim.minute),
        )
    claims = get_general_claims(
        "AGENT_K", "¿Cuál es mi color favorito?",
    )
    assert claims[0]["reported_value"] == "violeta"
    assert claims[0]["source_kind"] == "LEGACY_PLAYER_TESTIMONY"


def test_semantic_query_expansion_uses_only_query_and_owner_memories(monkeypatch):
    sim, interaction, greeting = contact()
    old = say_to_player_conversation(
        "AGENT_K", "Mi perro se llama Tango.",
        greeting["turn_id"], sim.minute,
    )
    for i in range(35):
        add_memory("AGENT_K", f"Ruido cotidiano sobre ventana {i}.")
    add_memory("AGENT_NORA", "SECRETO_SOLO_NORA_991")
    monkeypatch.setenv("LAIN_MEMORY_SEMANTIC", "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-qwen")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://127.0.0.1:11434/v1/chat/completions",
    )
    semantic_query._ask_local_model.cache_clear()
    sent = []

    def provider(request, timeout):
        body = request.data.decode("utf-8")
        sent.append(body)
        assert "SECRETO_SOLO_NORA_991" not in body
        assert "Tango" not in body
        assert timeout <= 4
        assert "compañero de cuatro patas" in body
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "perro, mascota, animal"}}]
        }).encode("utf-8"))

    monkeypatch.setattr(semantic_query, "urlopen", provider)
    context = AgentContextBuilder().build(
        "AGENT_K", interaction.id,
        retrieval_query="¿Cuál era el nombre de mi compañero de cuatro patas?",
    )
    assert len(sent) == 1
    assert any("Tango" in m for m in context["memory"])
    assert "SECRETO_SOLO_NORA_991" not in str(context)
    # Expansion influences ranking only. It never creates new DB facts.
    assert requested_topic(
        "¿Cuál era el nombre de mi compañero de cuatro patas?"
    ) is None


def test_semantic_expansion_timeout_falls_back_to_lexical(monkeypatch):
    sim, interaction, greeting = contact()
    monkeypatch.setenv("LAIN_MEMORY_SEMANTIC", "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-qwen")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://127.0.0.1:11434/v1/chat/completions",
    )
    semantic_query._ask_local_model.cache_clear()

    def unavailable(*args, **kwargs):
        raise TimeoutError("local model busy")

    monkeypatch.setattr(semantic_query, "urlopen", unavailable)
    context = AgentContextBuilder().build(
        "AGENT_K", interaction.id,
        retrieval_query="¿Qué sabes de NODE_07?",
    )
    assert context["identity"]["id"] == "AGENT_K"
    assert context["memory_records"] == []


def test_plain_password_guard_from_d8_r3_is_unchanged():
    assert requested_topic("¿Cuál es mi contraseña?") is None
