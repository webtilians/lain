"""Capa 01 · Física: Manchester, oversampling and polarity, from the oscilloscope's output only."""
import re

import pytest

from server.world_core import i18n, layer_one, layer_three
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.player_view import build_player_snapshot
from tests.test_chapter_one import move
from tests.test_layer_four import connected, layer_three_game, out  # noqa: F401 (fixtures)
from tests.test_layer_three import PLAYER, game  # noqa: F401 (fixture)

CABINET = layer_one.CABINET


@pytest.fixture
def flags(monkeypatch):
    monkeypatch.setenv("LAIN_LAYER_ONE", "1")


@pytest.fixture
def physical(flags, game):
    """A new player: Capa 01 opens with the Wired connection, beside Capa 03."""
    move(game, "SCHOOL_LAB")
    return game


def read_capture(sim):
    """What a player works out from the scope: the busy pair, samples per half-bit and convention."""
    busy, rate = None, None
    for pair in ("naranja", "verde"):
        screen = out(sim, f"scope {pair}", host=CABINET)
        rate = int(re.search(r"(\d+) MS/s", screen).group(1))
        if screen.count("¯") > 40:
            busy = pair
    samples = rate // 20          # 10 Mbit/s Manchester is 20 Mbaud
    reply = out(sim, f"decode {busy} {samples} ieee", host=CABINET)
    convention = "ieee"
    if "no encontrados" in reply or "not found" in reply:
        convention = "thomas"
        reply = out(sim, f"decode {busy} {samples} thomas", host=CABINET)
    return busy, samples, convention, reply


def test_opens_with_the_wired_connection_beside_capa_03(physical):
    sim = physical
    snapshot = layer_one.layer_snapshot(PLAYER)
    assert snapshot["active"] and snapshot["fragments"] == 0 and "osciloscopio" in snapshot["goal"]
    assert layer_three.layer_snapshot(PLAYER)["active"]
    assert build_player_snapshot(PLAYER)["current_layer"] == "layer_one"
    assert "decode" in out(sim, "cat /var/log/phy/LEEME", host=CABINET)
    assert "G. E. Thomas" in out(sim, "man manchester", host=CABINET) and "0xD5" in out(sim, "man preamble", host=CABINET)
    move(sim, "APARTMENT")
    assert "pabellón B" in out(sim, "cat ~/correo/cable.eml") and "aula de informática" in out(sim, "scope naranja")


def test_reading_the_frame_then_splicing_the_cable(physical):
    sim = physical
    busy, samples, convention, reply = read_capture(sim)
    assert "55 55 55 55 55 55 55 d5" in reply and "Este cable lo corté yo" in reply
    wrong = 5 if samples == 3 else 3
    assert "Manchester" in out(sim, f"decode {busy} {wrong} {convention}", host=CABINET)
    assert "Antes de tocar" not in out(sim, "empalmar", host=CABINET)
    assert layer_one.layer_snapshot(PLAYER)["decision"] == "SPLICE"
    assert layer_one.layer_snapshot(PLAYER)["fragments"] == 1
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("empalmó el cable" in memory["text"] for memory in nora)


def test_decisions_need_the_decoded_frame_and_happen_once(physical):
    sim = physical
    busy = layer_one.story_for(PLAYER).pair
    idle = "verde" if busy == "naranja" else "naranja"
    assert "Antes de tocar" in out(sim, "dejar", host=CABINET)
    assert "no encontrados" in out(sim, f"decode {idle} 1 ieee", host=CABINET) or "Manchester" in out(sim, f"decode {idle} 1 ieee", host=CABINET)
    assert "Uso" in out(sim, "decode naranja tres ieee", host=CABINET) and "Uso" in out(sim, "scope azul", host=CABINET)
    read_capture(sim)
    ending = out(sim, "puentear", host=CABINET)
    assert "CAPA 01 COMPLETADA" in ending and "eres el medio" in ending
    assert "Ya decidiste" in out(sim, "dejar", host=CABINET)


def test_earlier_players_get_it_as_an_open_layer_and_fragments_count_layers(monkeypatch, connected):
    monkeypatch.setenv("LAIN_LAYER_ONE", "1")
    layer_one.initialize_layer_one()
    assert layer_one.layer_snapshot(PLAYER)["active"]
    assert layer_three.layer_snapshot(PLAYER)["fragments"] == 1
    assert build_player_snapshot(PLAYER)["current_layer"] == "layer_four"
    move(connected, "SCHOOL_LAB")
    read_capture(connected)
    out(connected, "dejar", host=CABINET)
    assert layer_three.layer_snapshot(PLAYER)["fragments"] == 2


def test_each_player_gets_their_own_capture():
    stories = [layer_one.Story(f"PLAYER_{n:032x}", {"language": "es"}) for n in range(100)]
    assert {s.pair for s in stories} == {"naranja", "verde"} and {s.inverted for s in stories} == {True, False}
    assert {s.samples for s in stories} == {3, 5}
    for story in stories:
        data = story.capture[story.pair]
        halves = [int(sum(data[i:i + story.samples]) * 2 > story.samples) for i in range(0, len(data), story.samples)]
        assert all(a != b for a, b in zip(halves[0::2], halves[1::2]))   # the noise never wins a vote


def test_english_player_reads_the_layer_in_english(physical):
    sim = physical
    token = i18n.set_language("en")
    try:
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay|muestras)\b", re.I)
        busy = layer_one.story_for(PLAYER).pair
        for command in ("help", "man signal", "man manchester", "man noise", "man preamble", "man cable",
                        "cat /var/log/phy/LEEME", "scope naranja", "scope verde 120", "decode verde 1 ieee",
                        f"decode {busy} 2 ieee", "decode azul 3 ieee", "dejar"):
            text = out(sim, command, host=CABINET)
            lines = [line for line in text.splitlines() if spanish.search(line)]
            assert not lines, (command, lines[:3])
        move(sim, "APARTMENT")
        for command in ("cat ~/correo/cable.eml", "scope naranja"):
            lines = [line for line in out(sim, command).splitlines() if spanish.search(line)]
            assert not lines, (command, lines[:3])
        snapshot = i18n.payload(layer_one.layer_snapshot(PLAYER))
        assert not spanish.search(snapshot["goal"] + snapshot["mail"]["body"] + snapshot["title"] + snapshot["mail"]["subject"])
    finally:
        i18n.reset(token)
