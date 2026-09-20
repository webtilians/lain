"""D8-r3 regression of the exact repeated hallucination in the player's screenshot."""
import io
import json

import pytest

from server.world_core import llm_dialogue
from server.world_core.database import get_connection, save_agent
from server.world_core.dialogue_guard import (
    asserts_unverified_node_access_code,
    misattributes_player_password,
)
from server.world_core.free_conversation import say_to_player_conversation
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_conversation import (
    initialize_conversation_turns, start_player_conversation,
)
from server.world_core.simulation import Simulation


SCREENSHOT = (
    "La última contraseña que te dije fue clave123, pero eso "
    "no demuestra que sea correcta para entrar en Node07. "
    "Necesito que uses Killo13 para acceder."
)


def _contact():
    sim = Simulation()
    sim.player.location = "STATION"
    sim.k.agent.location = "STATION"
    save_agent(sim.player)
    save_agent(sim.k.agent)
    initialize_conversation_turns()
    interaction, _ = create_or_get_interaction(
        "PLAYER_1", "AGENT_K",
        "PLAYER_INITIATED_CONVERSATION", "UNKNOWN", sim.minute,
    )
    greeting = start_player_conversation("AGENT_K", sim.minute)
    return sim, interaction, greeting


@pytest.mark.parametrize("line", [
    SCREENSHOT,
    "Node07 solo se abre si utilizas la clave Killo13.",
    "Para entrar en NODE_07, tienes que utilizar clave123.",
    "El código de acceso a NODE_07 es Killo13.",
    "No estoy seguro: para acceder a Node07 necesito que uses Killo13.",
])
def test_node_access_guard_recognizes_wording_without_debes_or_usar(line):
    assert asserts_unverified_node_access_code(line)


def test_false_rules_are_not_inferred_from_personal_password():
    assert not asserts_unverified_node_access_code(
        "Me dijiste que tu contraseña personal era clave123."
    )
    assert misattributes_player_password(SCREENSHOT)
    assert not misattributes_player_password(
        "La última contraseña que me dijiste fue clave123."
    )


def test_screenshot_response_is_filtered_before_persistence(monkeypatch):
    sim, interaction, greeting = _contact()
    told = say_to_player_conversation(
        "AGENT_K", "Mi contraseña es clave123.",
        greeting["turn_id"], sim.minute,
    )
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-test-model")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://127.0.0.1:1234/v1/chat/completions",
    )

    def invented_rule(request, timeout):
        return io.BytesIO(json.dumps(
            {"choices": [{"message": {"content": SCREENSHOT}}]}
        ).encode("utf-8"))

    monkeypatch.setattr(llm_dialogue, "urlopen", invented_rule)
    result = say_to_player_conversation(
        "AGENT_K", "¿Qué opinas de esa frase?",
        told["turn_id"], sim.minute,
    )
    assert result["response_source"] == "RULE_GROUNDED"
    assert "Killo13" not in result["line"]
    assert "clave123" not in result["line"]
    assert "acceso verificada" in result["line"]
    with get_connection() as conn:
        saved = conn.execute(
            "SELECT text, source FROM player_conversation_turns WHERE id = ?",
            (result["turn_id"],),
        ).fetchone()
    assert saved == (result["line"], "RULE_GROUNDED")


def test_wrong_speaker_password_attribution_is_replaced(monkeypatch):
    sim, interaction, greeting = _contact()
    told = say_to_player_conversation(
        "AGENT_K", "Mi contraseña es clave123.",
        greeting["turn_id"], sim.minute,
    )
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-test-model")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://127.0.0.1:1234/v1/chat/completions",
    )

    def wrong_speaker(request, timeout):
        return io.BytesIO(json.dumps({
            "choices": [{
                "message": {"content": "La última contraseña que te dije fue Killo13."}
            }]
        }).encode("utf-8"))

    monkeypatch.setattr(llm_dialogue, "urlopen", wrong_speaker)
    result = say_to_player_conversation(
        "AGENT_K", "¿Puedes recordar la frase que comentamos?",
        told["turn_id"], sim.minute,
    )
    # The free-form question did not request a password lookup, so the
    # recipient's exact claim was not fetched. Reject wrong attribution
    # rather than falsely claiming an exact value from missing context.
    assert result["response_source"] == "RULE_GROUNDED"
    assert "clave123" not in result["line"]
    assert "Killo13" not in result["line"]
    assert "No puedo confirmar" in result["line"]
