"""Reality 0.4: real legacy identities, visible-only cards, first playable case."""
from server.world_core.action_queue import queue_action
from server.world_core.character_sheets import (
    ORIGIN_NAME_ROLES, actor_role, infer_origin_role, role_step_due,
)
from server.world_core.database import get_connection, save_agent
from server.world_core.episodic_memory import initialize_memory_provenance
from server.world_core.generated_entities import (
    EntityProposal, create_entity_from_turn, initialize_generated_entities,
)
from server.world_core.player_conversation import initialize_conversation_turns
from server.world_core.player_view import build_player_snapshot
from server.world_core.simulation import Simulation
from server.world_core.station_echo import CASE_ID, station_case_snapshot


def make_entity(sim: Simulation, name: str, seed_goal="OBSERVE_WORLD") -> str:
    initialize_generated_entities()
    initialize_memory_provenance()
    initialize_conversation_turns()
    with get_connection() as conn:
        turn = conn.execute(
            """INSERT INTO player_conversation_turns
               (interaction_id, speaker_id, text, source, minute)
               VALUES (?, 'AGENT_NORA', ?, 'LLM_DIALOGUE', ?)""",
            ("R04_TEST_" + name, "He visto una nueva presencia: " + name, sim.minute),
        ).lastrowid
        entity = create_entity_from_turn(
            conn, creator_id="AGENT_NORA", origin_turn_id=turn,
            proposal=EntityProposal(
                name, "Observa una huella en la estacion", seed_goal,
            ), minute=sim.minute,
        )
    sim.refresh_generated_actors()
    agent = sim.all_agents[entity]
    agent.location = "STATION"
    save_agent(agent)
    return entity


def station_player(sim: Simulation):
    sim.player.location = "STATION"
    save_agent(sim.player)


def player_action(sim: Simulation, action: str, target="NODE_07"):
    action_id = queue_action(
        actor_id="PLAYER_1", action=action, target=target, source="HUMAN",
    )
    return sim.tick()[action_id]


def test_all_seven_existing_names_get_independent_provisional_roles():
    roles = {
        infer_origin_role(name, "Una presencia generada", "OBSERVE_WORLD")
        for name in ORIGIN_NAME_ROLES
    }
    assert len(roles) == 7
    assert infer_origin_role("Eco", "Una presencia", "OBSERVE_WORLD") == "OBSERVER"


def test_legacy_profile_migration_preserves_origin_memory_and_identity():
    sim = Simulation()
    entity_id = make_entity(sim, "Node 07 Inquiry")
    with get_connection() as conn:
        original = conn.execute(
            "SELECT id, creator_id, seed_goal, premise FROM generated_entities WHERE id=?",
            (entity_id,),
        ).fetchone()
        original_memories = conn.execute(
            "SELECT memory FROM agent_memory WHERE agent_id=? ORDER BY id",
            (entity_id,),
        ).fetchall()
        # A save from before Reality 0.4 has no profile sidecar.
        conn.execute(
            "DELETE FROM generated_actor_profiles WHERE actor_id=?", (entity_id,)
        )
    restarted = Simulation()
    assert entity_id in restarted.all_agents
    assert actor_role(entity_id) == "INQUIRER"
    with get_connection() as conn:
        assert conn.execute(
            "SELECT id, creator_id, seed_goal, premise FROM generated_entities WHERE id=?",
            (entity_id,),
        ).fetchone() == original
        assert conn.execute(
            "SELECT memory FROM agent_memory WHERE agent_id=? ORDER BY id",
            (entity_id,),
        ).fetchall() == original_memories
        assert conn.execute(
            "SELECT assignment FROM generated_actor_profiles WHERE actor_id=?",
            (entity_id,),
        ).fetchone() == ("ORIGIN_PROVISIONAL",)


def test_npc_cards_hide_remote_actors_and_private_fields():
    sim = Simulation()
    remote = make_entity(sim, "Monitor Entities")
    local = make_entity(sim, "Node 07 Explorer", "EXPLORE")
    station_player(sim)
    sim.all_agents[remote].location = "APARTMENT"
    save_agent(sim.all_agents[remote])
    snapshot = build_player_snapshot()
    cards = snapshot["character_sheets"]
    assert cards["player"]["id"] == "PLAYER_1"
    assert cards["player"]["agency"] == "HUMAN_ONLY"
    assert {card["id"] for card in cards["visible_npcs"]}.issuperset({local})
    assert remote not in {card["id"] for card in cards["visible_npcs"]}
    npc_card = next(card for card in cards["visible_npcs"] if card["id"] == local)
    assert npc_card["role"] == "SCOUT"
    assert not ({"memory", "creator_id", "seed_goal", "goal", "energy",
                 "beliefs", "location"} & set(npc_card))


def test_role_step_phase_is_stable_and_no_longer_all_agents_move_at_once():
    ids = ["ENTITY_A1", "ENTITY_B2", "ENTITY_C3", "ENTITY_D4", "ENTITY_E5"]
    role = "MONITOR"
    sequences = [
        tuple(role_step_due(actor_id, role, minute) for minute in range(10, 110, 10))
        for actor_id in ids
    ]
    assert len(set(sequences)) > 1
    assert all(sum(sequence) == 2 for sequence in sequences)
    assert role_step_due("ENTITY_FALLBACK", "OBSERVER", 10)


