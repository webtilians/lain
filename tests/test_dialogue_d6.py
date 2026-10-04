"""D6 regressions: optional inference, bounded privacy and fallback."""
import io
import json
import pytest

from server.world_core import llm_dialogue
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection, save_agent
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_conversation import (
    initialize_conversation_turns,
    start_player_conversation,
    reply_to_player_conversation,
)
from server.world_core.simulation import Simulation


def setup_contact():
    sim = Simulation()
    sim.player.location = "STATION"
    sim.k.agent.location = "STATION"
    sim.nora.agent.location = "STATION"
    for agent in (sim.player, sim.k.agent, sim.nora.agent):
        save_agent(agent)
    initialize_conversation_turns()
    interaction, _ = create_or_get_interaction(
        "PLAYER_1", "AGENT_K",
        "PLAYER_INITIATED_CONVERSATION", "UNKNOWN", sim.minute,
    )
    return sim, interaction


def test_disabled_provider_never_calls_network(monkeypatch):
    sim, interaction = setup_contact()
    monkeypatch.delenv("LAIN_LLM_ENABLED", raising=False)

    def unexpected_network(*args, **kwargs):
        raise AssertionError("The opt-in switch is off")

    monkeypatch.setattr(llm_dialogue, "urlopen", unexpected_network)
    first = start_player_conversation("AGENT_K", sim.minute)
    result = reply_to_player_conversation(
        "AGENT_K", "ASK_IDENTITY", first["turn_id"], sim.minute,
    )
    assert "K" in result["line"]
    with get_connection() as conn:
        source = conn.execute(
            """
            SELECT source FROM player_conversation_turns
            WHERE id = ?
            """, (result["turn_id"],),
        ).fetchone()[0]
    assert source == "DETERMINISTIC_DIALOGUE"


def test_model_reply_is_persisted_with_source_and_private_context(monkeypatch):
    sim, interaction = setup_contact()
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-test-model")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://127.0.0.1:1234/v1/chat/completions",
    )
    seen = []

    def fake_network(request, timeout):
        assert timeout <= 15
        body = json.loads(request.data.decode("utf-8"))
        seen.append(body)
        content = json.loads(body["messages"][1]["content"])
        assert content["agent_context"]["identity"]["id"] == "AGENT_K"
        assert "AGENT_NORA" not in json.dumps(
            content["agent_context"]["memory"],
            ensure_ascii=False,
        )
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "Te estaba esperando aquí."}}]
        }).encode("utf-8"))

    monkeypatch.setattr(llm_dialogue, "urlopen", fake_network)
    first = start_player_conversation("AGENT_K", sim.minute)
    response = reply_to_player_conversation(
        "AGENT_K", "ASK_IDENTITY", first["turn_id"], sim.minute,
    )
    assert response["line"] == "Te estaba esperando aquí."
    assert len(seen) == 1
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT speaker_id, source FROM player_conversation_turns
            WHERE id = ?
            """, (response["turn_id"],),
        ).fetchone()
    assert row == ("AGENT_K", "LLM_DIALOGUE")

    # A retry must not contact the provider again or duplicate the line.
    duplicate = reply_to_player_conversation(
        "AGENT_K", "ASK_IDENTITY", first["turn_id"], sim.minute,
    )
    assert duplicate["turn_id"] == response["turn_id"]
    assert len(seen) == 1


def test_provider_failure_falls_back_and_keeps_game_playable(monkeypatch):
    sim, interaction = setup_contact()
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-test-model")

    def unavailable(*args, **kwargs):
        raise OSError("Model unavailable")

    monkeypatch.setattr(llm_dialogue, "urlopen", unavailable)
    first = start_player_conversation("AGENT_K", sim.minute)
    response = reply_to_player_conversation(
        "AGENT_K", "ASK_IDENTITY", first["turn_id"], sim.minute,
    )
    assert response["line"] == "Puedes llamarme K. ¿Qué necesitas saber?"
    with get_connection() as conn:
        source = conn.execute(
            "SELECT source FROM player_conversation_turns WHERE id = ?",
            (response["turn_id"],),
        ).fetchone()[0]
    assert source == "DETERMINISTIC_DIALOGUE"


def test_remote_endpoint_requires_explicit_opt_in_and_https(monkeypatch):
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "https://example.org/v1/chat/completions",
    )
    monkeypatch.delenv("LAIN_LLM_ALLOW_REMOTE", raising=False)
    monkeypatch.setenv("LAIN_LLM_API_KEY", "test-only-value")
    with pytest.raises(ValueError, match="REMOTE_LLM_NOT_AUTHORIZED"):
        llm_dialogue._endpoint()
    monkeypatch.setenv("LAIN_LLM_ALLOW_REMOTE", "1")
    assert llm_dialogue._endpoint().startswith("https://")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://example.org/v1/chat/completions",
    )
    with pytest.raises(ValueError, match="REMOTE_LLM_NOT_AUTHORIZED"):
        llm_dialogue._endpoint()


def test_provider_is_bounded_without_revealing_other_context(monkeypatch):
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-test-model")
    monkeypatch.setenv(
        "LAIN_LLM_ENDPOINT",
        "http://127.0.0.1:1234/v1/chat/completions",
    )
    context = {
        "identity": {"id": "AGENT_K", "name": "K"},
        "situation": {"location": "STATION"},
        "beliefs": {
            "nodes": [{"node_id": f"NODE_{n}"} for n in range(80)],
            "actors": [],
            "situations": [],
        },
        "memory": [f"private-{n}" for n in range(40)],
        "goals": {"current": "IDLE"},
        "conversation": {
            "id": "CONTACT_TEST",
            "status": "OPEN",
            "turns": [
                {"speaker_id": "PLAYER_1", "text": str(n), "source": "PLAYER_CHOICE"}
                for n in range(60)
            ],
        },
    }

    def fake_network(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        projected = json.loads(payload["messages"][1]["content"])["agent_context"]
        assert len(projected["memory"]) == 12
        assert len(projected["conversation"]["turns"]) == 16
        assert len(projected["beliefs"]["nodes"]) == 32
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "Comprendo."}}]
        }).encode("utf-8"))

    monkeypatch.setattr(llm_dialogue, "urlopen", fake_network)
    assert llm_dialogue._provider_reply(context, "¿Quién eres?") == "Comprendo."
