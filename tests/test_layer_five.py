"""Capa 05 · Sesión: three-way merge, optimistic versions and fencing tokens, from game output."""
import json
import re

import pytest

from server.world_core import i18n, layer_five, layer_four, layer_three
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection
from tests.test_chapter_one import move
from tests.test_layer_four import PLAYER, connected, layer_three_game, out  # noqa: F401 (fixtures)

ARCHIVE = layer_five.ARCHIVE


def finish_layer_four(sim, decision="keepalive nodo07"):
    story4 = layer_four.story_for(PLAYER)
    with get_connection() as c:
        c.execute("UPDATE layer_four SET isn_l=1, complete=1, retransmitted=1, found_nora=1 WHERE player_id=?", (PLAYER,))
    move(sim, layer_three.RELAYS[story4.nora_relay][1])
    if decision.startswith("send"):
        decision = decision.format(seq=story4.ka_seq)
    assert "CAPA 04 COMPLETADA" in out(sim, decision, host=story4.nora_relay)


@pytest.fixture
def archive(monkeypatch, connected):
    monkeypatch.setenv("LAIN_LAYER_FIVE", "1")
    layer_five.initialize_layer_five()
    assert layer_five.layer_snapshot(PLAYER) == {"active": False}
    finish_layer_four(connected)
    move(connected, "STATION")
    return connected


def states(sim):
    return {name: json.loads(out(sim, f"cat /var/lib/sesiones/{name}.json", host=ARCHIVE)) for name in ("base", "s0", "s1")}


def plan(base, s0, s1, conflict_side="s1"):
    """The three-way rule, as a player applies it field by field."""
    choices, conflicts = {}, []
    for field in base:
        if s0[field] == s1[field] or s0[field] == base[field]:
            choices[field] = "s1"
        elif s1[field] == base[field]:
            choices[field] = "s0"
        else:
            choices[field] = conflict_side
            conflicts.append(field)
    return choices, conflicts


def lease(sim):
    listing = out(sim, "sessions", host=ARCHIVE)
    version = int(re.search(r"s1\s+ACTIVE\s+v(\d+)", listing).group(1))
    token = int(re.search(r"fencing_token=(\d+)", listing).group(1))
    old = int(re.search(r"s0\s+EXPIRED\s+v\d+\s+minute \d+\s+(\d+)", listing).group(1))
    return version, token, old


def merged(sim, conflict_side="s1"):
    loaded = states(sim)
    choices, conflicts = plan(loaded["base"], loaded["s0"], loaded["s1"], conflict_side)
    for field, side in choices.items():
        out(sim, f"merge {field} {side}", host=ARCHIVE)
    version, token, _ = lease(sim)
    reply = out(sim, f"commit version={version + 1} token={token}", host=ARCHIVE)
    assert "Fusión confirmada" in reply, reply
    return loaded, conflicts


def test_starts_after_capa_04_with_mail_and_archive_at_the_platform(archive):
    snapshot = layer_five.layer_snapshot(PLAYER)
    assert snapshot["active"] and snapshot["fragments"] == 2 and "andén" in snapshot["goal"]
    move(archive, "APARTMENT")
    assert "Dos sesiones" in out(archive, "cat ~/correo/sesion.eml")
    assert "andén" in out(archive, "sessions")
    assert "git" in out(archive, "man merge") and "compare-and-swap" in out(archive, "man version")


