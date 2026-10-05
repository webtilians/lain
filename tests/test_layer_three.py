"""Capa 03 · TTL: solvable from in-game information only, per player, server-owned."""
import hashlib

import pytest

from server.world_core import layer_three as layer
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.network_conflict import perform_network_action
from server.world_core.prologue import submit_terminal_command, talk_to_prologue_npc
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement
from tests.test_chapter_one import move

PLAYER = "PLAYER_1"


@pytest.fixture
def game(monkeypatch):
    for flag in ("LAIN_LAYER_THREE", "LAIN_PROLOGUE_ENABLED", "LAIN_CITY_RESIDENTS_ENABLED", "LAIN_CORPORATION"):
        monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    sim = Simulation()
    assert layer.layer_snapshot(PLAYER) == {"active": False}
    move(sim, "SCHOOL_LAB")
    talk_to_prologue_npc(PLAYER, "PROFESSOR", sim.minute, "ASK_STUDENT")
    move(sim, "NIGHTCLUB")
    talk_to_prologue_npc(PLAYER, "RYOKO", sim.minute, "ASK_ADDRESS")
    move(sim, "APARTMENT")
    assert submit_terminal_command(PLAYER, "telnet wired 23", sim.minute)["accepted"]
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001", PLAYER, sim.minute)
    return sim


def sh(sim, command, host="navi", cwd="/"):
    return layer.run_shell(PLAYER, host, cwd, command, sim.minute)


def out(sim, command, host="navi", cwd="/"):
    return sh(sim, command, host, cwd)["output"]


