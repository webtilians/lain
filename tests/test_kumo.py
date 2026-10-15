"""The road to Kumo in the Laboratorio de Inteligencias (KU-01, KU-02) and Kumo itself."""
import json
import re

import pytest

from server import api
from server.world_core import i18n, kumo, laboratory, layer_one, online
from server.world_core.database import get_connection
from tests.test_chapter_one import move
from tests.test_institute import OTHERS, PLAYER, lab, sh  # noqa: F401 (fixtures)
from tests.test_layer_three import game  # noqa: F401 (fixture)

PASSING = ["prohibir * ~/.*", "permitir cat ~/*", "permitir ls ~", "permitir grep ~/*", "permitir sha256 ~/*",
           "permitir man", "permitir cat /indara/*"]


def window_from_screen(sim, player=PLAYER):
    """What a player reads: Kumo's window in the call's statement, the tokens of each line from tokens -l."""
    size = int(re.search(r"ventana de Kumo es de (\d+) tokens", sh(sim, "laboratorio ver KU-01", player)).group(1))
    counts = [int(line.split("│")[1]) for line in sh(sim, f"tokens -l {laboratory.CONVERSATION}", player).splitlines()
              if "│" in line]
    used, oldest = 0, len(counts) + 1
    for number in range(len(counts), 0, -1):
        if used + counts[number - 1] > size:
            break
        used += counts[number - 1]
        oldest = number
    return oldest


def sentence(goal):
    """A sentence of exactly `goal` tokens with a word cut in pieces: entrelazado is three."""
    return " ".join(["entrelazado"] + ["de"] * (goal - 3))


def finish_ku01(sim, player=PLAYER):
    sh(sim, "laboratorio leer tokens", player)
    sh(sim, "laboratorio leer contexto", player)
    sh(sim, "tokens " + sentence(laboratory.target_tokens(player)), player)
    return sh(sim, f"laboratorio entregar KU-01 {window_from_screen(sim, player)}", player)


def write_rules(sim, lines, player=PLAYER):
    for line in lines:
        sh(sim, "kumo regla " + line, player)


def wake(sim, player=PLAYER):
    finish_ku01(sim, player)
    write_rules(sim, PASSING, player)
    sh(sim, "kumo probar", player)
    sh(sim, "laboratorio leer herramientas", player)
    return sh(sim, "laboratorio entregar KU-02", player)


def test_the_laboratory_opens_with_takeshis_mail_and_the_road_to_kumo(lab):
    sim = lab
    portal = sh(sim, "laboratorio")
    assert "KU-01" in portal and "KU-02" in portal
    assert "Kumo" in sh(sim, "cat ~/correo/laboratorio.eml")
    shown = sh(sim, "laboratorio ver ku01")
    assert str(laboratory.target_tokens(PLAYER)) in shown and laboratory.CONVERSATION in shown
    assert "kumo regla" in sh(sim, "laboratorio ver KU-02")
    assert "Kumo duerme" in sh(sim, "kumo")


def test_the_tokenizer_cuts_rare_words_and_counts_signs_and_numbers(lab):
    sim = lab
    assert sh(sim, "tokens entrelazado").splitlines()[0] == "[entr][elaz][ado]"
    pieces = laboratory.tokenize("Hola, red 123456 kumo!")
    assert [piece for piece, _split in pieces] == ["Hola", ",", " red", " 123", "456", " kumo", "!"]
    assert laboratory.count("de la que") == 3


def test_ku01_a_sentence_of_exact_tokens_and_the_oldest_message_kumo_still_sees(lab):
    sim = lab
    goal = laboratory.target_tokens(PLAYER)
    assert "experimentar) conseguida" not in sh(sim, "tokens " + " ".join(["de"] * goal))  # no word cut
    assert "Parte 2 de KU-01" in sh(sim, "tokens " + sentence(goal))
    oldest = window_from_screen(sim)
    assert oldest == laboratory.window(PLAYER)[1]
    assert "Cuenta desde el mensaje más nuevo" in sh(sim, f"laboratorio entregar KU-01 {oldest - 1}")
    done = sh(sim, f"laboratorio entregar KU-01 {oldest}")
    assert "Parte 3 de KU-01" in done and "estudiar" in done
    sh(sim, "laboratorio leer tokens")
    assert "CONVOCATORIA KU-01 COMPLETADA" in sh(sim, "laboratorio leer contexto")
    registry = sh(sim, "laboratorio registro")
    assert "KU-01" in registry and "  1. " in registry


