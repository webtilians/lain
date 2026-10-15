"""Russian players (TRADUCCION.md): the whole reviewed catalogue in Russian, and the first hour
without Spanish leaking through."""
import json
from pathlib import Path

from server.world_core import i18n, kumo, research
from server.world_core.prologue import submit_terminal_command, talk_to_prologue_npc
from server.world_core.wired import process_wired_message_acknowledgement
from tests.test_chapter_one import move
from tests.test_i18n_english import SPANISH, english, leaks  # noqa: F401 (fixture)

CATALOGUES = Path(__file__).resolve().parents[1] / "server" / "content" / "i18n"


def test_every_reviewed_text_has_its_russian():
    english_texts = json.loads((CATALOGUES / "en.json").read_text(encoding="utf-8"))
    russian = json.loads((CATALOGUES / "ru.json").read_text(encoding="utf-8"))
    assert set(russian) == set(english_texts), sorted(set(english_texts) ^ set(russian))[:5]
    assert i18n.t("Entrar", "ru") == "Войти"
    assert i18n.t("Ya entregaste KU-01. Takeshi lo tiene apuntado.", "ru").startswith("Ты уже сдал KU-01")


def test_the_prologue_speaks_russian(english):
    client, runtime = english
    client.headers["X-Lain-Language"] = "ru"
    move(runtime, "SCHOOL_LAB")
    for choice in ("INTRO", "ASK_CLASS", "ASK_STUDENT", "ASK_WHERE", "GOODBYE"):
        reply = client.post("/api/v1/prologue/talk/PROFESSOR", json={"choice": choice})
        assert reply.status_code == 200, reply.text
        assert not leaks(reply.json(), "talk"), leaks(reply.json(), "talk")
    move(runtime, "NIGHTCLUB")
    for choice in ("INTRO", "ASK_SCHOOL", "ASK_WIRED", "ASK_ADDRESS", "ASK_METHOD", "GOODBYE"):
        reply = client.post("/api/v1/prologue/talk/RYOKO", json={"choice": choice})
        assert not leaks(reply.json(), "talk"), leaks(reply.json(), "talk")
        text = reply.json()["result"]["text"]
        assert any("Ѐ" <= ch <= "ӿ" for ch in text), text


def test_a_new_russian_players_terminal_has_no_spanish(english):
    client, runtime = english
    client.headers["X-Lain-Language"] = "ru"
    move(runtime, "SCHOOL_LAB")
    talk_to_prologue_npc("PLAYER_1", "PROFESSOR", runtime.minute, "ASK_STUDENT")
    move(runtime, "NIGHTCLUB")
    talk_to_prologue_npc("PLAYER_1", "RYOKO", runtime.minute, "ASK_ADDRESS")
    move(runtime, "APARTMENT")
    assert submit_terminal_command("PLAYER_1", "telnet wired 23", runtime.minute)["accepted"]
    token = i18n.set_language("ru")
    try:
        process_wired_message_acknowledgement("MSG_BOOTSTRAP_001", "PLAYER_1", runtime.minute)
    finally:
        i18n.reset(token)
    state = client.get("/api/v1/player/state").json()
    assert not leaks(state["layer_three"], "layer_three"), leaks(state["layer_three"], "layer_three")
    packet = state["layer_three"]["packet"]
    for command in ("help", "man ttl", "man chain", "cat ~/correo/ttl1.eml", f"traceroute {packet}", "cat /net/hosts",
                    "whoami", "uptime", "cat /var/log/indara/diario", "lab", "lab show KU-01", "man kumo", "kumo",
                    "tokens hola mundo", "frobnicate"):
        reply = client.post("/api/v1/layer-three/shell", json={"host": "navi", "cwd": "/", "command": command})
        assert reply.status_code == 200, reply.text
        output = reply.json()["result"]["output"]
        offending = [line for line in output.splitlines() if SPANISH.search(line) and "Sesión" not in line
                     and "/indara/" not in line]
        assert not offending, (command, offending[:3])


def test_russian_players_type_the_english_commands_and_the_ai_answers_in_russian():
    token = i18n.set_language("ru")
    try:
        assert research.command("laboratorio") == "lab" and research.command("instituto") == "institute"
        state = {"name": "Olya", "turns": []}
        place = {"hostname": "navi", "cwd": "/", "ls": ""}
        system = kumo._messages(state, "привет", place, "", [], 2)[0]["content"]
        assert "Hablas en ruso" in system
        # The watcher writes Spanish and English: a Russian player reads the English.
        assert research.say({"es": "Hola", "en": "Hello"}) == "Hello"
    finally:
        i18n.reset(token)
