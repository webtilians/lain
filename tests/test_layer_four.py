"""Capa 04 · Transporte: solvable with real TCP knowledge from in-game output only."""
import re

import pytest

from server.world_core import i18n, layer_four, layer_three
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection
from tests.test_chapter_one import move
from tests.test_layer_three import PLAYER, game as layer_three_game  # noqa: F401 (fixture)


@pytest.fixture
def connected(monkeypatch, layer_three_game):
    monkeypatch.setenv("LAIN_LAYER_FOUR", "1")
    layer_four.initialize_layer_four()
    sim = layer_three_game
    packet = layer_three.layer_snapshot(PLAYER)["packet"]
    with get_connection() as c:
        c.execute("UPDATE layer_three SET assembled=1, exposed=1 WHERE player_id=?", (PLAYER,))
    assert layer_four.layer_snapshot(PLAYER) == {"active": False}
    assert "CAPA 03 COMPLETADA" in out(sim, f"reenviar {packet}")
    return sim


def out(sim, command, host="navi", cwd="/"):
    return layer_three.run_shell(PLAYER, host, cwd, command, sim.minute)["output"]


def handshake(sim):
    dump = out(sim, "tcpdump")
    isn = int(re.search(r"Flags \[S\], seq (\d+)", dump).group(1))
    assert "SYN_RECV" in out(sim, "netstat")
    assert "RST" in out(sim, f"send nodo07 SYN+ACK seq=777 ack={isn}")
    assert "ESTABLISHED" in out(sim, f"send nodo07 SYN+ACK seq=5000 ack={isn + 1}")
    return isn


def received(dump):
    """(start, end) of every data segment in a capture, and the TTL they carried."""
    segments = [(int(a), int(b)) for a, b in re.findall(r"seq (\d+):(\d+)", dump)]
    ttl = int(re.search(r"Flags \[P\.\].*ttl (\d+)", dump).group(1))
    return sorted(set(segments)), ttl


def first_gap(isn, segments):
    expected = isn + 1
    for start, end in segments:
        if start != expected:
            return expected
        expected = end
    return None


def test_starts_when_capa_03_is_decided_and_mail_arrives(connected):
    snapshot = layer_four.layer_snapshot(PLAYER)
    assert snapshot["active"] and snapshot["fragments"] == 1 and "4004" in snapshot["goal"]
    assert "SYN" in out(connected, "cat ~/correo/syn.eml")
    assert "tcpdump" in out(connected, "help") and "SYN+ACK" in out(connected, "man tcp")
    assert "RFC 5681" in out(connected, "man retransmission")


def test_full_layer_with_real_tcp_reasoning(connected):
    sim = connected
    isn = handshake(sim)
    segments, ttl = received(out(sim, "tcpdump"))
    assert len(segments) == 5
    gap = first_gap(isn, segments)
    end = max(b for _a, b in segments)
    assert "1/3" in out(sim, f"send nodo07 ACK ack={gap}")
    assert "2/3" in out(sim, f"send nodo07 ACK ack={gap}")
    assert "retransmisión rápida" in out(sim, f"send nodo07 ACK ack={gap}")
    segments, _ = received(out(sim, "tcpdump"))
    assert first_gap(isn, segments) is None
    assert "Flujo completo" in out(sim, f"send nodo07 ACK ack={end}")
    stream = out(sim, "cat ~/flujo-4004.txt")
    assert "Sesión Cero" in stream and "TTL" in stream and "[…]" not in stream

    hops = layer_four.INITIAL_TTL - ttl
    neighbours = {line.split()[0]: int(line.split()[1]) for line in out(sim, "cat /net/vecinos").splitlines()
                  if not line.startswith("#")}
    host = next(name for name, distance in neighbours.items() if distance == hops)
    relay = next(r for r, (h, _p, _l) in layer_three.RELAYS.items() if h == host)
    other = next(r for r in layer_three.RELAYS if r != relay)
    move(sim, layer_three.RELAYS[other][1])
    assert "nora-pda" not in out(sim, "tcpdump", host=other)
    assert "ninguna conexión" in out(sim, "keepalive nodo07", host=other)

    move(sim, layer_three.RELAYS[relay][1])
    capture = out(sim, "tcpdump", host=relay)
    assert "nora-pda" in capture and "keepalive" in capture
    seq, ack = map(int, re.search(r"\(keepalive\)", capture) and re.search(r"seq (\d+), ack (\d+)", capture).groups())
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("Sesión Cero" in memory["text"] for memory in nora)
    # Keepalive probes carry SND.NXT - 1: the real next byte is seq + 1.
    assert "descarta" in out(sim, f"send nodo07 FIN+ACK seq={seq} ack={ack}", host=relay)
    reply = out(sim, f"send nodo07 FIN+ACK seq={seq + 1} ack={ack}", host=relay)
    fin = int(re.search(r"Flags \[F\.\], seq (\d+), ack (\d+)", reply).group(1))
    assert "no confirma" in out(sim, f"send nodo07 ACK seq={seq + 2} ack={fin}", host=relay)
    ending = out(sim, f"send nodo07 ACK seq={seq + 2} ack={fin + 1}", host=relay)
    assert "CAPA 04 COMPLETADA" in ending and "TIME_WAIT" in ending
    snapshot = layer_four.layer_snapshot(PLAYER)
    assert snapshot["decision"] == "FIN" and snapshot["fragments"] == 2
    k_memory = AgentContextBuilder().build("AGENT_K")["chapter_memory"]["memories"]
    assert any("limpiamente" in memory["text"] for memory in k_memory)