def test_case_requires_direct_player_investigation_not_observe_or_remote_action():
    sim = Simulation()
    assert station_case_snapshot("PLAYER_1")["status"] == "UNSEEN"
    assert player_action(sim, "BROADCAST_TRACE")["reason"] == "CASE_NOT_PRESENT"
    station_player(sim)
    assert player_action(sim, "BROADCAST_TRACE")["reason"] == "CASE_NOT_DISCOVERED"
    assert player_action(sim, "OBSERVE")["accepted"]
    assert station_case_snapshot("PLAYER_1")["status"] == "UNSEEN"
    result = player_action(sim, "INVESTIGATE")
    assert result["accepted"]
    assert station_case_snapshot("PLAYER_1")["status"] == "TRACE_FOUND"
    assert player_action(sim, "INVESTIGATE")["accepted"]
    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM events WHERE action='CASE_ECHO_DISCOVERED'"
        ).fetchone()[0] == 1


def test_broadcast_only_informs_colocated_witnesses_and_prompts_distinct_response():
    sim = Simulation()
    station_player(sim)
    inquiry = make_entity(sim, "Node 07 Inquiry")
    explorer = make_entity(sim, "Node 07 Explorer", "OBSERVE_WORLD")
    remote = make_entity(sim, "Monitor Entities")
    sim.all_agents[remote].location = "APARTMENT"
    save_agent(sim.all_agents[remote])
    assert player_action(sim, "INVESTIGATE")["accepted"]
    assert player_action(sim, "BROADCAST_TRACE")["accepted"]
    case = station_case_snapshot("PLAYER_1")
    assert case["status"] == "RESOLVED"
    assert case["resolution"] == "BROADCAST_TRACE"
    assert case["witness_count"] == 2
    assert player_action(sim, "ARCHIVE_TRACE")["reason"] == "CASE_ALREADY_RESOLVED"
    with get_connection() as conn:
        informed = conn.execute(
            "SELECT actor_id, source FROM station_echo_witnesses ORDER BY actor_id"
        ).fetchall()
        assert informed == sorted([
            (inquiry, "PLAYER_TESTIMONY"), (explorer, "PLAYER_TESTIMONY")
        ])
        assert conn.execute(
            """SELECT COUNT(*) FROM node_beliefs
               WHERE agent_id=? AND source='DIRECT_PERCEPTION'""", (remote,),
        ).fetchone()[0] == 0
    for _ in range(18):
        sim.tick()
        if len(station_case_snapshot("PLAYER_1")["responses"]) == 2:
            break
    case = station_case_snapshot("PLAYER_1")
    assert len(case["responses"]) == 2
    assert len({entry["reaction"] for entry in case["responses"]}) == 2
    assert {entry["actor_id"] for entry in case["responses"]} == {inquiry, explorer}
    assert Simulation().all_agents[inquiry].id == inquiry
    assert station_case_snapshot("PLAYER_1")["responses"] == case["responses"]


def test_archiving_keeps_evidence_private_and_never_recruits_witnesses():
    sim = Simulation()
    station_player(sim)
    npc = make_entity(sim, "Node 07 Inquiry")
    assert player_action(sim, "INVESTIGATE")["accepted"]
    assert player_action(sim, "ARCHIVE_TRACE")["accepted"]
    assert station_case_snapshot("PLAYER_1")["resolution"] == "ARCHIVE_TRACE"
    for _ in range(7):
        sim.tick()
    assert station_case_snapshot("PLAYER_1")["witness_count"] == 0
    assert station_case_snapshot("PLAYER_1")["responses"] == []
    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM station_echo_witnesses WHERE actor_id=?",
            (npc,),
        ).fetchone()[0] == 0
    assert player_action(sim, "BROADCAST_TRACE")["reason"] == "CASE_ALREADY_RESOLVED"


def test_npc_prompt_receives_only_its_own_role_and_station_testimony():
    from server.world_core.character_sheets import generated_role_context
    from server.world_core.station_echo import actor_received_case_report

    sim = Simulation()
    station_player(sim)
    informed = make_entity(sim, "Node 07 Inquiry")
    uninformed = make_entity(sim, "Monitor Entities")
    sim.all_agents[uninformed].location = "APARTMENT"
    save_agent(sim.all_agents[uninformed])
    assert generated_role_context(informed)["role"] == "INQUIRER"
    assert generated_role_context(uninformed)["role"] == "MONITOR"
    assert generated_role_context("AGENT_NORA") is None
    assert actor_received_case_report(informed) is None
    assert player_action(sim, "INVESTIGATE")["accepted"]
    assert player_action(sim, "BROADCAST_TRACE")["accepted"]
    report = actor_received_case_report(informed)
    assert report is not None
    assert report["source"] == "PLAYER_TESTIMONY"
    assert "mi observación" in report["report"]
    assert actor_received_case_report(uninformed) is None
    assert actor_received_case_report("AGENT_NORA") is None
