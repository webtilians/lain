"""Echoes: whoever closes their session in NODO_07 (the ending «Desconectarte»)
leaves an echo in the world.

The echo walks the places that player used to go, one after another, and anyone
can talk to it. It answers with what that player lived in this game (their
decisions, in first person): with the AI when it is on, from those memories when
it is off. Echoes are passive like the residents: the simulation never plans for
them, they only move along their route and listen.
"""
import time

from .database import get_connection
from .locations import LOCATION_GRAPH
from .models import Agent

PREFIX = "ECHO_"
# Real seconds in each place before walking on. Not world minutes: online, an hour of the world
# lasts under a minute, and nobody would ever catch the echo.
STAY = 20 * 60
ROUTE_TTL = 10 * 60  # how long a computed route is reused before reading the player's history again
ROUTE = 3            # how many of the player's usual places it walks
PRIVATE = {"APARTMENT"}  # everyone's home is their own: an echo never waits there
FALLBACK = "APARTMENT_DISTRICT"
FAREWELL = "Cerré mi sesión en NODO_07 para que ella pudiera descansar. Si me lees, alguien me recibe."


def enabled() -> bool:
    from . import layer_seven
    return layer_seven.enabled()


def is_echo(actor_id: str) -> bool:
    return str(actor_id).startswith(PREFIX)


def player_of(echo_id: str) -> str:
    return echo_id[len(PREFIX):]


def _ready(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_seven'").fetchone() is not None


_routes: dict = {}


def route(c, player: str) -> list[str]:
    """The player's usual public places, most visited first. Read from their history every ROUTE_TTL."""
    # Keyed by database too: a world restored or swapped in the same process has other histories.
    key = (str(c.execute("PRAGMA database_list").fetchone()[2]), player)
    cached = _routes.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    places = [place for (place,) in c.execute(
        "SELECT target FROM events WHERE actor_id=? AND action='MOVE' GROUP BY target "
        "ORDER BY COUNT(*) DESC, target", (player,)).fetchall()
        if place in LOCATION_GRAPH and place not in PRIVATE]
    places = places[:ROUTE] or [FALLBACK]
    _routes[key] = (time.monotonic() + ROUTE_TTL, places)
    return places


def place_at(c, player: str, minute: int = 0) -> str:
    places = route(c, player)
    return places[int(time.time() // STAY) % len(places)]


def sync(c, minute: int) -> list[tuple[str, str, str]]:
    """Every echo there should be, with its place now: (echo id, name, location). Rows are created or moved."""
    if not enabled() or not _ready(c):
        return []
    echoes = []
    for player, name in c.execute(
            "SELECT a.id, a.name FROM layer_seven s JOIN agents a ON a.id=s.player_id "
            "WHERE s.decision='DISCONNECT' AND a.controller_type='HUMAN' ORDER BY a.id").fetchall():
        echo, label, place = PREFIX + player, f"Eco de {name}", place_at(c, player, minute)
        c.execute("INSERT OR IGNORE INTO agents (id,name,faction,location,goal,energy,controller_type) "
                  "VALUES (?,?,'ECHO',?,'REMEMBER',1.0,'ECHO')", (echo, label, place))
        # Written only when it actually moves (or its player was renamed), not on every tick.
        c.execute("UPDATE agents SET location=?, name=? WHERE id=? AND (location<>? OR name<>?)",
                  (place, label, echo, place, label))
        echoes.append((echo, label, place))
    return echoes


def initialize_echoes(minute: int = 0) -> list[Agent]:
    with get_connection() as c:
        echoes = sync(c, minute)
    return [Agent(id=echo, name=name, faction="ECHO", location=place, goal="REMEMBER", controller_type="ECHO")
            for echo, name, place in echoes]


def advance_echoes(simulation) -> None:
    """New echoes join the running world and every echo walks on to its next place."""
    with get_connection() as c:
        echoes = sync(c, simulation.minute)
    for echo, name, place in echoes:
        agent = simulation.all_agents.get(echo)
        if agent is None:
            simulation.all_agents[echo] = Agent(id=echo, name=name, faction="ECHO", location=place,
                                                goal="REMEMBER", controller_type="ECHO")
        else:
            agent.location, agent.name = place, name


def memories(echo_id: str) -> list[str]:
    """What the echo remembers: the player's decisions, in first person, and how it ended."""
    from .layer_seven import lived
    with get_connection() as c:
        return lived(c, player_of(echo_id)) + [FAREWELL]


def layer_actor_context(actor: str, player: str) -> list:
    if not is_echo(actor):
        return []
    return [{"id": f"ECHO_MEMORY_{index}", "text": text, "source": player_of(actor), "learned_minute": 0}
            for index, text in enumerate(memories(actor))]


def greeting(name: str) -> str:
    return f"Soy lo que queda de {name.removeprefix('Eco de ')}. Pregúntame qué viví."


def reply(echo_id: str, question: str) -> str:
    """Without the AI, the echo answers with one of its memories, a different one each time you ask."""
    remembered = memories(echo_id)
    with get_connection() as c:
        asked = c.execute(
            "SELECT COUNT(*) FROM player_conversation_turns t JOIN interactions i ON i.id=t.interaction_id "
            "WHERE t.speaker_id=? AND t.source='ECHO_MEMORY'", (echo_id,)).fetchone()[0]
    return remembered[asked % len(remembered)]
