"""D8-r2: no invented NODE_07 access code from remembered player testimony."""
import io
import json

import pytest

from server.world_core import llm_dialogue
from server.world_core.database import get_connection, save_agent
from server.world_core.dialogue_guard import (
    asks_about_node_access_code,
    asserts_unverified_node_access_code,
)
from server.world_core.free_conversation import say_to_player_conversation
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_conversation import (
    initialize_conversation_turns, start_player_conversation,
)
from server.world_core.simulation import Simulation


def _contact():
    sim = Simulation()
    sim.player.location = "STATION"
    sim.k.agent.location = "STATION"
    for actor in (sim.player, sim.k.agent):
        save_agent(actor)
    initialize_conversation_turns()
    interaction, _ = create_or_get_interaction(
        "PLAYER_1", "AGENT_K",
        "PLAYER_INITIATED_CONVERSATION", "UNKNOWN", sim.minute,
    )
    greeting = start_player_conversation("AGENT_K", sim.minute)
    return sim, interaction, greeting


@pytest.mark.parametrize("phrase", [
    "No reconozco esa clave. Para acceder a Node07, debes usar la clave Killo13.",
    "Para acceder a NODE_07 necesitas la contraseña ESTRELLA-52.",
    "El código Killo13 permite acceder a NODE_07.",
    "La clave Killo13 desbloquea NODE_07.",
])
def test_fabricated_world_rule_is_detected(phrase):
    assert asserts_unverified_node_access_code(phrase)


def test_a_personal_password_is_not_an_access_rule():
    assert not asserts_unverified_node_access_code(
        "Recuerdo que me dijiste que tu contraseña era ESTRELLA-52."
    )
    assert asks_about_node_access_code(
        "¿Qué clave necesito para acceder a NODE_07?"
    )
    assert not asks_about_node_access_code(
        "¿Cuál era mi contraseña personal?"
    )


def test_model_invented_node_code_is_replaced_before_saving(monkeypatch):
    sim, interaction, greeting = _contact()
    saved = say_to_player_conversation(
        "AGENT_K", "Mi contraseña es ESTRELLA-52.",
        greeting["turn_id"], sim.minute,
    )
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-test-model")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://127.0.0.1:1234/v1/chat/completions",
    )

    def model(request, timeout):
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content":
                "No reconozco esa clave. Para acceder a Node07, "
                "debes usar la clave Killo13."
            }}]
        }).encode("utf-8"))

    monkeypatch.setattr(llm_dialogue, "urlopen", model)
    response = say_to_player_conversation(
        "AGENT_K", "¿Qué te parece la frase que te dije?",
        saved["turn_id"], sim.minute,
    )
    assert response["response_source"] == "RULE_GROUNDED"
    assert "Killo13" not in response["line"]
    assert "acceso verificada" in response["line"]
    with get_connection() as conn:
        row = conn.execute(
            "SELECT text, source FROM player_conversation_turns WHERE id = ?",
            (response["turn_id"],),
        ).fetchone()
    assert row == (response["line"], "RULE_GROUNDED")


def test_asking_node_code_does_not_conflate_players_password(monkeypatch):
    sim, interaction, greeting = _contact()
    saved = say_to_player_conversation(
        "AGENT_K", "Mi contraseña es ESTRELLA-52.",
        greeting["turn_id"], sim.minute,
    )
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    def cannot_run(*args, **kwargs):
        raise AssertionError("No model inference needed for unverified node access")
    monkeypatch.setattr(llm_dialogue, "_provider_reply", cannot_run)
    response = say_to_player_conversation(
        "AGENT_K", "¿Qué clave necesito para acceder a Node07?",
        saved["turn_id"], sim.minute,
    )
    assert response["response_source"] == "RULE_GROUNDED"
    assert "ESTRELLA-52" not in response["line"]
    assert "acceso verificada" in response["line"]


def test_existing_password_recall_still_uses_last_player_testimony():
    sim, interaction, greeting = _contact()
    old = say_to_player_conversation(
        "AGENT_K", "Mi contraseña es ESTRELLA-52.",
        greeting["turn_id"], sim.minute,
    )
    new = say_to_player_conversation(
        "AGENT_K", "Mi contraseña ahora es NUBE-731.",
        old["turn_id"], sim.minute,
    )
    answer = say_to_player_conversation(
        "AGENT_K", "¿Cuál es mi contraseña?",
        new["turn_id"], sim.minute,
    )
    assert answer["response_source"] == "GROUNDED_RECALL"
    assert "NUBE-731" in answer["line"]
    assert "ESTRELLA-52" not in answer["line"]
