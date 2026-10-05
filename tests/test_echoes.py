"""Echoes: whoever disconnects in NODO_07 leaves an echo that walks their usual places and talks with their memories."""
import pytest

from server.world_core import echoes, i18n
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection
from server.world_core.player_view import list_visible_actors
from tests.test_layer_seven import node  # noqa: F401 (fixture)
from tests.test_layer_four import PLAYER, connected, layer_three_game  # noqa: F401 (fixtures)
from tests.test_layer_five import archive  # noqa: F401 (fixture)
from tests.test_layer_six import club  # noqa: F401 (fixture)

ANA = "PLAYER_ANA"


def ana_disconnected(places):
    """Another real player who walked these places and then closed her session in NODO_07."""
    with get_connection() as c:
        c.execute("INSERT INTO agents(id,name,faction,location,goal,energy,controller_type) "
                  "VALUES(?,'Ana','UNALIGNED','APARTMENT','UNKNOWN',1,'HUMAN')", (ANA,))
        c.execute("INSERT INTO layer_three(player_id, started_minute, connection_minute, decision) "
                  "VALUES(?, 1, 1, 'FORWARD')", (ANA,))
        c.execute("INSERT INTO layer_seven(player_id, started_minute, language, previous, inside, decision) "
                  "VALUES(?, 1, 'es', 'KEEP', 1, 'DISCONNECT')", (ANA,))
        for place, times in places.items():
            for minute in range(times):
                c.execute("INSERT INTO events(minute, actor_id, action, target, details) VALUES(?,?,'MOVE',?,'')",
                          (minute, ANA, place))


def location(actor):
    with get_connection() as c:
        return c.execute("SELECT location FROM agents WHERE id=?", (actor,)).fetchone()[0]


def test_an_echo_walks_its_players_usual_places_but_never_a_home(node, monkeypatch):
    sim, _word, _name = node
    ana_disconnected({"APARTMENT": 9, "CAFE": 5, "STATION": 3, "SCHOOL": 1, "NOWHERE": 7})
    clock = [0.0]
    monkeypatch.setattr(echoes.time, "time", lambda: clock[0])
    sim.tick()
    echo = echoes.PREFIX + ANA
    assert echo in sim.all_agents and sim.all_agents[echo].controller_type == "ECHO"
    with get_connection() as c:
        assert echoes.route(c, ANA) == ["CAFE", "STATION", "SCHOOL"]
    seen = set()
    for stay in range(3):
        clock[0] = stay * echoes.STAY + 1
        sim.tick()
        seen.add(location(echo))
        assert sim.all_agents[echo].location == location(echo)
        sim.tick()
        assert location(echo) == sorted(seen, key=["CAFE", "STATION", "SCHOOL"].index)[-1], "it stays a while"
    assert seen == {"CAFE", "STATION", "SCHOOL"}


def test_only_disconnecting_leaves_an_echo(node):
    sim, _word, _name = node
    ana_disconnected({"CAFE": 2})
    with get_connection() as c:
        c.execute("UPDATE layer_seven SET decision='PERSIST' WHERE player_id=?", (ANA,))
    sim.tick()
    assert echoes.PREFIX + ANA not in sim.all_agents


def test_other_players_meet_the_echo_and_hear_what_she_lived(node, monkeypatch):
    from server.api import perform_player_step
    from server.world_core.free_conversation import say_to_player_conversation
    from server.world_core.player_conversation import reply_to_player_conversation, start_player_conversation
    from tests.test_chapter_one import move
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    sim, _word, _name = node
    ana_disconnected({"CAFE": 4})
    sim.tick()
    echo = echoes.PREFIX + ANA
    move(sim, "CAFE")
    seen = {actor["id"]: actor for actor in list_visible_actors(PLAYER, "CAFE")}
    assert seen[echo]["name"] == "Eco de Ana" and seen[echo]["kind"] == "echo"
    assert perform_player_step(action="CONTACT", target=echo, simulation=sim)["action_result"]["accepted"]
    greeting = start_player_conversation(echo, sim.minute, player_id=PLAYER)
    assert greeting["line"] == "Soy lo que queda de Ana. Pregúntame qué viví."
    first = say_to_player_conversation(echo, "¿Qué hiciste?", greeting["turn_id"], sim.minute, player_id=PLAYER)
    assert first["response_source"] == "ECHO_MEMORY" and first["line"] == "Reenvié el paquete de la Sesión Cero con un TTL nuevo."
    second = reply_to_player_conversation(echo, "ASK_IDENTITY", first["turn_id"], sim.minute, player_id=PLAYER)
    assert second["line"].startswith("Cerré mi sesión en NODO_07"), "each question brings another memory"
    memories = AgentContextBuilder().build(echo)["chapter_memory"]["memories"]
    assert any("Reenvié el paquete" in memory["text"] for memory in memories)


def test_the_echo_in_english(node, monkeypatch):
    from server.world_core.character_sheets import visible_npc_sheets
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    sim, _word, _name = node
    ana_disconnected({"CAFE": 4})
    sim.tick()
    token = i18n.set_language("en")
    try:
        assert i18n.t("Eco de Ana") == "Echo of Ana"
        assert i18n.t(echoes.greeting("Eco de Ana")) == "I am what is left of Ana. Ask me what I lived."
        sheet = next(item for item in visible_npc_sheets(PLAYER, "CAFE") if item["id"] == echoes.PREFIX + ANA)
        assert i18n.t(sheet["role_label"]) == "Echo"
    finally:
        i18n.reset(token)


@pytest.fixture(autouse=True)
def _quiet_llm(monkeypatch):
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
