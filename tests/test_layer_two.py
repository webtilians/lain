"""Capa 02 · Enlace: MAC learning, frame check sequences and a duplicate address, from game output."""
import re

import pytest

from server.world_core import i18n, layer_two
from server.world_core.agent_context import AgentContextBuilder
from tests.test_chapter_one import move
from tests.test_layer_four import out
from tests.test_layer_one import CABINET, PLAYER, flags, game, physical, read_capture  # noqa: F401 (fixtures)

SWITCH = layer_two.SWITCH


@pytest.fixture
def link(monkeypatch, physical):
    monkeypatch.setenv("LAIN_LAYER_TWO", "1")
    layer_two.initialize_layer_two()
    assert layer_two.layer_snapshot(PLAYER) == {"active": False}
    read_capture(physical)
    assert "CAPA 01 COMPLETADA" in out(physical, "empalmar", host=CABINET)
    move(physical, "APARTMENT")
    return physical


def own_interface(sim):
    text = out(sim, "ip link")
    return re.search(r"link/ether (\S+)", text).group(1), int(re.search(r"seq (\d+)", text).group(1))


def ports(sim, address):
    """The two ports the switch log keeps moving the address between."""
    log = out(sim, "show log", host=SWITCH)
    assert address in log
    return sorted({int(port) for port in re.findall(r"(?:puerto|port) (\d+)", log)})


def intact_frames(sim, port):
    """Captured frames whose FCS matches the recomputed CRC-32."""
    frames = re.findall(r"^(\d+)  \S+  \S+  [0-9a-f]{8}  (.+)$", out(sim, f"capture {port}", host=SWITCH), re.M)
    kept = []
    for number, payload in frames:
        check = out(sim, f"fcs {port} {number}", host=SWITCH)
        carried, computed = re.findall(r"([0-9a-f]{8})$", check, re.M)
        if carried == computed:
            kept.append(payload)
    return frames, kept


def test_starts_after_capa_01_with_k_mail(link):
    sim = link
    snapshot = layer_two.layer_snapshot(PLAYER)
    assert snapshot["active"] and snapshot["fragments"] == 1 and "conmutador" in snapshot["goal"]
    assert "dos puertos" in out(sim, "cat ~/correo/direccion.eml")
    assert "andén" in out(sim, "show mac") and "multicast" in out(sim, "man mac") and "CRC-32" in out(sim, "man fcs")


def test_heartbeats_and_fcs_tell_the_ports_apart_then_shut_the_copy(link):
    sim = link
    address, last_beat = own_interface(sim)
    move(sim, "STATION")
    first, second = ports(sim, address)
    assert re.search(rf"{address}\s+\d+\s+41", out(sim, "show mac", host=SWITCH))
    assert "Antes de decidir" in out(sim, f"shutdown {first}", host=SWITCH)
    beats = {}
    for port in (first, second):
        frames, kept = intact_frames(sim, port)
        assert len(kept) == len(frames) - 1          # one damaged frame on each port
        beats[port] = [int(seq) for seq in re.findall(r"seq (\d+)", " ".join(kept))]
    mine = next(port for port in beats if last_beat in beats[port])
    copy = next(port for port in beats if port != mine)
    assert max(beats[copy]) < last_beat
    _, kept = intact_frames(sim, copy)
    assert any("kagami-04" in payload for payload in kept)
    assert "tu Navi" in out(sim, f"shutdown {mine}", host=SWITCH)
    ending = out(sim, f"shutdown {copy}", host=SWITCH)
    assert "CAPA 02 COMPLETADA" in ending and "réplica tuya" in ending
    assert layer_two.layer_snapshot(PLAYER)["decision"] == "SHUT" and layer_two.layer_snapshot(PLAYER)["fragments"] == 2
    k = AgentContextBuilder().build("AGENT_K")["chapter_memory"]["memories"]
    assert any("vuelve a estar estable" in memory["text"] for memory in k)


def test_a_new_address_must_be_unicast_and_locally_administered(link):
    sim = link
    address, _ = own_interface(sim)
    move(sim, "STATION")
    out(sim, f"capture {layer_two.story_for(PLAYER).replica_port}", host=SWITCH)
    move(sim, "APARTMENT")
    assert "no es una dirección MAC" in out(sim, "ip link set address 12:34")
    assert "ya es tu dirección" in out(sim, f"ip link set address {address}")
    assert "multicast" in out(sim, "ip link set address 03:00:00:00:00:01")
    assert "universal" in out(sim, "ip link set address 00:11:22:33:44:55")
    assert "dirección de fábrica" in out(sim, "ip link set address 02:11:22:33:44:55")
    assert layer_two.layer_snapshot(PLAYER)["decision"] == "RENAME"
    assert "Ya decidiste" in out(sim, "ip link set address 06:11:22:33:44:55")


def test_sharing_the_address_and_console_rules(link):
    sim = link
    assert "andén" in out(sim, "capture 3") and "Navi" not in out(sim, "ip link")
    move(sim, "STATION")
    assert "no es tu Navi" in out(sim, "ip link", host=SWITCH)
    assert "Uso" in out(sim, "capture 99", host=SWITCH) and "Uso" in out(sim, "show nada", host=SWITCH)
    assert "Uso" in out(sim, "fcs 3", host=SWITCH)
    story = layer_two.story_for(PLAYER)
    out(sim, f"capture {story.replica_port}", host=SWITCH)
    assert "misma persona en dos sitios" in out(sim, "compartir", host=SWITCH)


def test_each_player_gets_their_own_address_and_ports():
    stories = [layer_two.Story(f"PLAYER_{n:032x}", {"language": "es", "started": 3000}, "navi-x") for n in range(100)]
    assert len({s.mac for s in stories}) == 100 and len({(s.port, s.replica_port) for s in stories}) > 40
    for story in stories:
        assert story.port != story.replica_port and story.replica_seq < story.seq
        assert str(story.replica_seq)[1:] == str(story.seq)[1:]


def test_english_player_reads_the_layer_in_english(monkeypatch, physical):
    sim = physical
    monkeypatch.setenv("LAIN_LAYER_TWO", "1")
    layer_two.initialize_layer_two()
    token = i18n.set_language("en")
    try:
        read_capture(sim)
        assert "LAYER 01 COMPLETE" in out(sim, "splice", host=CABINET)
        move(sim, "APARTMENT")
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay|puerto|tramas)\b", re.I)
        story = layer_two.story_for(PLAYER)
        for command in ("help", "man mac", "man frame", "man fcs", "man switch", "cat ~/correo/direccion.eml",
                        "ip link", "show mac", "ip link set address 00:11:22:33:44:55"):
            lines = [line for line in out(sim, command).splitlines() if spanish.search(line)]
            assert not lines, (command, lines[:3])
        move(sim, "STATION")
        for command in ("show mac", "show log", "show x", f"capture {story.port}", "capture 99",
                        f"fcs {story.port} 1", "fcs 3", "shutdown 1", "ip link"):
            lines = [line for line in out(sim, command, host=SWITCH).splitlines() if spanish.search(line)]
            assert not lines, (command, lines[:3])
        snapshot = i18n.payload(layer_two.layer_snapshot(PLAYER))
        assert not spanish.search(snapshot["goal"] + snapshot["mail"]["body"] + snapshot["title"] + snapshot["mail"]["subject"])
    finally:
        i18n.reset(token)
