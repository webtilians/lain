"""The Instituto de Física del Puerto: the qubit and BB84 call, its registry and QKD entering the Malla."""
import re

import pytest

from server.world_core import i18n, institute, layer_three
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection
from server.world_core.player_view import build_player_snapshot
from tests.test_layer_three import PLAYER, game  # noqa: F401 (fixture)

OTHERS = ["PLAYER_ANA", "PLAYER_BEA", "PLAYER_CRIS"]


@pytest.fixture
def lab(game):  # noqa: F811
    """The usual player at home and three more players, all already connected to the Malla."""
    with get_connection() as c:
        for player in OTHERS:
            name = player.split("_")[1].title()
            c.execute("INSERT INTO agents(id,name,faction,location,goal,energy,controller_type) "
                      "VALUES(?,?,'UNALIGNED','APARTMENT','UNKNOWN',1,'HUMAN')", (player, name))
            c.execute("INSERT INTO layer_three(player_id, started_minute, connection_minute) VALUES(?, 1, 1)", (player,))
    return game


def sh(sim, command, player=PLAYER):
    return layer_three.run_shell(player, "navi", "/", command, sim.minute)["output"]


def row(text, label, spaced=False):
    """The values of one labelled row of bb84's output (labels follow the language)."""
    line = next(line for line in text.splitlines() if line.startswith(i18n.t(label)))
    return line[16:].split() if spaced else line[16:].replace(" ", "")


def clean_channel(player):
    return "b" if institute._spied(player) == "a" else "a"


def key_from_output(sim, channel, player=PLAYER):
    """What a player does by hand: keep the matching bases, drop the compared positions, read the rest."""
    measured = sh(sim, f"bb84 medir {channel}", player)
    assert i18n.t("Eliges las bases al azar, como haría Bob.") in measured
    published = sh(sim, f"bb84 bases {channel}", player)
    hideo, mine, bits = row(published, "bases de Hideo"), row(published, "tus bases"), row(published, "tus bits")
    assert mine == row(measured, "tus bases") and bits == row(measured, "tus bits")
    compared = sh(sim, f"bb84 comparar {channel}", player)
    public = [int(n) - 1 for n in row(compared, "posición", spaced=True)]
    matches = [i for i in range(len(hideo)) if hideo[i] == mine[i]]
    assert public == matches[0::2]
    errors = sum(bit != bits[i] for bit, i in zip(row(compared, "bit de Hideo", spaced=True), public))
    return "".join(bits[i] for i in matches if i not in public), errors


def finish(sim, player=PLAYER):
    for command in ("instituto leer qubit", "instituto leer bb84", "qubit nuevo", "qubit x", "qubit h",
                    "qubit medir x"):
        sh(sim, command, player)
    channel = clean_channel(player)
    key, _errors = key_from_output(sim, channel, player)
    return sh(sim, f"instituto entregar {channel} {key}", player)


def test_the_institute_opens_once_connected_and_hideo_writes(lab):
    sim = lab
    portal = sh(sim, "instituto")
    assert portal.startswith("INSTITUTO DE FÍSICA DEL PUERTO · instituto.malla")
    assert "QB-01  El qubit y la clave que delata al espía" in portal
    assert "estudiar [ ] · experimentar [ ] · demostrar [ ]" in portal and "han terminado 0/3" in portal
    assert "nada nuevo todavía" in portal
    assert "hideo@instituto.malla" in sh(sim, "cat ~/correo/instituto.eml")
    assert "instituto ver <código>" in sh(sim, "help")
    assert "qubit nuevo" in sh(sim, "man qubit") and "24 fotones" in sh(sim, "man bb84")
    with get_connection() as c:
        assert institute.run_for(c, "PLAYER_NOBODY") is None, "only players connected to the Malla"


