"""Círculo de dos: two players at two different cabinets agree on a Diffie-Hellman key that never travels."""
import re

import pytest

from server.world_core import duo, i18n, layer_three
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection
from tests.test_chapter_one import move
from tests.test_layer_three import PLAYER, game  # noqa: F401 (fixture)

ANA = "PLAYER_ANA"


@pytest.fixture
def two(game):  # noqa: F811
    """The usual player at the school cabinet and Ana, also connected, at the station's."""
    sim = game
    duo.initialize_duo()
    with get_connection() as c:
        c.execute("INSERT INTO agents(id,name,faction,location,goal,energy,controller_type) "
                  "VALUES(?,'Ana','UNALIGNED','STATION','UNKNOWN',1,'HUMAN')", (ANA,))
        c.execute("INSERT INTO layer_three(player_id, started_minute, connection_minute) VALUES(?, 1, 1)", (ANA,))
    move(sim, "SCHOOL_LAB")
    return sim


def sh(sim, player, command, host):
    return layer_three.run_shell(player, host, "/", command, sim.minute)["output"]


def numbers(text, *names):
    return [int(re.search(rf"\b{name} = (\d+)", text).group(1)) for name in names]


def test_two_players_open_a_circle_without_ever_sending_the_key(two):
    sim = two
    opened = sh(sim, PLAYER, "circulo abrir", "RELAY_SCHOOL")
    code = re.search(r"Círculo (C-\d+) abierto en relay-escuela", opened).group(1)
    p, g, a = numbers(opened, "p", "g", "a")
    assert code in sh(sim, ANA, "circulo lista", "RELAY_STATION")
    joined = sh(sim, ANA, f"circulo unirse {code}", "RELAY_STATION")
    assert "con " in joined and numbers(joined, "p", "g") == [p, g]
    (b,) = numbers(joined, "b")
    A = int(sh(sim, PLAYER, f"powmod {g} {a} {p}", "RELAY_SCHOOL").split("= ")[-1])
    B = pow(g, b, p)
    assert "no sale de tu número secreto" in sh(sim, PLAYER, f"circulo publicar {A + 1}", "RELAY_SCHOOL")
    assert "Publicado" in sh(sim, PLAYER, f"circulo publicar {A}", "RELAY_SCHOOL")
    assert "todavía no ha publicado" in sh(sim, PLAYER, "circulo enlazar 5", "RELAY_SCHOOL")
    sh(sim, ANA, f"circulo publicar {B}", "RELAY_STATION")
    assert str(B) in sh(sim, PLAYER, "circulo ver", "RELAY_SCHOOL")
    key = pow(B, a, p)
    assert key == pow(A, b, p)
    assert "no es la vuestra" in sh(sim, PLAYER, f"circulo enlazar {key + 1}", "RELAY_SCHOOL")
    assert "Falta la otra persona" in sh(sim, PLAYER, f"circulo enlazar {key}", "RELAY_SCHOOL")
    final = sh(sim, ANA, f"circulo enlazar {key}", "RELAY_STATION")
    assert final.startswith(f"CÍRCULO DE DOS ABIERTO · {code}") and "la clave nunca viajó" in final
    registry = sh(sim, ANA, "cat /var/circulos/registro", "RELAY_STATION")
    assert code in registry and "Ana" in registry
    with get_connection() as c:
        assert duo.run_for(c, PLAYER)["completed"] and duo.run_for(c, ANA)["completed"]
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("círculo de dos con Ana" in memory["text"] for memory in nora)


