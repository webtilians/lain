"""City09: persistent identity, privacy, clock authority and existing saves."""
import json
from server.world_core import residents
from server.world_core.database import get_connection, save_agent
from server.world_core.simulation import Simulation
from server.world_core.player_view import list_visible_actors
from server.world_core.character_sheets import visible_npc_sheets
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.locations import shortest_path
from server.world_core.models import ActionIntent


def populated(monkeypatch):
    monkeypatch.setenv("LAIN_CITY_RESIDENTS_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    return Simulation()


def test_population_is_real_unique_persistent_and_opt_in(monkeypatch):
    old = Simulation()
    assert len(old.all_agents) == 3
    sim = populated(monkeypatch)
    catalog = residents.load_catalog()
    assert len(catalog) == 56
    assert len({c["name"] for c in catalog}) == 56
    assert len(sim.all_agents) == 59
    assert all(c["objective"] and c["skills"] for c in catalog)
    with get_connection() as conn:
        before = conn.execute("SELECT * FROM city_residents ORDER BY actor_id").fetchall()
        # An already edited citizen/save wins over the default catalog.
        profile = json.loads(before[0][1])
        profile["objective"] = "Objetivo editado por el jugador."
        conn.execute("UPDATE city_residents SET profile=? WHERE actor_id=?",
                     (json.dumps(profile), before[0][0]))
        conn.execute("UPDATE agents SET name='Nombre editado' WHERE id=?", (before[0][0],))
    monkeypatch.setenv("LAIN_CITY_RESIDENTS_ENABLED","0")
    resumed = Simulation()
    assert len(resumed.all_agents) == 59
    assert resumed.all_agents["RESIDENT_001"].name == "Nombre editado"
    assert residents.public_residents("APARTMENT_DISTRICT")["RESIDENT_001"]["public_objective"] == profile["objective"]
    assert resumed.k.agent.memory == sim.k.agent.memory


def test_projection_is_colocated_read_only_and_has_no_private_memory(monkeypatch):
    sim = populated(monkeypatch)
    before = residents.public_residents("APARTMENT_DISTRICT")
    visible = list_visible_actors("PLAYER_1","APARTMENT_DISTRICT")
    ids = {a["id"] for a in visible}
    assert len(ids.intersection(sim.all_agents.keys())) == 17  # K and 16 civilians
    assert "RESIDENT_017" not in ids  # teacher in school
    assert not residents.public_residents("APARTMENT")
    sheets = visible_npc_sheets("PLAYER_1","APARTMENT_DISTRICT")
    resident = next(a for a in sheets if a["id"] == "RESIDENT_001")
    assert resident["skills"] and resident["public_objective"] and resident["activity"]
    for entry in visible + sheets:
        assert not {"memory","beliefs","goal","profile","activities","last_minute"} & entry.keys()
    for _ in range(4):
        list_visible_actors("PLAYER_1","APARTMENT_DISTRICT")
    assert residents.public_residents("APARTMENT_DISTRICT") == before


def test_routines_are_tick_driven_persistent_idempotent_and_pause_for_chat(monkeypatch):
    sim = populated(monkeypatch)
    before = residents.public_residents("APARTMENT_DISTRICT")["RESIDENT_001"]
    sim.tick()  # phase 1 at minute 10
    first = residents.public_residents("APARTMENT_DISTRICT")["RESIDENT_001"]
    assert first["patrol_step"] == (before["patrol_step"]+1) % 4
    residents.advance_residents(sim.minute)
    assert residents.public_residents("APARTMENT_DISTRICT")["RESIDENT_001"] == first
    restarted = Simulation()
    assert residents.public_residents("APARTMENT_DISTRICT")["RESIDENT_001"] == first
    restarted.player.location = "APARTMENT_DISTRICT"
    save_agent(restarted.player)
    from server.api import perform_player_step
    result = perform_player_step(action="CONTACT", target="RESIDENT_001", simulation=restarted)
    assert result["action_result"]["accepted"]
    with get_connection() as conn:
        assert conn.execute("SELECT 1 FROM interactions WHERE recipient_id='RESIDENT_001' AND status='OPEN'").fetchone()
    for _ in range(8):
        restarted.tick()
    assert residents.public_residents("APARTMENT_DISTRICT")["RESIDENT_001"]["patrol_step"] == first["patrol_step"]
    with get_connection() as conn:
        conn.execute("UPDATE interactions SET status='PAUSED' WHERE recipient_id='RESIDENT_001'")
    for _ in range(3):
        restarted.tick()
    assert residents.public_residents("APARTMENT_DISTRICT")["RESIDENT_001"]["patrol_step"] != first["patrol_step"]


def test_own_context_does_not_import_other_resident_or_k_nora_memories(monkeypatch):
    sim = populated(monkeypatch)
    own = AgentContextBuilder().build("RESIDENT_001")
    assert own["resident"]["role"] == "Cartero"
    assert not own["beliefs"]["nodes"]
    assert "resident" not in AgentContextBuilder().build("AGENT_K")
    assert "resident" not in AgentContextBuilder().build("AGENT_NORA")
    assert "Orientación" in own["resident"]["skills"]
    assert "Matemáticas" not in own["resident"]["skills"]
    assert sim.all_agents["RESIDENT_001"].controller_type == "RESIDENT"


def test_shops_have_reversible_graph_edges_and_no_player_forced_npc_motion(monkeypatch):
    sim = populated(monkeypatch)
    for location in ("IZAKAYA","GROCERY","VIDEO_CLUB","BOOKSHOP","ARCADE","CAFE"):
        assert shortest_path("APARTMENT",location) == ["APARTMENT","APARTMENT_DISTRICT",location]
        assert shortest_path(location,"APARTMENT") == [location,"APARTMENT_DISTRICT","APARTMENT"]
    agent = sim.all_agents["RESIDENT_001"]
    accepted, _reason = sim.validate_intent(agent, ActionIntent(agent.id,"WANDER",agent.location,"AI"))
    assert not accepted


def test_resident_chat_uses_its_own_activity_and_real_conversation_pipeline(monkeypatch):
    sim = populated(monkeypatch)
    sim.player.location = "VIDEO_CLUB"
    save_agent(sim.player)
    from server.api import perform_player_step
    from server.world_core.player_conversation import start_player_conversation
    from server.world_core.free_conversation import say_to_player_conversation
    result = perform_player_step(action="CONTACT", target="RESIDENT_045", simulation=sim)
    assert result["action_result"]["accepted"]
    greeting = start_player_conversation("RESIDENT_045", sim.minute)
    assert "Makoto Ishikawa" in greeting["line"]
    reply = say_to_player_conversation("RESIDENT_045", "¿Qué haces aquí?",
                                      greeting["turn_id"], sim.minute)
    assert reply["response_source"] == "DETERMINISTIC_RESIDENT_PROFILE"
    assert "cinta" in reply["line"]
    assert "Cartero" not in reply["line"]


def test_explicit_catalog_edit_preserves_position_progress_and_existing_memory(monkeypatch):
    sim = populated(monkeypatch)
    sim.tick()
    before = residents.public_residents("APARTMENT_DISTRICT")["RESIDENT_001"]
    catalog = residents.load_catalog()
    edited = dict(catalog[0], name="Mi vecino", objective="Preparar una exposición.",
                  location="STATION", slot=15)
    monkeypatch.setattr(residents, "load_catalog", lambda: [edited])
    assert residents.apply_catalog_profiles() == 1
    after = residents.public_residents("APARTMENT_DISTRICT")["RESIDENT_001"]
    assert after["public_objective"] == "Preparar una exposición."
    assert after["patrol_step"] == before["patrol_step"]
    assert after["slot"] == before["slot"]
    with get_connection() as conn:
        assert conn.execute("SELECT name FROM agents WHERE id='RESIDENT_001'").fetchone()[0] == "Mi vecino"
    assert residents.public_residents("STATION").get("RESIDENT_001") is None
