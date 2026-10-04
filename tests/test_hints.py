"""Hints: the terminal gives the idea and names who knows more; that neighbour gives the method and then
the values; levels reset on each new step, and level 3 really solves the step."""
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
    line = next(line for line in text.splitlines() if re.search(r"\b(?:Escribe|Type) ", line))
    return re.search(r"(?:Escribe|Type) (.+?)(?:\.$| y | and |$)", line).group(1)


def level3(sim, extra="", host="navi"):
    """Ask in the terminal, then ask the neighbour it names twice: the third hint, with the player's values."""
    from server.world_core.database import get_connection
    ask(sim, extra, host=host)
    with get_connection() as c:
        layer = hints.current(hints._runs(c, PLAYER))
        actor = hints.EXPERTS[layer][0]
        if hints.expert(c, layer) is None:
            return ask(sim, extra, host=host) and ask(sim, extra, host=host)
        hints.consult(c, PLAYER, actor, sim.minute)
        return hints.consult(c, PLAYER, actor, sim.minute)


def test_levels_climb_reset_on_a_new_step_and_nora_remembers(physical):
    from server.world_core.database import get_connection
    sim = physical
    first = ask(sim, host=CABINET)
    assert first.startswith("PISTA 1/3 · Capa 01 · Física") and "scope naranja" in first
    with get_connection() as c:
        second = hints.consult(c, PLAYER, "RESIDENT_027", sim.minute)
        assert second.startswith("PISTA 2/3") and "entre 20" in second and "vuelve a preguntarme" in second
        story = layer_one.story_for(PLAYER)
        third = hints.consult(c, PLAYER, "RESIDENT_027", sim.minute)
        assert third.startswith("PISTA 3/3") and f"decode {story.pair} {story.samples} {story.convention}" in third
        assert "vuelve a preguntarme" not in third
        assert hints.consult(c, PLAYER, "RESIDENT_027", sim.minute).startswith("PISTA 3/3")
    assert "preámbulo y SFD encontrados" in out(sim, solution(third), host=CABINET)
    decide = ask(sim, host=CABINET)
    assert decide.startswith("PISTA 1/3") and "qué haces con el cable" in decide
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("me pidió ayuda con la Capa 01" in memory["text"] for memory in nora)


def test_choosing_a_layer_and_layers_not_reached_or_done(physical):
    sim = physical
    assert "traceroute" in ask(sim, "3", host=CABINET)
    assert "Todavía no has llegado a la Capa 05" in ask(sim, "5", host=CABINET)
    third = level3(sim, "1", host=CABINET)
    out(sim, solution(third), host=CABINET)
    out(sim, "dejar", host=CABINET)
    assert "ya está completada" in ask(sim, "1", host=CABINET)


def test_level_three_answers_the_tcp_handshake(connected):
    sim = connected
    text = level3(sim)
    story = layer_four.story_for(PLAYER)
    assert f"ack={story.isn_r + 1}" in text
    assert "ESTABLISHED" in out(sim, solution(text))
    following = ask(sim)
    assert following.startswith("PISTA 1/3 · Capa 04") and "tcpdump" in following


def test_level_three_merge_plan_commits(archive):
    sim = archive
    text = level3(sim, host=STATION)
    commit = re.search(r"commit version=\d+ token=\d+", text).group(0)
    loaded = states(sim)
    choices, _ = plan(loaded["base"], loaded["s0"], loaded["s1"])
    for field, side in choices.items():
        out(sim, f"merge {field} {side}", host=STATION)
    assert "Fusión confirmada" in out(sim, commit, host=STATION)
    assert "qué sesión conserva la cuenta" in ask(sim, host=STATION)


def test_level_three_unmasks_session_zero(club):
    sim, word = club
    text = level3(sim, host=VIDEO)
    assert word in text
    xor, hmac = re.findall(r"(?:xor|hmac) /var/spool/caras/\w\.pkt [^\s.]+", text)
    assert out(sim, xor, host=VIDEO).startswith("Has vuelto.")
    out(sim, hmac, host=VIDEO)
    assert "qué haces con su último paquete" in ask(sim, host=VIDEO)


def test_level_three_reaches_node_07(node):
    sim, word, name = node
    text = level3(sim)
    assert "s0-" in out(sim, solution(text))
    assert "cómo termina tu historia" in ask(sim)
    from server.world_core.database import get_connection
    with get_connection() as c:
        assert "PUT" in hints.consult(c, PLAYER, hints.EXPERTS["layer_seven"][0], sim.minute)


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


# ---------------------------------------------------------------- the neighbour who knows

