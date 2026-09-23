"""Reality 0.3: generated actors advance without any player action or LLM call."""
from threading import RLock

from server.world_core.database import get_connection, save_agent
from server.world_core.generated_entities import (
    EntityProposal, create_entity_from_turn, initialize_generated_entities,
)
from server.world_core.models import ActionIntent
from server.world_core.episodic_memory import initialize_memory_provenance
from server.world_core.player_conversation import (
    initialize_conversation_turns, start_player_conversation,
)
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_view import build_player_snapshot
from server.world_core.realtime import WorldClock
from server.world_core.simulation import Simulation


def world_with_entity():
    sim = Simulation()
    initialize_generated_entities()
    initialize_memory_provenance()
    initialize_conversation_turns()
    sim.player.location = sim.k.agent.location
    save_agent(sim.player)
    with get_connection() as conn:
        turn_id = conn.execute(
            """INSERT INTO player_conversation_turns
               (interaction_id, speaker_id, text, source, minute)
               VALUES ('R03_GENESIS', 'AGENT_K',
                       'Quizá exista Eco.', 'LLM_DIALOGUE', 0)"""
        ).lastrowid
        entity_id = create_entity_from_turn(
            conn, creator_id="AGENT_K", origin_turn_id=turn_id,
            proposal=EntityProposal(
                "Eco", "Una presencia nueva junto al apartamento", "OBSERVE_WORLD",
            ), minute=0,
        )
    return sim, entity_id


def test_idle_player_does_not_stop_independent_world_and_generated_motion():
    sim, entity_id = world_with_entity()
    clock = WorldClock(sim, RLock(), interval=8)
    original_player = sim.player.location
    original_energy = sim.player.energy
    start = sim.minute
    assert clock.tick_once() is True
    assert sim.minute == start + 10
    assert sim.player.location == original_player
    assert sim.player.energy == original_energy
    with get_connection() as conn:
        row = conn.execute(
            "SELECT action, target FROM events WHERE actor_id=? "
            "AND action='WANDER' ORDER BY id DESC LIMIT 1", (entity_id,),
        ).fetchone()
        waypoint = conn.execute(
            "SELECT waypoint FROM generated_actor_motion WHERE actor_id=?",
            (entity_id,),
        ).fetchone()
        assert conn.execute(
            "SELECT COUNT(*) FROM pending_actions WHERE actor_id='PLAYER_1'"
        ).fetchone()[0] == 0
    assert row == ("WANDER", original_player)
    assert waypoint == (1,)
    assert {"id": entity_id, "name": "Eco", "patrol_step": 1} in (
        build_player_snapshot()["visible_actors"]
    )


def test_local_waypoint_persists_and_cannot_be_set_by_player():
    sim, entity_id = world_with_entity()
    sim.refresh_generated_actors()
    assert sim.validate_intent(
        sim.player, ActionIntent("PLAYER_1", "WANDER", sim.player.location),
    ) == (False, "INVALID_WANDER")
    clock = WorldClock(sim, RLock(), interval=8)
    for _ in range(2):
        clock.tick_once()
    with get_connection() as conn:
        assert conn.execute(
            "SELECT waypoint FROM generated_actor_motion WHERE actor_id=?",
            (entity_id,),
        ).fetchone() == (2,)
    restarted = Simulation()
    assert restarted.all_agents[entity_id].location == sim.player.location
    assert {"id": entity_id, "name": "Eco", "patrol_step": 2} in (
        build_player_snapshot()["visible_actors"]
    )


def test_clock_pauses_during_open_player_conversation_and_resumes_after_pause():
    sim, entity_id = world_with_entity()
    clock = WorldClock(sim, RLock(), interval=8)
    create_or_get_interaction(
        initiator_id="PLAYER_1", recipient_id=entity_id,
        topic="PLAYER_INITIATED_CONVERSATION",
        source_goal="UNKNOWN", minute=sim.minute,
    )
    start_player_conversation(entity_id, sim.minute)
    clock.note_player_dialogue_active()
    start = sim.minute
    assert clock.tick_once() is False
    assert sim.minute == start
    with get_connection() as conn:
        conn.execute(
            """UPDATE interactions SET status='PAUSED'
               WHERE initiator_id='PLAYER_1' AND recipient_id=?""",
            (entity_id,),
        )
    assert clock.tick_once() is True
    assert sim.minute == start + 10


def test_legacy_actor_projection_has_no_unneeded_new_fields():
    sim = Simulation()
    snapshot = build_player_snapshot()
    assert all(
        "patrol_step" not in actor for actor in snapshot["visible_actors"]
        if actor["id"] in {"AGENT_K", "AGENT_NORA"}
    )


def test_abandoned_open_conversation_does_not_freeze_clock_after_restart():
    sim, entity_id = world_with_entity()
    create_or_get_interaction(
        initiator_id="PLAYER_1", recipient_id=entity_id,
        topic="PLAYER_INITIATED_CONVERSATION",
        source_goal="UNKNOWN", minute=sim.minute,
    )
    start_player_conversation(entity_id, sim.minute)
    # On a new Uvicorn process the old interaction is still OPEN in world.db,
    # but the client has not signalled any visible chat session.
    restarted = Simulation()
    clock = WorldClock(restarted, RLock(), interval=8)
    starting_minute = restarted.minute
    assert clock.tick_once() is True
    assert restarted.minute == starting_minute + 10
    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM events WHERE actor_id=? AND action='WANDER'",
            (entity_id,),
        ).fetchone()[0] == 1


def test_expired_dialogue_heartbeat_resumes_even_if_pause_request_was_lost(monkeypatch):
    import server.world_core.realtime as realtime
    sim, entity_id = world_with_entity()
    create_or_get_interaction(
        initiator_id="PLAYER_1", recipient_id=entity_id,
        topic="PLAYER_INITIATED_CONVERSATION",
        source_goal="UNKNOWN", minute=sim.minute,
    )
    start_player_conversation(entity_id, sim.minute)
    now = [100.0]
    monkeypatch.setattr(realtime, "monotonic", lambda: now[0])
    clock = WorldClock(sim, RLock(), interval=8)
    clock.note_player_dialogue_active()
    assert clock.tick_once() is False
    now[0] += 5.0
    assert clock.tick_once() is True
    assert sim.minute == 10
    # The next deliberate UI heartbeat re-pauses an existing conversation.
    clock.note_player_dialogue_active()
    assert clock.tick_once() is False
