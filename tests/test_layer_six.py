"""Capa 06 · Presentación: base64, XOR masks, a known plaintext and HMACs, from game output."""
import hashlib
import hmac
import re

import pytest

from server.world_core import i18n, layer_five, layer_six
from server.world_core.agent_context import AgentContextBuilder
from tests.test_chapter_one import move
from tests.test_layer_five import archive, merged  # noqa: F401 (fixture)
from tests.test_layer_four import PLAYER, connected, layer_three_game, out  # noqa: F401 (fixtures)

VIDEO = layer_six.VIDEO
SPOOL = layer_six.SPOOL


def reach_club(sim, language="es"):
    merged(sim)
    token = i18n.set_language(language)
    try:
        ending = out(sim, "lease s1", host=layer_five.ARCHIVE)
    finally:
        i18n.reset(token)
    move(sim, "VIDEO_CLUB")
    return re.search(r"\(([^)]+)\) (?:abre algo|opens something)", ending).group(1)


@pytest.fixture
def club(monkeypatch, archive):
    monkeypatch.setenv("LAIN_LAYER_SIX", "1")
    layer_six.initialize_layer_six()
    assert layer_six.layer_snapshot(PLAYER) == {"active": False}
    return archive, reach_club(archive)


def signature(sim, letter):
    return re.search(r"x-signature: hmac-sha256/64 ([0-9a-f]{16})", out(sim, f"cat {SPOOL}/{letter}.pkt", host=VIDEO)).group(1)


def mac(sim, letter, key):
    return re.match(r"hmac-sha256/64 ([0-9a-f]{16})", out(sim, f"hmac {SPOOL}/{letter}.pkt {key}", host=VIDEO)).group(1)


def known_key(sim, letter, opening="Has vuelto."):
    """Plaintext ⊕ masked = key: the shortest repetition in the first bytes."""
    stream = out(sim, f'xor {SPOOL}/{letter}.pkt "{opening}"', host=VIDEO)[:len(opening)]
    period = next(p for p in range(1, len(stream)) if all(stream[i] == stream[i + p] for i in range(len(stream) - p)))
    return stream[:period]


def read(sim):
    """What a player works out: each face's key and whose signature holds."""
    faces = {}
    for letter in "abc":
        key = known_key(sim, letter)
        faces[letter] = {"key": key, "signed": mac(sim, letter, key) == signature(sim, letter)}
    return faces


def test_starts_after_capa_05_with_mail_and_three_faces(club):
    sim, word = club
    snapshot = layer_six.layer_snapshot(PLAYER)
    assert snapshot["active"] and snapshot["fragments"] == 3 and "videoclub" in snapshot["goal"]
    assert "base64" in out(sim, f"cat {SPOOL}/LEEME", host=VIDEO)
    assert out(sim, f"ls {SPOOL}", host=VIDEO).split() == ["LEEME", "a.pkt", "b.pkt", "c.pkt"]
    dump = out(sim, f"base64 -d {SPOOL}/a.pkt", host=VIDEO)
    assert re.match(r"00000000  ([0-9a-f]{2} ){15}[0-9a-f]{2}  ", dump)
    assert "⊕" in out(sim, "man xor", host=VIDEO) and "WebSocket" in out(sim, "man mask", host=VIDEO)
    move(sim, "APARTMENT")
    assert "Tres caras" in out(sim, "cat ~/correo/caras.eml") and "videoclub" in out(sim, "xor a b")


def test_known_plaintext_and_signatures_tell_the_faces_apart_then_publish(club):
    sim, word = club
    faces = read(sim)
    mine = [letter for letter, face in faces.items() if face["key"] == word]
    authentic = next(letter for letter in mine if faces[letter]["signed"])
    noema = next(letter for letter in mine if letter != authentic)
    replica = next(letter for letter in faces if letter not in mine)
    assert not faces[noema]["signed"] and faces[replica]["signed"] and faces[replica]["key"] != word
    assert "NODO_07" in out(sim, f"xor {SPOOL}/{noema}.pkt {word}", host=VIDEO)
    assert "Antes de decidir" in out(sim, f"publish {authentic}", host=VIDEO)
    message = out(sim, f"xor {SPOOL}/{authentic}.pkt 0x{word.encode().hex()}", host=VIDEO)
    assert message.startswith("Has vuelto.") and "solo tú has vivido" in message
    assert "Ya sabes" in layer_six.layer_snapshot(PLAYER)["goal"]
    assert "no es la de la Sesión Cero" in out(sim, f"publish {noema}", host=VIDEO)
    ending = out(sim, f"publicar {authentic}.pkt", host=VIDEO)
    assert "CAPA 06 COMPLETADA" in ending and "firma pública" in ending
    assert layer_six.layer_snapshot(PLAYER)["decision"] == "PUBLISH" and layer_six.layer_snapshot(PLAYER)["fragments"] == 4
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("hablar con su voz" in memory["text"] for memory in nora)