def h8(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def solve_route(sim):
    """What a player does with /net/rutas, /net/hosts and `man ttl`."""
    snapshot = layer.layer_snapshot(PLAYER)
    destination = snapshot["hostname"]
    table = {}
    for line in out(sim, "cat /net/rutas").splitlines():
        if line.startswith("#"):
            continue
        dest, router, nxt, queue, _unit, norm = line.split()
        if dest == destination:
            table[router] = (nxt, int(queue), norm)
    ttl, router = layer.INITIAL_TTL, table["nodo07"][0]   # the sender is not a hop
    while True:
        nxt, queue, norm = table[router]
        ttl -= max(1, queue) if norm == "rfc791" else 1
        if ttl <= 0:
            break
        router = nxt
    places = {line.split()[0]: line for line in out(sim, "cat /net/hosts").splitlines() if not line.startswith("#")}
    assert "consola física" in places[router]
    return next(relay for relay, (host, _place, _label) in layer.RELAYS.items() if host == router)


def test_connection_starts_the_layer_with_mail_and_goal(game):
    snapshot = layer.layer_snapshot(PLAYER)
    assert snapshot["active"] and snapshot["fragments"] == 0
    assert snapshot["packet"] in snapshot["goal"]
    mail = out(game, "cat ~/correo/ttl1.eml")
    assert "TTL=1" in mail and snapshot["packet"] in mail
    trace = out(game, f"traceroute {snapshot['packet']}")
    assert "* * *" in trace and "ttl restante" in trace
    assert "RFC 791" in out(game, "man ttl")


def test_terminals_need_the_player_beside_them(game):
    move(game, "STATION")
    with pytest.raises(ValueError, match="TERMINAL_NOT_PRESENT"):
        sh(game, "help")
    with pytest.raises(ValueError, match="CONSOLE_NOT_PRESENT"):
        sh(game, "ls", host="RELAY_VIDEO")
    assert "ls" in out(game, "help", host="RELAY_STATION")
    with pytest.raises(ValueError, match="UNKNOWN_HOST"):
        sh(game, "help", host="../etc")


def test_virtual_file_system_cannot_escape(game):
    assert "no existe" in out(game, "cat ../../../../etc/passwd")
    assert "CASA" in out(game, "cat /etc/motd", cwd="/home")
    assert sh(game, "cd ~")["cwd"].startswith("/home/")
    assert "orden desconocida" in out(game, "rm -rf /")
    assert out(game, "cat 'sin cerrar") == "Comillas sin cerrar."


def test_full_layer_is_solvable_from_in_game_information(game):
    packet = layer.layer_snapshot(PLAYER)["packet"]
    drop = solve_route(game)
    wrong = next(relay for relay in layer.RELAYS if relay != drop)
    move(game, layer.RELAYS[wrong][1])
    assert packet not in out(game, "ls /var/spool/descartes", host=wrong)
    assert packet not in out(game, "cat /var/log/icmp", host=wrong)

    move(game, layer.RELAYS[drop][1])
    menu = perform_network_action(PLAYER, "OPEN", drop, "", "open_" + drop.lower() + "_0001")
    assert any(choice["action"] == "CONSOLE" for choice in menu["choices"])
    assert "descartado aquí" in out(game, "cat /var/log/icmp", host=drop)
    index = out(game, f"cat /var/spool/descartes/{packet}.idx", host=drop).splitlines()[2:]
    declared = {sha: (int(seq), int(length)) for seq, length, sha in (row.split() for row in index)}
    files = [name for name in out(game, "ls /var/spool/descartes", host=drop).split() if name.startswith(packet + "-")]
    by_seq = {}
    for name in files:
        digest = out(game, f"sha256 /var/spool/descartes/{name}", host=drop).split()[0]
        if digest in declared:
            by_seq.setdefault(declared[digest][0], name)
    ordered = [by_seq[seq] for seq in sorted(by_seq)]
    assert len(ordered) == 5 and len(files) == 7   # one retransmission, one forgery
    wrong_order = " ".join(reversed(ordered))
    assert "esperaba seq 1000" in out(game, f"ensamblar {packet} {wrong_order}", host=drop, cwd="/var/spool/descartes")
    forged = next(name for name in files if out(game, f"sha256 /var/spool/descartes/{name}", host=drop).split()[0] not in declared)
    attempt = ordered[:]
    attempt[0] = forged
    assert "no coincide" in out(game, f"ensamblar {packet} {' '.join(attempt)}", host=drop, cwd="/var/spool/descartes")
    done = sh(game, f"ensamblar {packet} {' '.join(ordered)}", host=drop, cwd="/var/spool/descartes")
    assert done["changed"] and "Sesión Cero" in done["output"]

    move(game, "APARTMENT")
    assert "NODO_07" in out(game, "cat ~/sesion0.txt")
    lines = out(game, "cat /var/log/malla/diario").splitlines()
    breaks = [n for n in range(1, len(lines)) if lines[n].split(" | ")[2] != "prev " + h8(lines[n - 1])]
    assert len(breaks) == 1
    forged_entry = breaks[0]   # 0-based index of the entry after the break == 1-based number of the forged one
    assert h8(lines[forged_entry - 1]) == out(game, f"sha256 /var/log/malla/diario {forged_entry}").split()[0]
    assert "infundada" in out(game, f"denunciar {forged_entry + 1}")
    assert "no existe" in out(game, "cat /mnt/kagami/diario.espejo")
    assert "aceptada" in out(game, f"denunciar {forged_entry}")
    mirror = out(game, "cat /mnt/kagami/diario.espejo")
    assert "terminada por NOEMA" in mirror and "cerrada por su usuario" in out(game, "cat /var/log/malla/diario")
    assert "terminada" in out(game, "last")

    ending = out(game, f"reenviar {packet}")
    assert "CAPA 03 COMPLETADA" in ending
    assert "Ya decidiste" in out(game, f"soltar {packet}")
    snapshot = layer.layer_snapshot(PLAYER)
    assert snapshot["decision"] == "FORWARD" and snapshot["fragments"] == 1
    memories = AgentContextBuilder().build("AGENT_K")["chapter_memory"]["memories"]
    assert any("Sesión Cero" in memory["text"] for memory in memories)


def test_decisions_wait_for_the_truth_and_drop_tells_nobody(game):
    packet = layer.layer_snapshot(PLAYER)["packet"]
    assert "Todavía no sabes" in out(game, f"soltar {packet}")
    from server.world_core.database import get_connection
    with get_connection() as c:
        c.execute("UPDATE layer_three SET assembled=1, exposed=1 WHERE player_id=?", (PLAYER,))
    assert "Nadie más lo leerá" in out(game, f"soltar {packet}")
    assert layer.layer_actor_context("AGENT_NORA", PLAYER) == []


def test_three_unfounded_reports_seal_the_diary(game):
    lines = out(game, "cat /var/log/malla/diario").splitlines()
    forged = next(n for n in range(1, len(lines)) if lines[n].split(" | ")[2] != "prev " + h8(lines[n - 1]))
    for attempt in (1, 2):
        assert "tomado nota" in out(game, "denunciar 1")
    assert "sella el diario" in out(game, "denunciar 1")
    assert "ha sellado" in out(game, f"denunciar {forged}")
    game.minute += layer.LOCK_MINUTES
    assert "aceptada" in out(game, f"denunciar {forged}")


def test_puzzles_differ_between_players_and_always_end_at_hop_seven():
    stories = [layer.Story(f"PLAYER_{n:032x}", "Ana", {"connection": 300, "started": 700}) for n in range(200)]
    assert len({story.packet for story in stories}) > 150
    assert {story.drop for story in stories} == set(layer.RELAYS)
    assert len({story.forged_number for story in stories}) == 4
    for story in stories:
        assert story.ttl_after[6] == 0 and story.ttl_after[5] == 1
        joined = "".join(segment["payload"] for segment in story.segments)
        assert joined == layer.MESSAGE


def test_shell_api_returns_state_only_after_a_change(game, monkeypatch):
    from fastapi.testclient import TestClient
    from server.api import app

    with TestClient(app) as client:
        reply = client.post("/api/v1/layer-three/shell", json={"host": "navi", "cwd": "/", "command": "whoami"})
        assert reply.status_code == 200
        assert reply.json()["state"] is None and "sesión 1" in reply.json()["result"]["output"]
        bad = client.post("/api/v1/layer-three/shell", json={"host": "RELAY_VIDEO", "command": "ls"})
        assert bad.status_code == 409 and bad.json()["detail"] == "CONSOLE_NOT_PRESENT"