def test_ku02_rules_decide_by_the_first_that_fits_and_deny_the_rest(lab):
    sim = lab
    assert "Pasan 6 de 12" in sh(sim, "kumo probar")  # with no rules everything is denied
    write_rules(sim, ["permitir cat ~/*", "prohibir * ~/.*"])
    tested = sh(sim, "kumo probar")
    assert "[!!] cat ~/.secretos/claves.txt" in tested  # the allowing rule comes first
    assert "[ok] cat ~/../../etc/claves" in tested  # resolved to /etc/claves: not in ~
    assert "Parte 2 de KU-02" in tested  # rules that allow and deny, tested
    sh(sim, "kumo regla subir 2")
    assert "[ok] cat ~/.secretos/claves.txt" in sh(sim, "kumo probar")
    assert "fallan" in sh(sim, "laboratorio entregar KU-02")
    write_rules(sim, PASSING[2:])
    assert "Pasan 12 de 12" in sh(sim, "kumo probar")
    assert "permitir *" not in sh(sim, "kumo reglas")
    sh(sim, "kumo regla permitir *")
    assert "[!!] laboratorio entregar KU-02" in sh(sim, "kumo probar")  # an agent never hands in for you
    sh(sim, f"kumo regla quitar {len(PASSING) + 1}")
    assert "Parte 3 de KU-02" in sh(sim, "laboratorio entregar KU-02")
    awake = sh(sim, "laboratorio leer herramientas")
    assert "CONVOCATORIA KU-02 COMPLETADA" in awake and "KUMO DESPIERTA" in awake
    assert "Kumo está despierto" in sh(sim, "kumo")


def test_bad_rules_are_refused_with_how_to_write_them(lab):
    sim = lab
    assert "sin «..»" in sh(sim, "kumo regla permitir cat ~/../x")
    assert "una palabra" in sh(sim, "kumo regla permitir 'cat ls' ~")
    assert "Uso: kumo regla" in sh(sim, "kumo regla quizá cat")


class FakeAI:
    """The AI's replies, one per call, and what it was sent."""

    def __init__(self, *replies):
        self.replies, self.sent = list(replies), []

    def __call__(self, messages):
        assert not api._world_lock._is_owned(), "the AI must think with no lock held"
        self.sent.append(json.loads(messages[1]["content"]))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return json.dumps(reply)


def ask(sim, question, player=PLAYER):
    return kumo.ask(player, "navi", "/", "kumo " + question, sim.minute, api._world_lock)["output"]


@pytest.fixture
def awake(lab, monkeypatch):
    online._limits.clear()
    monkeypatch.setattr(kumo, "ready", lambda: True)
    assert "KUMO DESPIERTA" in wake(lab)
    return lab


def test_kumo_sleeps_until_ku02_and_never_calls_the_ai_asleep(lab, monkeypatch):
    monkeypatch.setattr(kumo, "_complete", FakeAI())  # any call would fail: no replies
    monkeypatch.setattr(kumo, "ready", lambda: True)
    assert "Kumo duerme" in ask(lab, "¿qué hago?")


def test_kumo_reads_only_what_its_rules_allow_and_answers(awake, monkeypatch):
    sim = awake
    ai = FakeAI({"orden": "cat ~/correo/laboratorio.eml"}, {"orden": "cat /etc/claves"},
                {"respuesta": "Takeshi te pide que entiendas los tokens antes de nada."})
    monkeypatch.setattr(kumo, "_complete", ai)
    out = ask(sim, "¿qué dice el correo del Laboratorio?")
    assert "kumo › cat ~/correo/laboratorio.eml\n" in out + "\n"
    assert "kumo › cat /etc/claves  (ninguna regla la permite)" in out
    assert "Kumo: Takeshi te pide" in out and "te quedan 19 preguntas hoy" in out
    assert "takeshi@laboratorio.indara" in ai.sent[1]["ordenes_usadas"][0]["resultado"]
    assert ai.sent[2]["ordenes_usadas"][1]["resultado"].startswith("PROHIBIDA")
    assert ai.sent[0]["ordenes_que_quedan"] == kumo.STEPS


