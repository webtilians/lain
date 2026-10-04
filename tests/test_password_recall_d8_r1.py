"""D8-r1 regression: new testimony overrides earlier password only for its recipient."""
import pytest

from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection, save_agent
from server.world_core.free_conversation import say_to_player_conversation
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_claims import (
    extract_password_claim, get_player_claims, asks_about_password,
)
from server.world_core.player_conversation import (
    initialize_conversation_turns, start_player_conversation,
)
from server.world_core.simulation import Simulation


def _talk_to(actor_id: str):
    sim = Simulation()
    for agent in (sim.player, sim.k.agent, sim.nora.agent):
        agent.location = "STATION"
        save_agent(agent)
    initialize_conversation_turns()
    interaction, _ = create_or_get_interaction(
        "PLAYER_1", actor_id, "PLAYER_INITIATED_CONVERSATION",
        "UNKNOWN", sim.minute,
    )
    start = start_player_conversation(actor_id, sim.minute)
    return sim, interaction, start


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("Mi contraseña es ESTRELLA-52.", "ESTRELLA-52"),
        ("Esta es mi contraseña: MAR-763.", "MAR-763"),
        ("Mi nueva contraseña es LUNA-28.", "LUNA-28"),
        ("Mi contraseña centinela es RIO-819.", "RIO-819"),
        ("Esta es mi contraseña.", None),
        ("La contraseña anterior era ESTRELLA-52.", None),
    ],
)
def test_only_explicit_password_assignment_creates_claim(utterance, expected):
    assert extract_password_claim(utterance) == expected


def test_k_recall_uses_latest_direct_claim_not_older_answer(monkeypatch):
    sim, interaction, start = _talk_to("AGENT_K")
    first = say_to_player_conversation(
        "AGENT_K", "Mi contraseña es ESTRELLA-52.",
        start["turn_id"], sim.minute,
    )
    second = say_to_player_conversation(
        "AGENT_K", "Mi contraseña ahora es NUBE-731.",
        first["turn_id"], sim.minute,
    )
    assert second["turn_id"] > first["turn_id"]

    # Even a broken or stale model must not fabricate the old value.
    from server.world_core import llm_dialogue
    def should_not_call_provider(*args, **kwargs):
        raise AssertionError("Direct value recall should be grounded")
    monkeypatch.setattr(llm_dialogue, "_provider_reply", should_not_call_provider)
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    recall = say_to_player_conversation(
        "AGENT_K", "¿Cuál es mi contraseña?",
        second["turn_id"], sim.minute,
    )
    assert "NUBE-731" in recall["line"]
    assert "ESTRELLA-52" not in recall["line"]
    assert "me lo contaste" in recall["line"]
    assert recall["response_source"] == "GROUNDED_RECALL"
    claims = AgentContextBuilder().build(
        "AGENT_K", interaction.id, retrieval_query="contraseña",
    )["player_claims"]
    assert len(claims) == 1
    assert claims[0]["source_kind"] == "PLAYER_TESTIMONY"
    assert claims[0]["claim_value"] == "NUBE-731"


def test_nora_can_recall_own_claim_and_cannot_access_ks_claim():
    sim, k_interaction, k_start = _talk_to("AGENT_K")
    say_to_player_conversation(
        "AGENT_K", "Mi contraseña es SOL-347.",
        k_start["turn_id"], sim.minute,
    )
    assert get_player_claims("AGENT_NORA", "¿Cuál es mi contraseña?") == []

    nora_interaction, _ = create_or_get_interaction(
        "PLAYER_1", "AGENT_NORA",
        "PLAYER_INITIATED_CONVERSATION", "UNKNOWN", sim.minute,
    )
    nora_start = start_player_conversation("AGENT_NORA", sim.minute)
    nora_first = say_to_player_conversation(
        "AGENT_NORA", "Esta es mi contraseña: LAGO-561.",
        nora_start["turn_id"], sim.minute,
    )
    nora_recall = say_to_player_conversation(
        "AGENT_NORA", "¿Cuál es mi contraseña?",
        nora_first["turn_id"], sim.minute,
    )
    assert "LAGO-561" in nora_recall["line"]
    assert "SOL-347" not in nora_recall["line"]
    assert nora_recall["response_source"] == "GROUNDED_RECALL"
    assert get_player_claims("AGENT_K", "contraseña")[0]["claim_value"] == "SOL-347"
    assert get_player_claims("AGENT_NORA", "contraseña")[0]["claim_value"] == "LAGO-561"


def test_phrase_without_explicit_value_is_not_invented():
    sim, interaction, start = _talk_to("AGENT_NORA")
    say_to_player_conversation(
        "AGENT_NORA", "Esta es mi contraseña.",
        start["turn_id"], sim.minute,
    )
    assert get_player_claims("AGENT_NORA", "contraseña") == []


def test_legacy_unindexed_player_turn_is_read_without_resetting_save():
    sim, interaction, start = _talk_to("AGENT_K")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO player_conversation_turns
            (interaction_id, speaker_id, text, source, minute)
            VALUES (?, 'PLAYER_1', ?, 'PLAYER_FREE_TEXT', ?)
            """,
            (interaction.id, "Mi contraseña es VIEJA-135.", sim.minute),
        )
    assert get_player_claims("AGENT_K", "¿Cuál es mi contraseña?")[0][
        "claim_value"
    ] == "VIEJA-135"
