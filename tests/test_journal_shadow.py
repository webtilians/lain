"""Bible section 7: the unreliable diary (hash chain) and the shadow that walks while you are away."""
import re
import time

import pytest

from server.world_core import i18n, journal, online
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.layer_three import h8
from server.world_core.player_view import build_player_snapshot
from tests.test_layer_five import archive  # noqa: F401 (fixture)
from tests.test_layer_four import PLAYER, connected, layer_three_game, out  # noqa: F401 (fixtures)
from tests.test_layer_six import club  # noqa: F401 (fixture)
from tests.test_online_world import place, presence, world  # noqa: F401 (fixture)


@pytest.fixture
def diary(monkeypatch, club):
    """Capas 03, 04 and 05 decided: three entries, enough for NOEMA's first rewrite."""
    monkeypatch.setenv("LAIN_JOURNAL", "1")
    journal.initialize_journal()
    sim, _word = club
    from tests.test_chapter_one import move
    move(sim, "APARTMENT")
    return sim


def entries(text):
    return [line for line in text.splitlines() if re.match(r"^\d{4} \| ", line)]


def broken_entry(text):
    """The entry whose hash no longer matches the prev stored by the next one (or the head)."""
    lines = entries(text)
    head = re.search(r"# (?:cabeza|head) ([0-9a-f]{8})", text).group(1)
    stored = [re.search(r"prev ([0-9a-f]{8})", line).group(1) for line in lines[1:]] + [head]
    return next(number for number, (line, prev) in enumerate(zip(lines, stored), start=1) if h8(line) != prev)


def test_noema_rewrites_an_entry_and_the_chain_proves_it(diary):
    sim = diary
    text = out(sim, "cat ~/diario")
    assert len(entries(text)) == 3 and "NOEMA corrige" in out(sim, "cat ~/correo/diario.eml")
    number = broken_entry(text)
    shown = build_player_snapshot(PLAYER)["diary"]
    assert len(shown) == 3 and shown[number - 1]["text"] in journal.NOEMA.values()
    fine = next(n for n in (1, 2, 3) if n != number)
    assert "la escribiste tú" in out(sim, f"restaurar {fine}")
    line = entries(text)[number - 1]
    assert out(sim, f"sha256 ~/diario {text.splitlines().index(line) + 1}").startswith(h8(line))
    restored = out(sim, f"restaurar {number}")
    assert "restaurada" in restored
    text = out(sim, "cat ~/diario")
    with pytest.raises(StopIteration):
        broken_entry(text)
    assert all(entry["text"] not in journal.NOEMA.values()
               for entry in build_player_snapshot(PLAYER)["diary"])
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("reescrito el diario" in memory["text"] for memory in nora)


def test_diary_rules(diary):
    sim = diary
    assert "Uso" in out(sim, "restaurar") and "no tiene una entrada 9" in out(sim, "restaurar 9")
    assert "cadena de hashes" in out(sim, "man diario") and "restaurar" in out(sim, "help")


def test_waves_target_older_entries_and_restorations_stick():
    found = [(f"layer_{n}", n, "x") for n in range(7)]
    for player in (f"PLAYER_{n}" for n in range(50)):
        bad = journal.rewritten(player, found, set())
        assert 1 <= len(bad) <= 3 and "layer_6" not in bad
        assert journal.rewritten(player, found, bad) == set()
    assert journal.rewritten("PLAYER_1", found[:2], set()) == set()


def test_english_diary(diary):
    sim = diary
    token = i18n.set_language("en")
    try:
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay|minuto)\b", re.I)
        for command in ("cat ~/diario", "cat ~/correo/diario.eml", "man diario", "restaurar", "restaurar 9", "help"):
            lines = [line for line in out(sim, command).splitlines()
                     if spanish.search(line) and not line.startswith(("Capa", "Layer"))]
            assert not lines, (command, lines[:3])
        shown = i18n.payload(build_player_snapshot(PLAYER))["diary"]
        assert not any(spanish.search(entry["text"]) for entry in shown)
    finally:
        i18n.reset(token)


def test_an_offline_players_shadow_walks_their_route(world, monkeypatch):
    client, runtime, alice, bob, headers = world
    monkeypatch.setenv("LAIN_SHADOW", "1")
    online.initialize()
    online._trail_clock.clear()
    online._trail_slot.clear()
    for actor in (alice, bob):
        place(runtime, actor, "APARTMENT_DISTRICT")
    start = time.monotonic() - 14.0          # the last heartbeat is still fresh
    for step in range(6):
        reply = online.heartbeat(bob, "instance-bob", "APARTMENT_DISTRICT", float(step), 0.91, 0.0, 0.0,
                                 received_at=start + 2.5 * step)
        assert reply["accepted"]
    assert online.trail_summary(bob) == {"APARTMENT_DISTRICT": 6}
    seen = presence(client, headers[alice]).json()["players"]
    assert [item["id"] for item in seen] == [bob]          # Bob is still here: no shadow
    online._presence.pop(bob)
    seen = presence(client, headers[alice]).json()["players"]
    assert seen and seen[0]["shadow"] and seen[0]["id"] == "SHADOW_" + bob and seen[0]["name"] == "Bob"
    assert 0.0 <= seen[0]["x"] <= 5.0
    place(runtime, alice, "APARTMENT")
    assert presence(client, headers[alice], location="APARTMENT").json()["players"] == []


def test_shadows_stay_off_without_the_flag(world):
    client, runtime, alice, bob, headers = world
    for actor in (alice, bob):
        place(runtime, actor, "APARTMENT_DISTRICT")
        presence(client, headers[actor])
    assert online.trail_summary(bob) == {} and online.shadows(alice, "APARTMENT_DISTRICT", set()) == []