def test_replying_to_the_replica_needs_its_own_key_and_happens_once(club):
    sim, word = club
    faces = read(sim)
    authentic = next(letter for letter, face in faces.items() if face["key"] == word and face["signed"])
    replica = next(letter for letter, face in faces.items() if face["key"] != word)
    assert "Antes de decidir" in out(sim, "keep", host=VIDEO)
    out(sim, f"xor {SPOOL}/{authentic}.pkt {word}", host=VIDEO)
    assert "no es de la réplica" in out(sim, f"reply {authentic} {word}", host=VIDEO)
    assert "no podrá leerte" in out(sim, f"reply {replica} {word}", host=VIDEO)
    assert "copia sabe que lo es" in out(sim, f"responder {replica} {faces[replica]['key']}", host=VIDEO)
    assert "Ya decidiste" in out(sim, "guardar", host=VIDEO)
    assert layer_six.layer_snapshot(PLAYER)["decision"] == "REPLY"
    k = AgentContextBuilder().build("AGENT_K")["chapter_memory"]["memories"]
    assert any("réplica de KAGAMI" in memory["text"] for memory in k)


def test_bad_input_is_explained(club):
    sim, word = club
    assert "Uso" in out(sim, f"base64 {SPOOL}/a.pkt", host=VIDEO)
    assert "no lleva carga" in out(sim, f"xor {SPOOL}/LEEME {word}", host=VIDEO)
    assert "no existe" in out(sim, f"hmac {SPOOL}/z.pkt {word}", host=VIDEO)
    assert "0x4b2a" in out(sim, f"xor {SPOOL}/a.pkt 0xzz", host=VIDEO)
    assert "Uso" in out(sim, "publish", host=VIDEO) and "Uso" in out(sim, "reply a", host=VIDEO)


def test_each_player_gets_different_faces():
    run = {"language": "es"}
    stories = [layer_six.Story(f"PLAYER_{n:032x}", "Ana", run, layer_five.WORDS[n % 8], layer_five.WORDS)
               for n in range(120)]
    assert len({tuple(s.faces.values()) for s in stories}) == 6
    for story in stories:
        assert story.replica_key != story.key
        assert layer_six.xor(story.masked["sesion0"], story.key.encode()).decode() == story.plain["sesion0"]
        assert story.signature["noema"] == story.signature["sesion0"] != layer_six.sign(story.key, story.masked["noema"])
        expected = hmac.new(story.replica_key.encode(), story.masked["kagami"], hashlib.sha256).hexdigest()[:16]
        assert story.signature["kagami"] == expected


def test_english_player_reads_the_layer_in_english(monkeypatch, archive):
    monkeypatch.setenv("LAIN_LAYER_SIX", "1")
    layer_six.initialize_layer_six()
    word = reach_club(archive, "en")
    token = i18n.set_language("en")
    try:
        for letter in "abc":
            key = known_key(archive, letter, "You have returned.")
            assert key in (word, layer_six.story_for(PLAYER).replica_key)
            assert out(archive, f"xor {SPOOL}/{letter}.pkt {key}", host=VIDEO).startswith("You have returned.")
        header = out(archive, f"cat {SPOOL}/b.pkt", host=VIDEO).split("\n\n")[0]
        assert "the key does not travel" in header
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay|cara)\b", re.I)
        for command in ("help", "man encoding", "man base64", "man xor", "man mask", "man hmac", f"cat {SPOOL}/LEEME",
                        "keep", "publish a", "reply a b", f"base64 {SPOOL}/a.pkt",
                        f"xor {SPOOL}/LEEME x", f"hmac {SPOOL}/a.pkt 0xzz"):
            # man encoding spells out the UTF-8 bytes of “á” on purpose.
            text = out(archive, command, host=VIDEO).replace("“á”", "")
            lines = [line for line in text.splitlines() if spanish.search(line)]
            assert not lines, (command, lines[:3])
        move(archive, "APARTMENT")
        for command in ("cat ~/correo/caras.eml", "xor a b"):
            lines = [line for line in out(archive, command).splitlines() if spanish.search(line)]
            assert not lines, (command, lines[:3])
        snapshot = i18n.payload(layer_six.layer_snapshot(PLAYER))
        assert not spanish.search(snapshot["goal"] + snapshot["mail"]["body"] + snapshot["title"] + snapshot["mail"]["subject"])
    finally:
        i18n.reset(token)