def test_study_experiment_and_demonstrate_finish_the_call(lab):
    sim = lab
    shown = sh(sim, "instituto ver qb01")
    assert "1. Estudiar [ ]  instituto leer qubit · instituto leer bb84" in shown and "umbral: 3 personas" in shown
    assert "superposición" in sh(sim, "instituto leer qubit")
    assert "Parte 1" in sh(sim, "instituto leer bb84")
    assert "Parte 1" not in sh(sim, "instituto leer bb84"), "reading again changes nothing"

    assert "Medido en la base Z: 0 seguro." in sh(sim, "qubit")
    assert "pasa de |0> a |1>" in sh(sim, "qubit x")
    assert "pasa de |1> a |->" in sh(sim, "qubit h")
    assert "Medido en la base X: - seguro (cuenta como 1)." in sh(sim, "qubit estado")
    measured = sh(sim, "qubit medir x")
    assert "sale - (cuenta como 1)" in measured and "Era seguro" in measured and "Parte 2 de QB-01" in measured

    spied, channel = institute._spied(PLAYER), clean_channel(PLAYER)
    assert "Primero saca la clave" in sh(sim, f"instituto entregar {channel} 0101")
    key, errors = key_from_output(sim, channel)
    assert errors == 0 and len(key) >= 4
    assert "Esa no es la clave" in sh(sim, f"instituto entregar {channel} {key[::-1]}1")
    _tapped_key, tapped_errors = key_from_output(sim, spied)
    assert tapped_errors >= 2, "the tap always shows in the sample"
    assert "alguien medía los fotones" in sh(sim, f"instituto entregar {spied} {_tapped_key}")
    grouped = " ".join(key[i:i + 4] for i in range(0, len(key), 4))
    done = sh(sim, f"instituto entregar QB-01 {channel} {grouped}")
    assert f"Clave aceptada: {key}" in done and "CONVOCATORIA QB-01 COMPLETADA" in done
    assert "Van 1 de 3" in done
    assert "Ya entregaste" in sh(sim, f"instituto entregar {channel} {key}")
    assert "terminada" in sh(sim, "instituto") and "Estás en el registro" in sh(sim, "instituto ver QB-01")
    registry = sh(sim, "instituto registro")
    assert "QB-01 · El qubit y la clave que delata al espía" in registry and "1. " in registry
    assert "Han terminado 1/3." in sh(sim, "instituto ver QB-01")
    snapshot = build_player_snapshot(PLAYER)["institute"]
    assert snapshot["completed"] == [{"id": "QB-01", "title": "El qubit y la clave que delata al espía"}]
    assert snapshot["unlocked"] == []
    hideo = AgentContextBuilder().build(institute.HIDEO)["chapter_memory"]["memories"]
    assert any("QB-01" in memory["text"] for memory in hideo)


def test_steps_out_of_order_explain_what_is_missing(lab):
    sim = lab
    channel = clean_channel(PLAYER)
    sh(sim, f"bb84 medir {channel}")
    assert "bb84 bases" in sh(sim, f"instituto entregar {channel} 0101")
    assert "Primero Hideo tiene que decir sus bases" in sh(sim, f"bb84 comparar {channel}")
    sh(sim, f"bb84 bases {channel}")
    assert "nadie escuchaba: bb84 comparar" in sh(sim, f"instituto entregar {channel} 0101")
    assert "ronda 1 · medido · bases publicadas" in sh(sim, "bb84")
    sh(sim, f"bb84 medir {channel} {'+x' * 12}")
    assert "ronda 2 · medido" in sh(sim, "bb84") and "bases publicadas" not in sh(sim, "bb84"), "a new round starts over"
    assert "Necesito 24 bases" in sh(sim, f"bb84 medir {channel} ++x")
    key, _errors = key_from_output(sim, channel)
    done = sh(sim, f"instituto entregar {channel} {key}")
    assert "Parte 3" in done and "te falta: estudiar (instituto leer), experimentar (qubit)" in done
    assert "COMPLETADA" not in done


def test_the_tap_always_shows_and_the_key_is_never_short():
    for number in range(40):
        player = f"PLAYER_{number}"
        for channel in institute.CHANNELS:
            bases = "".join("+x"[(number * 7 + i * i) % 2] for i in range(institute.PHOTONS))
            alice_bits, alice_bases, bob_bits = institute._photons(player, channel, 1, bases)
            sample, key = institute._split(alice_bases, bases)
            errors = sum(alice_bits[i] != bob_bits[i] for i in sample + key)
            assert len(key) >= 4
            if channel == institute._spied(player):
                assert sum(alice_bits[i] != bob_bits[i] for i in sample) >= 2
            else:
                assert errors == 0, "a clean channel has no errors where the bases match"


