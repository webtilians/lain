"""Reality 0.1: deterministic integration tests, no live LLM or player data."""
import pytest

from server.world_core.database import get_connection, save_agent
from server.world_core.episodic_memory import initialize_memory_provenance
from server.world_core.generated_entities import (
    EntityProposal, create_entity_from_turn, initialize_generated_entities,
    list_generated_entities, validate_proposal,
)
from server.world_core.interactions import create_or_get_interaction
from server.world_core.llm_dialogue import DialogueReply
from server.world_core.player_conversation import (
    initialize_conversation_turns, start_player_conversation,
)
from server.world_core.player_view import build_player_snapshot
from server.world_core.simulation import Simulation
from server.world_core import free_conversation


def initialize():
    sim = Simulation()
    initialize_generated_entities()
    initialize_memory_provenance()
    initialize_conversation_turns()
    return sim


def insert_npc_turn(conn, creator="AGENT_NORA", source="LLM_DIALOGUE"):
    return conn.execute(
        """INSERT INTO player_conversation_turns
           (interaction_id, speaker_id, text, source, minute)
           VALUES ('TEST_CONVERSATION', ?, 'Vi una presencia desconocida', ?, 0)""",
        (creator, source),
    ).lastrowid


def test_proposal_is_bounded_and_does_not_accept_reserved_identity():
    assert validate_proposal({
        "name": "Eco", "premise": "Una presencia surgida de la Wired",
        "goal": "OBSERVE_WORLD",
    }).name == "Eco"
    for bad in (
        {"name": "Nora", "premise": "Una nueva presencia digital", "goal": "EXPLORE"},
        {"name": "Eco", "premise": "x", "goal": "EXPLORE"},
        {"name": "Eco", "premise": "Una nueva presencia digital", "goal": "WIPE_DATABASE"},
        {"name": "Eco", "premise": "Una nueva presencia digital", "goal": "EXPLORE",
         "sql": "DROP TABLE agents"},
    ):
        with pytest.raises(ValueError, match="INVALID_ENTITY_PROPOSAL"):
            validate_proposal(bad)


def test_creation_requires_a_persisted_npc_llm_reply():
    initialize()
    proposal = EntityProposal("Eco", "Una presencia surgida de la Wired", "OBSERVE_WORLD")
    with get_connection() as conn:
        human_turn = insert_npc_turn(conn, creator="PLAYER_1")
        scripted_turn = insert_npc_turn(conn, source="DETERMINISTIC_DIALOGUE")
        with pytest.raises(ValueError, match="UNAUTHORIZED_ENTITY_CREATION"):
            create_entity_from_turn(
                conn, creator_id="AGENT_NORA",
                origin_turn_id=human_turn, proposal=proposal, minute=0,
            )
        with pytest.raises(ValueError, match="UNAUTHORIZED_ENTITY_CREATION"):
            create_entity_from_turn(
                conn, creator_id="AGENT_NORA",
                origin_turn_id=scripted_turn, proposal=proposal, minute=0,
            )
    assert list_generated_entities() == []


def test_entity_memory_goal_actions_survive_restart():
    sim = initialize()
    proposal = EntityProposal("Eco", "Una sombra que emerge de la señal", "SEEK_CREATOR")
    with get_connection() as conn:
        origin = insert_npc_turn(conn)
        entity_id = create_entity_from_turn(
            conn, creator_id="AGENT_NORA",
            origin_turn_id=origin, proposal=proposal, minute=sim.minute,
        )
        assert create_entity_from_turn(
            conn, creator_id="AGENT_NORA",
            origin_turn_id=origin, proposal=proposal, minute=sim.minute,
        ) == entity_id

    with get_connection() as conn:
        agent = conn.execute(
            "SELECT name, location, goal, controller_type FROM agents WHERE id = ?",
            (entity_id,),
        ).fetchone()
        memories = conn.execute(
            "SELECT memory FROM agent_memory WHERE agent_id = ?", (entity_id,),
        ).fetchall()
        genesis = conn.execute(
            "SELECT source_kind, source_actor_id FROM agent_memory_provenance "
            "WHERE memory_id IN (SELECT id FROM agent_memory WHERE agent_id = ?)",
            (entity_id,),
        ).fetchone()
    assert agent == ("Eco", sim.nora.agent.location, "SEEK_CREATOR", "GENERATED")
    assert len(memories) == 1 and "sombra" in memories[0][0]
    assert genesis == ("GENERATED_ORIGIN", "AGENT_NORA")
    assert len(list_generated_entities()) == 1

    # The creator moves away; the entity's own persisted goal drives its move.
    sim.nora.agent.location = "STATION"
    save_agent(sim.nora.agent)
    sim.tick()
    assert entity_id in sim.all_agents
    assert sim.all_agents[entity_id].location == "STATION"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT action, target FROM events WHERE actor_id = ? ORDER BY id",
            (entity_id,),
        ).fetchall()
    assert ("MOVE", "STATION") in rows

    restarted = Simulation()
    assert entity_id in restarted.all_agents
    assert restarted.all_agents[entity_id].location == "STATION"
    assert restarted.all_agents[entity_id].goal == "SEEK_CREATOR"
    # Genesis survives, and the entity can acquire new memories on its own.
    assert memories[0][0] in restarted.all_agents[entity_id].memory
    assert any("Discovered anomalous node NODE_12" in item
               for item in restarted.all_agents[entity_id].memory)


