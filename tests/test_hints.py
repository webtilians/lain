"""Hints: three levels per step, reset on each new step, and level 3 really solves the step."""
import re

import pytest

from server.world_core import hints, i18n, layer_four, layer_one
from server.world_core.agent_context import AgentContextBuilder
from tests.test_layer_five import archive, plan, states  # noqa: F401 (fixture)
from tests.test_layer_four import PLAYER, connected, layer_three_game, out  # noqa: F401 (fixtures)
from tests.test_layer_one import CABINET, flags, game, physical  # noqa: F401 (fixtures)
from tests.test_layer_seven import node  # noqa: F401 (fixture)
from tests.test_layer_six import VIDEO, club  # noqa: F401 (fixture)

STATION = "RELAY_STATION"


@pytest.fixture(autouse=True)
def hints_on(monkeypatch):
    monkeypatch.setenv("LAIN_HINTS", "1")


def ask(sim, extra="", host="navi"):
    hints.initialize_hints()
    return out(sim, ("pista " + extra).strip(), host=host)


def solution(text):
    """The command a level-3 hint tells the player to type."""
    return re.search(r"(?:Escribe|Type) (.+?)(?:\.$| y | and |$)", text.splitlines()[1]).group(1)


def test_levels_climb_reset_on_a_new_step_and_nora_remembers(physical):
    sim = physical
    first = ask(sim, host=CABINET)
    assert first.startswith("PISTA 1/3 · Capa 01 · Física") and "scope naranja" in first and "otra vez" in first
    second = ask(sim, host=CABINET)
    assert second.startswith("PISTA 2/3") and "entre 20" in second
    story = layer_one.story_for(PLAYER)
    third = ask(sim, host=CABINET)
    assert third.startswith("PISTA 3/3") and f"decode {story.pair} {story.samples} {story.convention}" in third
    assert "otra vez" not in third and ask(sim, host=CABINET).startswith("PISTA 3/3")
    assert "preámbulo y SFD encontrados" in out(sim, solution(third), host=CABINET)
    decide = ask(sim, host=CABINET)
    assert decide.startswith("PISTA 1/3") and "qué haces con el cable" in decide
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("me pidió ayuda con la Capa 01" in memory["text"] for memory in nora)


def test_choosing_a_layer_and_layers_not_reached_or_done(physical):
    sim = physical
    assert "traceroute" in ask(sim, "3", host=CABINET)
    assert "Todavía no has llegado a la Capa 05" in ask(sim, "5", host=CABINET)
    for _ in range(3):
        level3 = ask(sim, "1", host=CABINET)
    out(sim, solution(level3), host=CABINET)
    out(sim, "dejar", host=CABINET)
    assert "ya está completada" in ask(sim, "1", host=CABINET)


def test_level_three_answers_the_tcp_handshake(connected):
    sim = connected
    for _ in range(3):
        text = ask(sim)
    story = layer_four.story_for(PLAYER)
    assert f"ack={story.isn_r + 1}" in text
    assert "ESTABLISHED" in out(sim, solution(text))
    following = ask(sim)
    assert following.startswith("PISTA 1/3 · Capa 04") and "tcpdump" in following


def test_level_three_merge_plan_commits(archive):
    sim = archive
    for _ in range(3):
        text = ask(sim, host=STATION)
    commit = re.search(r"commit version=\d+ token=\d+", text).group(0)
    loaded = states(sim)
    choices, _ = plan(loaded["base"], loaded["s0"], loaded["s1"])
    for field, side in choices.items():
        out(sim, f"merge {field} {side}", host=STATION)
    assert "Fusión confirmada" in out(sim, commit, host=STATION)
    assert "qué sesión conserva la cuenta" in ask(sim, host=STATION)


def test_level_three_unmasks_session_zero(club):
    sim, word = club
    for _ in range(3):
        text = ask(sim, host=VIDEO)
    assert word in text
    xor, hmac = re.findall(r"(?:xor|hmac) /var/spool/caras/\w\.pkt [^\s.]+", text)
    assert out(sim, xor, host=VIDEO).startswith("Has vuelto.")
    out(sim, hmac, host=VIDEO)
    assert "qué haces con su último paquete" in ask(sim, host=VIDEO)


def test_level_three_reaches_node_07(node):
    sim, word, name = node
    for _ in range(3):
        text = ask(sim)
    assert "s0-" in out(sim, solution(text))
    assert "cómo termina tu historia" in ask(sim)
    assert "PUT" in ask(sim)


def test_hints_in_english(physical):
    sim = physical
    token = i18n.set_language("en")
    try:
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay|escribe|otra)\b", re.I)
        texts = [ask(sim, extra, host=CABINET) for extra in ("", "", "", "3", "3", "3", "5")]
        texts += [out(sim, "help", host=CABINET), out(sim, "man hint", host=CABINET)]
        for text in texts:
            lines = [line for line in text.splitlines() if spanish.search(line)]
            assert not lines, lines[:3]
    finally:
        i18n.reset(token)