def test_merge_versions_and_fencing_then_yield_to_session_zero(archive):
    sim = archive
    loaded = states(sim)
    assert loaded["s0"]["kept_word"] and loaded["s1"]["kept_word"] is None
    choices, conflicts = plan(loaded["base"], loaded["s0"], loaded["s1"])
    assert "last_place" in conflicts and choices["kept_word"] == "s0" and choices["remembers_node07"] == "s0"
    version, token, old = lease(sim)
    for field, side in choices.items():
        out(sim, f"merge {field} {side}", host=ARCHIVE)
    out(sim, "merge kept_word s1", host=ARCHIVE)
    assert "pierde un cambio" in out(sim, f"commit version={version + 1} token={token}", host=ARCHIVE)
    out(sim, "merge kept_word s0", host=ARCHIVE)
    assert "rechazada" in out(sim, f"commit version={version + 1} token={old}", host=ARCHIVE)
    assert "Conflicto de versión" in out(sim, f"commit version={version} token={token}", host=ARCHIVE)
    assert "Fusión confirmada" in out(sim, f"commit version={version + 1} token={token}", host=ARCHIVE)
    fused = json.loads(out(sim, "cat /var/lib/sesiones/fusion.json", host=ARCHIVE))
    assert fused["kept_word"] == loaded["s0"]["kept_word"] and fused["fears"] in (loaded["s0"]["fears"], loaded["s1"]["fears"])
    ending = out(sim, "lease s0", host=ARCHIVE)
    assert "CAPA 05 COMPLETADA" in ending and loaded["s0"]["kept_word"] in ending
    assert layer_five.layer_snapshot(PLAYER)["decision"] == "YIELD"
    move(sim, "APARTMENT")
    assert "sesión 0 (restaurada)" in out(sim, "whoami")
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("misma persona" in memory["text"] for memory in nora)


def test_decisions_need_the_merge_and_happen_once(archive):
    sim = archive
    assert "Primero confirma" in out(sim, "lease s1", host=ARCHIVE)
    merged(sim, conflict_side="s0")
    assert "nadie puede comprobarlo" in out(sim, "lease s1", host=ARCHIVE).lower()
    assert "Ya decidiste" in out(sim, "expire s0", host=ARCHIVE)
    assert layer_five.layer_snapshot(PLAYER)["fragments"] == 3


def test_erase_is_remembered_and_commands_need_the_platform_console(archive):
    sim = archive
    other = next(r for r in layer_three.RELAYS if r != ARCHIVE)
    move(sim, layer_three.RELAYS[other][1])
    assert "andén" in out(sim, "merge name s1", host=other)
    move(sim, "STATION")
    assert "Uso" in out(sim, "merge name s7", host=ARCHIVE)
    merged(sim)
    assert "recolector de basura" in out(sim, "expire s0", host=ARCHIVE)
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("no se lo perdono" in memory["text"].lower() for memory in nora)


def test_what_session_one_trusts_depends_on_capa_04(monkeypatch, connected):
    monkeypatch.setenv("LAIN_LAYER_FIVE", "1")
    layer_five.initialize_layer_five()
    finish_layer_four(connected, "send nodo07 RST seq={seq}")
    story = layer_five.story_for(PLAYER)
    assert story.s1["trusts"] == "nadie" and story.s1["open_connections"] == 0


def test_each_player_gets_different_states():
    run = {"language": "es", "trusts": "Nora", "open_connections": 1, "fragments": 2, "started": 500}
    stories = [layer_five.Story(f"PLAYER_{n:032x}", "Ana", run) for n in range(120)]
    assert len({(s.token, s.version) for s in stories}) > 100
    assert len({s.word for s in stories}) == len(layer_five.WORDS)
    counts = {sum(s.resolution(f)[0] == "conflict" for f in layer_five.FIELDS) for s in stories}
    assert counts == {1, 2}
    assert all(s.s0_token < s.token for s in stories)


def test_english_player_reads_the_layer_in_english(archive):
    token = i18n.set_language("en")
    try:
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay)\b", re.I)
        for command, host in (("help", ARCHIVE), ("man merge", ARCHIVE), ("man lease", ARCHIVE),
                              ("man fencing", ARCHIVE), ("man version", ARCHIVE), ("man sesion", ARCHIVE),
                              ("sessions", ARCHIVE), ("merge", ARCHIVE), ("merge name s9", ARCHIVE),
                              ("commit version=1 token=1", ARCHIVE), ("lease s1", ARCHIVE),
                              ("cat /var/lib/sesiones/LEEME", ARCHIVE)):
            lines = [line for line in out(archive, command, host=host).splitlines() if spanish.search(line)]
            assert not lines, (command, lines[:3])
        snapshot = i18n.payload(layer_five.layer_snapshot(PLAYER))
        assert not spanish.search(snapshot["goal"] + snapshot["mail"]["body"] + snapshot["title"] + snapshot["mail"]["subject"])
    finally:
        i18n.reset(token)
