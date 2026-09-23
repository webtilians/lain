"""Reality 0.2: the new actor acts from its OWN direct node beliefs.

No model, network or player-private memory is necessary for these checks.
"""
import pytest

from server.world_core.beliefs import save_belief
from server.world_core.database import get_connection, save_agent, save_node
from server.world_core.generated_entities import (
    EntityProposal, belief_driven_goal, create_entity_from_turn,
    initialize_generated_entities, list_generated_entities,
)
from server.world_core.models import NodeBelief
from server.world_core.player_conversation import initialize_conversation_turns
from server.world_core.episodic_memory import initialize_memory_provenance
from server.world_core.simulation import Simulation


def make_entity(seed_goal="OBSERVE_WORLD"):
    sim = Simulation()
    initialize_generated_entities()
    initialize_memory_provenance()
    initialize_conversation_turns()
    with get_connection() as conn:
        turn_id = conn.execute(
            """INSERT INTO player_conversation_turns
               (interaction_id, speaker_id, text, source, minute)
               VALUES ('REALITY_02_TEST', 'AGENT_NORA',
                       'He visto una presencia desconocida.', 'LLM_DIALOGUE', 0)"""
        ).lastrowid
        entity_id = create_entity_from_turn(
            conn, creator_id="AGENT_NORA", origin_turn_id=turn_id,
            proposal=EntityProposal(
                "Eco", "Una voz que despierta en la Wired", seed_goal,
            ), minute=0,
        )
    return sim, entity_id


def test_only_own_fresh_direct_anomaly_can_set_investigation_goal():
    sim, entity_id = make_entity()
    sim.refresh_generated_actors()
    actor = sim.all_agents[entity_id]
    assert belief_driven_goal(actor, 10) is None

    # A rumor, an old sighting or a private belief belonging to Nora must
    # not reveal an otherwise unknown anomaly to the generated character.
    save_belief(NodeBelief(
        agent_id=entity_id, node_id="NODE_07",
        believed_location="STATION", believed_strength=0.95,
        confidence=0.99, source="ANONYMOUS_SIGNAL", updated_minute=10,
    ))
    save_belief(NodeBelief(
        agent_id="AGENT_NORA", node_id="NODE_07",
        believed_location="STATION", believed_strength=0.99,
        confidence=0.99, source="DIRECT_PERCEPTION", updated_minute=10,
    ))
    assert belief_driven_goal(actor, 10) is None

    save_belief(NodeBelief(
        agent_id=entity_id, node_id="NODE_07",
        believed_location="STATION", believed_strength=0.90,
        confidence=0.99, source="DIRECT_PERCEPTION", updated_minute=-100,
    ))
    assert belief_driven_goal(actor, 10) is None

    save_belief(NodeBelief(
        agent_id=entity_id, node_id="NODE_07",
        believed_location="STATION", believed_strength=0.90,
        confidence=0.99, source="DIRECT_PERCEPTION", updated_minute=10,
    ))
    goal = belief_driven_goal(actor, 10)
    assert goal is not None
    assert goal.goal_type == "INVESTIGATE_ANOMALY"
    assert goal.target_id == "NODE_07"
    assert goal.source_situation_id == "PERCEPTION:NODE_07"


def test_entity_reacts_to_direct_anomaly_then_remembers_and_retires_goal():
    sim, entity_id = make_entity()
    with get_connection() as conn:
        conn.execute(
            "UPDATE agents SET location = 'STATION' WHERE id = ?",
            (entity_id,),
        )
    sim.nodes["NODE_07"].anomaly_strength = 0.85
    save_node(sim.nodes["NODE_07"])
    sim.tick()

    actor = sim.all_agents[entity_id]
    assert actor.location == "STATION"
    assert actor.goal == "INVESTIGATE_ANOMALY"
    assert any(
        "Investigated anomalous node NODE_07" in memory
        for memory in actor.memory
    )
    with get_connection() as conn:
        investigate = conn.execute(
            """SELECT COUNT(*) FROM events
               WHERE actor_id = ? AND action = 'INVESTIGATE' AND target = 'NODE_07'""",
            (entity_id,),
        ).fetchone()[0]
    assert investigate == 1

    sim.tick()
    assert actor.goal == "OBSERVE_WORLD"
    with get_connection() as conn:
        investigate_again = conn.execute(
            """SELECT COUNT(*) FROM events
               WHERE actor_id = ? AND action = 'INVESTIGATE' AND target = 'NODE_07'""",
            (entity_id,),
        ).fetchone()[0]
    assert investigate_again == 1

    restarted = Simulation()
    assert entity_id in restarted.all_agents
    assert restarted.all_agents[entity_id].goal == "OBSERVE_WORLD"
    assert any(
        "Investigated anomalous node NODE_07" in memory
        for memory in restarted.all_agents[entity_id].memory
    )
    assert len(list_generated_entities()) == 1


def test_recent_direct_belief_survives_restart_and_can_drive_later_decision():
    sim, entity_id = make_entity()
    sim.refresh_generated_actors()
    agent = sim.all_agents[entity_id]
    save_belief(NodeBelief(
        agent_id=entity_id, node_id="NODE_07",
        believed_location="STATION", believed_strength=0.90,
        confidence=0.85, source="DIRECT_PERCEPTION", updated_minute=10,
    ))
    restarted = Simulation()
    generated = restarted.all_agents[entity_id]
    goal = belief_driven_goal(generated, 30)
    assert goal is not None
    assert goal.target_id == "NODE_07"
    assert goal.believed_location == "STATION"
    assert belief_driven_goal(generated, 70) is None


def test_generated_explorer_stays_when_player_present_and_can_resume_chat():
    from server.world_core.action_queue import queue_action
    from server.world_core.player_conversation import start_player_conversation
    from server.world_core.free_conversation import say_to_player_conversation

    sim, entity_id = make_entity("EXPLORE")
    sim.player.location = sim.nora.agent.location
    save_agent(sim.player)
    sim.tick()
    assert sim.all_agents[entity_id].location == sim.player.location

    queue_action(
        actor_id="PLAYER_1", action="CONTACT", target=entity_id,
        source="HUMAN",
    )
    sim.tick()
    with get_connection() as conn:
        assert conn.execute(
            """SELECT COUNT(*) FROM events
               WHERE actor_id='PLAYER_1' AND action='CONTACT' AND target=?""",
            (entity_id,),
        ).fetchone()[0] == 1

    greeting = start_player_conversation(entity_id, sim.minute)
    answer = say_to_player_conversation(
        entity_id, "¿Qué recuerdas de tu origen?",
        greeting["turn_id"], sim.minute,
    )
    assert answer["actor_id"] == entity_id
    with get_connection() as conn:
        testimony = conn.execute(
            """SELECT source_kind FROM agent_memory_provenance
               WHERE memory_id IN (
                   SELECT id FROM agent_memory WHERE agent_id=?
               ) ORDER BY memory_id DESC LIMIT 1""",
            (entity_id,),
        ).fetchone()
    assert testimony == ("PLAYER_TESTIMONY",)
    assert start_player_conversation(entity_id, sim.minute)["turn_id"] == answer["turn_id"]