def test_entity_creation_rolls_back_with_dialogue_transaction():
    initialize()
    proposal = EntityProposal("Eco", "Una presencia que emerge en silencio", "EXPLORE")
    with pytest.raises(RuntimeError):
        with get_connection() as conn:
            origin = insert_npc_turn(conn)
            create_entity_from_turn(
                conn, creator_id="AGENT_NORA", origin_turn_id=origin,
                proposal=proposal, minute=0,
            )
            raise RuntimeError("simulated crash")
    assert list_generated_entities() == []
    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM agents WHERE controller_type='GENERATED'"
        ).fetchone()[0] == 0


def test_npc_free_dialogue_creates_persistent_visible_actor_without_duplicate(monkeypatch):
    sim = initialize()
    sim.player.location = sim.nora.agent.location
    save_agent(sim.player)
    interaction, _ = create_or_get_interaction(
        initiator_id="PLAYER_1", recipient_id="AGENT_NORA",
        topic="PLAYER_INITIATED_CONVERSATION",
        source_goal="UNKNOWN", minute=sim.minute,
    )
    greeting = start_player_conversation("AGENT_NORA", sim.minute)
    monkeypatch.setattr(
        free_conversation, "generate_dialogue_reply",
        lambda **kw: DialogueReply("He visto una nueva voz en la Wired.", "LLM_DIALOGUE"),
    )
    monkeypatch.setattr(
        free_conversation, "suggest_entity",
        lambda *args, **kwargs: EntityProposal(
            "Eco", "Una voz aparecida en la Wired", "OBSERVE_WORLD",
        ),
    )
    response = free_conversation.say_to_player_conversation(
        "AGENT_NORA", "¿Qué has visto?", greeting["turn_id"], sim.minute,
    )
    assert response["line"] == "He visto una nueva voz en la Wired."
    entities = list_generated_entities()
    assert len(entities) == 1
    entity_id = entities[0][0]
    snapshot = build_player_snapshot()
    assert {"id": entity_id, "name": "Eco"} in snapshot["visible_actors"]
    assert free_conversation.say_to_player_conversation(
        "AGENT_NORA", "¿Qué has visto?", greeting["turn_id"], sim.minute,
    )["turn_id"] == response["turn_id"]
    assert len(list_generated_entities()) == 1
    sim.tick()
    assert entity_id in sim.all_agents
    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM events WHERE action='ENTITY_CREATED'"
        ).fetchone()[0] == 1


def test_scripted_npc_reply_never_creates_an_entity(monkeypatch):
    sim = initialize()
    sim.player.location = sim.nora.agent.location
    save_agent(sim.player)
    create_or_get_interaction(
        initiator_id="PLAYER_1", recipient_id="AGENT_NORA",
        topic="PLAYER_INITIATED_CONVERSATION",
        source_goal="UNKNOWN", minute=sim.minute,
    )
    greeting = start_player_conversation("AGENT_NORA", sim.minute)
    monkeypatch.setattr(
        free_conversation, "generate_dialogue_reply",
        lambda **kw: DialogueReply("He visto una nueva voz en la Wired.",
                                   "DETERMINISTIC_DIALOGUE"),
    )
    monkeypatch.setattr(
        free_conversation, "suggest_entity",
        lambda *args, **kwargs: pytest.fail("scripted dialogue proposed creation"),
    )
    free_conversation.say_to_player_conversation(
        "AGENT_NORA", "¿Qué has visto?", greeting["turn_id"], sim.minute,
    )
    assert list_generated_entities() == []


def test_wired_projection_shows_presence_not_private_memories():
    from server.world_core.messages import INITIAL_MESSAGE_ID
    from server.world_core.wired import process_wired_message_acknowledgement

    sim = initialize()
    with get_connection() as conn:
        origin = insert_npc_turn(conn)
        entity_id = create_entity_from_turn(
            conn, creator_id="AGENT_NORA", origin_turn_id=origin,
            proposal=EntityProposal(
                "Eco", "Una presencia con memoria privada que nadie debe leer",
                "OBSERVE_WORLD",
            ), minute=sim.minute,
        )
    disconnected = build_player_snapshot()["wired"]
    assert disconnected["connected"] is False
    assert disconnected["digital_presences"] == []

    process_wired_message_acknowledgement(
        message_id=INITIAL_MESSAGE_ID, player_id="PLAYER_1", minute=sim.minute,
    )
    connected = build_player_snapshot()["wired"]
    assert connected["connected"] is True
    assert connected["digital_presences"] == [{"id": entity_id, "name": "Eco"}]
    assert "memoria privada" not in repr(connected)
    assert "creator_id" not in repr(connected)