def test_a_circle_needs_two_cabinets_and_both_within_ten_minutes(two, monkeypatch):
    sim = two
    code = re.search(r"(C-\d+)", sh(sim, PLAYER, "circulo abrir", "RELAY_SCHOOL")).group(1)
    with get_connection() as c:
        c.execute("UPDATE agents SET location='SCHOOL_LAB' WHERE id=?", (ANA,))
    assert "desde otro armario" in sh(sim, ANA, f"circulo unirse {code}", "RELAY_SCHOOL")
    with get_connection() as c:
        c.execute("UPDATE agents SET location='APARTMENT' WHERE id=?", (ANA,))
    assert "no desde casa" in sh(sim, ANA, "circulo abrir", "navi")
    with get_connection() as c:
        c.execute("UPDATE agents SET location='STATION' WHERE id=?", (ANA,))
    joined = sh(sim, ANA, f"circulo unirse {code}", "RELAY_STATION")
    with get_connection() as c:
        p, g = c.execute("SELECT p, g FROM duo_links WHERE code=?", (code,)).fetchone()
        a = c.execute("SELECT secret FROM duo_members WHERE player_id=?", (PLAYER,)).fetchone()[0]
    (b,) = numbers(joined, "b")
    sh(sim, PLAYER, f"circulo publicar {pow(g, a, p)}", "RELAY_SCHOOL")
    sh(sim, ANA, f"circulo publicar {pow(g, b, p)}", "RELAY_STATION")
    key = pow(g, a * b, p)
    sh(sim, PLAYER, f"circulo enlazar {key}", "RELAY_SCHOOL")
    later = duo.time.time() + duo.WINDOW + 60
    monkeypatch.setattr(duo.time, "time", lambda: later)
    assert "Falta la otra persona" in sh(sim, ANA, f"circulo enlazar {key}", "RELAY_STATION"), "too late: wait again"
    assert "ABIERTO" in sh(sim, PLAYER, f"circulo enlazar {key}", "RELAY_SCHOOL")
    assert "Sales del círculo" not in sh(sim, PLAYER, "circulo salir", "RELAY_SCHOOL")


def test_leaving_and_the_manual(two):
    sim = two
    code = re.search(r"(C-\d+)", sh(sim, PLAYER, "circulo abrir", "RELAY_SCHOOL")).group(1)
    assert "Ya estás en un círculo" in sh(sim, PLAYER, "circulo abrir", "RELAY_SCHOOL")
    assert f"Sales del círculo {code}" in sh(sim, PLAYER, "circulo salir", "RELAY_SCHOOL")
    assert "Ningún círculo espera" in sh(sim, ANA, "circulo lista", "RELAY_STATION")
    assert "(g^b)^a = (g^a)^b" in sh(sim, PLAYER, "man dh", "RELAY_SCHOOL")
    assert "circulo abrir · circulo lista" in sh(sim, PLAYER, "circulo Ayuda", "RELAY_SCHOOL"), "unknown subcommands get the help"
    assert "circulo abrir" in sh(sim, PLAYER, "help", "RELAY_SCHOOL")
    assert "Usage" not in sh(sim, PLAYER, "powmod 2 10 1000", "RELAY_SCHOOL")
    assert sh(sim, PLAYER, "powmod 2 10 1000", "RELAY_SCHOOL").endswith("= 24")
    move(sim, "APARTMENT")
    assert "ryoko" in sh(sim, PLAYER, "cat ~/correo/circulos.eml", "navi")


def test_the_circle_in_english(two):
    sim = two
    token = i18n.set_language("en")
    try:
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay|desde|círculo)\b", re.I)
        opened = sh(sim, PLAYER, "circle open", "RELAY_SCHOOL")
        code = re.search(r"(C-\d+)", opened).group(1)
        texts = [opened, sh(sim, ANA, "circle list", "RELAY_STATION"), sh(sim, ANA, f"circle join {code}", "RELAY_STATION"),
                 sh(sim, PLAYER, "circle show", "RELAY_SCHOOL"), sh(sim, PLAYER, "circle publish 1", "RELAY_SCHOOL"),
                 sh(sim, PLAYER, "man dh", "RELAY_SCHOOL"), sh(sim, PLAYER, "man circle", "RELAY_SCHOOL"),
                 sh(sim, PLAYER, "cat /var/circulos/LEEME", "RELAY_SCHOOL")]
        for text in texts:
            lines = [line for line in text.splitlines() if spanish.search(line)]
            assert not lines, lines[:3]
    finally:
        i18n.reset(token)