@pytest.fixture
def residents_on(monkeypatch):
    """The neighbourhood is populated, so `pista` sends the player to someone."""
    monkeypatch.setenv("LAIN_CITY_RESIDENTS_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")


def talk(sim, actor):
    from server.api import perform_player_step
    from server.world_core.player_conversation import start_player_conversation
    assert perform_player_step(action="CONTACT", target=actor, simulation=sim)["action_result"]["accepted"]
    return start_player_conversation(actor, sim.minute, player_id=PLAYER)


def choose(sim, actor, conversation, choice):
    from server.world_core.player_conversation import reply_to_player_conversation
    return reply_to_player_conversation(actor, choice, conversation["turn_id"], sim.minute, player_id=PLAYER)


def finished_layer_one(name):
    """Another real player who already finished Capa 01."""
    from server.world_core import online
    from server.world_core.database import get_connection
    other, _token = online.create_player(name)
    with get_connection() as c:
        columns = [row[1] for row in c.execute("PRAGMA table_info(layer_one)")]
        values = ", ".join("?" if column == "player_id" else ("'SPLICE'" if column == "decision" else column)
                           for column in columns)
        c.execute(f"INSERT INTO layer_one ({', '.join(columns)}) SELECT {values} FROM layer_one WHERE player_id=?",
                  (other, PLAYER))


def test_pista_gives_the_idea_and_names_who_knows_more(residents_on, physical):
    sim = physical
    finished_layer_one("Alice")
    first = ask(sim, host=CABINET)
    assert first.startswith("PISTA 1/3 · Capa 01 · Física") and "scope naranja" in first
    assert "Jun Saito (Alumno del taller), en el aula de informática" in first and "Ve a buscarle" in first
    assert "También la han superado: Alice" in first
    again = ask(sim, host=CABINET)
    assert "PISTA 2/3" not in again, "the terminal must not climb when someone can be asked"


def test_the_expert_explains_the_method_then_the_values(residents_on, physical):
    sim = physical
    conversation = talk(sim, "RESIDENT_027")
    assert "ASK_HINT" not in [choice["id"] for choice in conversation["choices"]], "offered before pista sent the player"
    ask(sim, host=CABINET)
    conversation = talk(sim, "RESIDENT_027")
    offer = next(choice for choice in conversation["choices"] if choice["id"] == "ASK_HINT")
    assert "¿Me ayudas con la Capa 01 · Física?" in offer["text"]
    second = choose(sim, "RESIDENT_027", conversation, "ASK_HINT")
    assert second["response_source"] == "EXPERT_HINT"
    assert second["line"].startswith("PISTA 2/3 · Capa 01 · Física") and "entre 20" in second["line"]
    third = choose(sim, "RESIDENT_027", second, "ASK_HINT")
    story = layer_one.story_for(PLAYER)
    command = f"decode {story.pair} {story.samples} {story.convention}"
    assert third["line"].startswith("PISTA 3/3") and command in third["line"]
    # Back at the terminal, pista recalls what the neighbour said.
    recall = ask(sim, host=CABINET)
    assert "Jun Saito: " in recall and command in recall
    assert "preámbulo y SFD encontrados" in out(sim, command, host=CABINET)
    memories = AgentContextBuilder().build("RESIDENT_027")["chapter_memory"]["memories"]
    assert any("vino a preguntarme por la Capa 01" in memory["text"] for memory in memories)


def test_only_the_right_neighbour_helps(residents_on, physical):
    sim = physical
    ask(sim, host=CABINET)
    other = talk(sim, "RESIDENT_026")
    assert "ASK_HINT" not in [choice["id"] for choice in other["choices"]]
    with pytest.raises(ValueError, match="NO_HINT_HERE"):
        choose(sim, "RESIDENT_026", other, "ASK_HINT")


def test_the_expert_in_english(residents_on, physical):
    sim = physical
    token = i18n.set_language("en")
    try:
        first = ask(sim, host=CABINET)
        assert "The person who knows about this is Jun Saito (Workshop student), in the computer lab" in first
        conversation = talk(sim, "RESIDENT_027")
        offer = next(choice for choice in conversation["choices"] if choice["id"] == "ASK_HINT")
        assert "Can you help me with Layer 01" in offer["text"] or "Can you help me with" in offer["text"]
        reply = choose(sim, "RESIDENT_027", conversation, "ASK_HINT")
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay|escribe|otra)\b", re.I)
        lines = [line for line in (first + "\n" + offer["text"] + "\n" + reply["line"]).splitlines() if spanish.search(line)]
        assert not lines, lines[:3]
    finally:
        i18n.reset(token)