def test_measuring_in_the_wrong_basis_is_random_and_changes_the_qubit(lab, monkeypatch):
    sim = lab
    monkeypatch.setattr(institute.random, "choice", lambda options: options[-1])
    sh(sim, "qubit h")
    measured = sh(sim, "qubit medir z")
    assert "sale 1." in measured and "Era al azar: el qubit estaba en |+> y la medida lo ha dejado en |1>" in measured
    assert "Medido en la base Z: 1 seguro." in sh(sim, "qubit")
    assert "Parte 2" not in sh(sim, "qubit medir x"), "a lucky 1 in X is not the experiment"
    sh(sim, "qubit nuevo")
    for gate, state in (("h", "|+>"), ("z", "|->"), ("h", "|1>"), ("x", "|0>")):
        assert sh(sim, f"qubit {gate}").endswith(f"a {state}.")
    assert "Uso: qubit medir" in sh(sim, "qubit medir y")


def test_three_researchers_bring_qkd_to_the_whole_malla(lab):
    sim = lab
    assert "Van 0" in sh(sim, "qkd") and "todavía no sabe" in sh(sim, "qkd")
    assert "Van 1 de 3" in finish(sim, OTHERS[0])
    assert "Van 2 de 3" in finish(sim, OTHERS[1])
    third = finish(sim, OTHERS[2])
    assert "LA MALLA APRENDE · QKD entra en la Malla para todos." in third
    out = sh(sim, "qkd")
    assert out.startswith("qkd · enlaces cuánticos") and out.count("QBER") == 3 and out.count("ALGUIEN ESCUCHA") == 1
    assert "relay-escuela" in out
    assert "QKD (desde el minuto" in sh(sim, "instituto") and "han terminado 3 · QKD ya está en la Malla" in sh(sim, "instituto")
    assert "QKD entró en la Malla" in sh(sim, "instituto registro")
    registry = sh(sim, "instituto registro")
    assert registry.index("1. Ana") < registry.index("2. Bea") < registry.index("3. Cris")
    snapshot = build_player_snapshot(PLAYER)["institute"]
    assert [tech["id"] for tech in snapshot["unlocked"]] == ["qkd"] and snapshot["completed"] == []
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("QKD ya está en la Malla" in memory["text"] for memory in nora)
    assert "LA MALLA APRENDE" not in finish(sim), "it enters the Malla once"
    with get_connection() as c:
        assert c.execute("SELECT COUNT(*) FROM events WHERE action='MALLA_EVOLVES'").fetchone()[0] == 1


def test_the_institute_in_english(lab):
    sim = lab
    spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|tus|está|hay|desde|canal|"
                         r"fotones|clave|bits de)\b", re.I)
    token = i18n.set_language("en")
    try:
        channel = clean_channel(PLAYER)
        texts = [sh(sim, "institute"), sh(sim, "institute show QB-01"), sh(sim, "institute read qubit"),
                 sh(sim, "institute read bb84"), sh(sim, "institute read nothing"), sh(sim, "qubit"),
                 sh(sim, "qubit x"), sh(sim, "qubit h"), sh(sim, "qubit measure x"), sh(sim, "qubit measure z"),
                 sh(sim, "qubit measure y"), sh(sim, "qubit new"), sh(sim, "bb84"),
                 sh(sim, f"bb84 compare {channel}"), sh(sim, f"bb84 measure {channel}"),
                 sh(sim, f"bb84 measure {channel} ++"), sh(sim, f"institute submit {channel} 01"),
                 sh(sim, f"bb84 compare {channel}"), sh(sim, f"bb84 bases {channel}"),
                 sh(sim, f"institute submit {channel} 01"), sh(sim, f"bb84 compare {channel}"),
                 sh(sim, f"institute submit {channel} 01"),
                 sh(sim, f"institute submit {institute._spied(PLAYER)} 01"), sh(sim, "bb84"), sh(sim, "qkd"),
                 sh(sim, "institute registry"), sh(sim, "man institute"), sh(sim, "man qubit"),
                 sh(sim, "man bb84"), sh(sim, "man qkd"), sh(sim, "help"), sh(sim, "cat ~/correo/instituto.eml"),
                 sh(sim, "institute submit")]
        for player in OTHERS:
            texts.append(finish(sim, player))
        texts += [sh(sim, "qkd"), sh(sim, "institute"), sh(sim, "institute registry"), finish(sim)]
        snapshot = i18n.payload(build_player_snapshot(PLAYER)["institute"])
        texts += [item[key] for item in snapshot["completed"] + snapshot["unlocked"] for key in item if key != "id"]
        for text in texts:
            lines = [line for line in text.splitlines() if spanish.search(line)
                     and not re.search(r"Ana|Bea|Cris|hideo@|instituto\.malla", line)]
            assert not lines, lines[:3]
    finally:
        i18n.reset(token)