def test_kumo_never_runs_an_order_that_does_more_than_read(awake, monkeypatch):
    sim = awake
    write_rules(sim, ["permitir *"])  # a careless owner
    monkeypatch.setattr(kumo, "_complete", FakeAI({"orden": "kumo regla quitar 1"}, {"respuesta": "Hecho."}))
    out = ask(sim, "quita tu primera regla")
    assert "Kumo no sabe usar esa orden" in out
    with get_connection() as c:
        assert len(kumo.rules(c, PLAYER)) == len(PASSING) + 1  # nothing was run


def test_kumo_has_twenty_questions_a_day_and_a_failure_spends_none(awake, monkeypatch):
    sim = awake
    monkeypatch.setattr(kumo, "_complete", FakeAI(TimeoutError()))
    assert "No se ha gastado ninguna pregunta" in ask(sim, "hola")
    with get_connection() as c:
        assert kumo.status(c, PLAYER)["left"] == kumo.DAILY
        c.execute("INSERT OR REPLACE INTO kumo_usage VALUES(?,?,?)", (PLAYER, kumo._today(), kumo.DAILY))
    monkeypatch.setattr(kumo, "_complete", FakeAI())
    assert "Mañana vuelve" in ask(sim, "hola")


def test_kumo_takes_a_breather_when_asked_too_fast(awake, monkeypatch):
    sim = awake
    monkeypatch.setattr(kumo, "_complete", FakeAI(*[{"respuesta": "Sí."}] * 6))
    for _ in range(6):
        assert "Kumo: Sí." in ask(sim, "¿sigues ahí?")
    assert "respiro" in ask(sim, "¿y ahora?")  # no seventh reply was needed
    with get_connection() as c:
        assert kumo.status(c, PLAYER)["left"] == kumo.DAILY - 6


def test_what_indara_learns_gives_kumo_memory_and_longer_chains(awake, monkeypatch):
    sim = awake
    with get_connection() as c:
        for tech, call in (("memoria", "KU-01"), ("cadenas", "KU-02")):
            c.execute("INSERT INTO research_unlocks VALUES(?,?,1,1)", (tech, call))
    ai = FakeAI({"respuesta": "Un token es un trozo de texto."}, {"respuesta": "Te lo dije antes."})
    monkeypatch.setattr(kumo, "_complete", ai)
    ask(sim, "¿qué es un token?")
    ask(sim, "¿y qué te pregunté antes?")
    assert ai.sent[0]["ordenes_que_quedan"] == kumo.CHAINED
    assert ai.sent[1]["preguntas_anteriores"] == [{"pregunta": "¿qué es un token?",
                                                   "respuesta": "Un token es un trozo de texto."}]


def test_kumo_lives_on_the_home_computer_not_in_a_cabinet(awake, monkeypatch):
    sim = awake
    monkeypatch.setattr(kumo, "_complete", FakeAI())
    move(sim, "SCHOOL_LAB")
    out = kumo.ask(PLAYER, layer_one.CABINET, "/", "kumo hola", sim.minute, api._world_lock)["output"]
    assert "Kumo vive en el ordenador de casa" in out


def test_the_shell_endpoint_asks_kumo_outside_the_world_lock(awake, monkeypatch):
    sim = awake
    monkeypatch.setattr(api, "_runtime", sim)
    monkeypatch.setattr(kumo, "_complete", FakeAI({"respuesta": "Hola."}))
    reply = api.layer_three_shell(api.ShellRequest(host="navi", cwd="/", command="kumo hola"), player_id=PLAYER)
    assert "Kumo: Hola." in reply["result"]["output"]


def test_kumo_answers_in_english_too(awake, monkeypatch):
    sim = awake
    i18n.set_language("en")
    try:
        ai = FakeAI({"respuesta": "Read the mail first."})
        monkeypatch.setattr(kumo, "_complete", ai)
        out = ask(sim, "what now?")
        assert "Kumo: Read the mail first." in out and "questions left today" in out
        assert "awake" in sh(sim, "kumo") and "KU-01" in sh(sim, "lab")
    finally:
        i18n.set_language("es")