def test_confirming_missing_bytes_loses_those_words_forever(connected):
    sim = connected
    isn = handshake(sim)
    segments, _ = received(out(sim, "tcpdump"))
    end = max(b for _a, b in segments)
    assert "se han perdido" in out(sim, f"send nodo07 ACK ack={end}")
    assert "[…]" in out(sim, "cat ~/flujo-4004.txt")
    assert "Pasa el tiempo" in out(sim, "wait")
    assert "Ya confirmaste" in out(sim, f"send nodo07 ACK ack={first_gap(isn, segments)}")


def test_timeout_also_retransmits_and_reset_needs_the_exact_sequence(connected):
    sim = connected
    isn = handshake(sim)
    segments, ttl = received(out(sim, "tcpdump"))
    gap, end = first_gap(isn, segments), max(b for _a, b in segments)
    out(sim, f"send nodo07 ACK ack={gap}")
    assert "RTO" in out(sim, "wait")
    assert "Flujo completo" in out(sim, f"send nodo07 ACK ack={end}")
    story = layer_four.story_for(PLAYER)
    move(sim, layer_three.RELAYS[story.nora_relay][1])
    out(sim, "tcpdump", host=story.nora_relay)
    assert "ignora el RST" in out(sim, f"send nodo07 RST seq={story.ka_seq - 1}", host=story.nora_relay)
    assert "CAPA 04 COMPLETADA" in out(sim, f"send nodo07 RST seq={story.ka_seq}", host=story.nora_relay)
    assert layer_four.layer_snapshot(PLAYER)["decision"] == "RST"
    assert "Ya decidiste" in out(sim, "keepalive nodo07", host=story.nora_relay)


def test_taking_over_the_keepalives(connected):
    sim = connected
    isn = handshake(sim)
    segments, _ = received(out(sim, "tcpdump"))
    gap, end = first_gap(isn, segments), max(b for _a, b in segments)
    for _ in range(3):
        out(sim, f"send nodo07 ACK ack={gap}")
    out(sim, f"send nodo07 ACK ack={end}")
    story = layer_four.story_for(PLAYER)
    move(sim, layer_three.RELAYS[story.nora_relay][1])
    assert "Termina" not in out(sim, "tcpdump", host=story.nora_relay)
    assert "Tú ya no" in out(sim, "keepalive nodo07", host=story.nora_relay)
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("Ya no la sostengo sola" in memory["text"] for memory in nora)


def test_each_player_gets_a_different_connection():
    stories = [layer_four.Story(f"PLAYER_{n:032x}", {"language": "es"}, "navi-x") for n in range(150)]
    assert len({story.isn_r for story in stories}) == 150
    assert {story.nora_relay for story in stories} == set(layer_three.RELAYS)
    for story in stories:
        assert 0 < story.lost < len(story.segments) - 1
        assert b"".join(s["data"] for s in story.segments).decode() == layer_four.MESSAGE
        assert sorted(story.distances.values()) == [2, 3, 4] and story.distances[story.nora_relay] == 2


def test_english_player_reads_the_layer_in_english(connected):
    token = i18n.set_language("en")
    try:
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay)\b", re.I)
        for command in ("help", "man tcp", "man ack", "man retransmission", "man keepalive", "man fin", "man rst",
                        "man tcpdump", "cat ~/correo/syn.eml", "netstat", "tcpdump", "send nodo07 ACK ack=1",
                        "send nodo07 SYN", "wait"):
            lines = [line for line in out(connected, command).splitlines() if spanish.search(line)]
            assert not lines, (command, lines[:3])
        snapshot = i18n.payload(layer_four.layer_snapshot(PLAYER))
        assert not spanish.search(snapshot["goal"] + snapshot["mail"]["body"] + snapshot["title"])
    finally:
        i18n.reset(token)
