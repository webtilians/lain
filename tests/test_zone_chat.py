"""One chat per zone: residents speak in it like anyone else, and nothing says who is who."""
import pytest

from server.world_core import online, zone_chat
from server.world_core.database import get_connection
from tests.test_online_world import conversation, place, presence, say, world  # noqa: F401 (fixtures)

PLAZA = "APARTMENT_DISTRICT"


@pytest.fixture
def plaza(world, monkeypatch):  # noqa: F811
    """Alice in the plaza with one resident, Hideo; the chat answers at once."""
    client, runtime, alice, bob, headers = world
    monkeypatch.setattr(zone_chat, "SYNC", True)
    zone_chat._last_line.clear()
    zone_chat._next_ambient.clear()
    zone_chat._partner.clear()
    with get_connection() as c:
        c.execute("UPDATE agents SET location='SCHOOL' WHERE controller_type='RESIDENT' AND location=?", (PLAZA,))
        c.execute("INSERT INTO agents(id,name,faction,location,goal,energy,controller_type) "
                  "VALUES('RESIDENT_T','Hideo Prueba','CIVILIAN',?,'DAILY_LIFE',1.0,'RESIDENT')", (PLAZA,))
    place(runtime, alice, PLAZA)
    assert presence(client, headers[alice], location=PLAZA).status_code == 200
    return client, runtime, alice, bob, headers


def chat(client, headers, text):
    response = client.post("/api/v1/online/chat", headers=headers, json={"text": text})
    assert response.status_code == 200, response.text


def lines(client, headers, location=PLAZA):
    return presence(client, headers, location=location).json()["chat"]


def test_a_resident_named_in_the_chat_answers_like_anyone_else(plaza):
    client, runtime, alice, bob, headers = plaza
    chat(client, headers[alice], "Hideo, ¿has visto a Ryoko?")
    said = lines(client, headers[alice])
    assert [line["name"] for line in said] == ["Alice", "Hideo"], said
    assert said[1]["text"]
    # The same shape for both: a name, a text and an opaque key, never an actor id.
    assert set(said[0]) == set(said[1]) == {"id", "who", "name", "text"}
    assert said[0]["who"] != said[1]["who"]
    assert "RESIDENT" not in str(said) and alice not in str(said)
    with get_connection() as c:
        memory = c.execute("SELECT memory FROM agent_memory WHERE agent_id='RESIDENT_T'").fetchall()
    assert any("¿has visto a Ryoko?" in row[0] for row in memory), "the resident does not remember what was said"


def test_alone_a_question_to_the_room_gets_an_answer(plaza, monkeypatch):
    client, runtime, alice, bob, headers = plaza
    monkeypatch.setattr(zone_chat.random, "random", lambda: 0.0)
    chat(client, headers[alice], "¿Alguien sabe dónde está el colegio?")
    assert [line["name"] for line in lines(client, headers[alice])] == ["Alice"], "without the AI, nobody answers the room"
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setattr(zone_chat, "reply_text", lambda *args: "Al final de la calle, a la izquierda.")
    chat(client, headers[alice], "¿Alguien sabe dónde está el colegio?")
    said = lines(client, headers[alice])
    assert [line["name"] for line in said] == ["Alice", "Alice", "Hideo"]
    assert said[-1]["text"] == "Al final de la calle, a la izquierda."


def test_without_the_ai_a_named_resident_answers_like_someone_busy(plaza):
    client, runtime, alice, bob, headers = plaza
    chat(client, headers[alice], "Hideo, ¿me oyes?")
    answer = lines(client, headers[alice])[-1]["text"]
    assert answer in zone_chat.SHORT_ANSWERS, answer


def test_with_people_around_residents_only_answer_when_named(plaza, monkeypatch):
    client, runtime, alice, bob, headers = plaza
    monkeypatch.setattr(zone_chat.random, "random", lambda: 0.0)
    place(runtime, bob, PLAZA)
    presence(client, headers[bob], location=PLAZA)
    chat(client, headers[alice], "¿Vamos al colegio?")
    assert [line["name"] for line in lines(client, headers[bob])] == ["Alice"]
    chat(client, headers[alice], "Lo que tú digas")
    assert len(lines(client, headers[bob])) == 2, "a plain line to the room is left to the people"


def test_a_resident_does_not_answer_twice_in_a_row(plaza):
    client, runtime, alice, bob, headers = plaza
    chat(client, headers[alice], "Hideo")
    chat(client, headers[alice], "hideo, otra cosa")
    assert [line["name"] for line in lines(client, headers[alice])] == ["Alice", "Hideo", "Alice"]


def test_what_other_players_say_never_reaches_the_ai(plaza):
    client, runtime, alice, bob, headers = plaza
    place(runtime, bob, PLAZA)
    presence(client, headers[bob], location=PLAZA)
    chat(client, headers[bob], "Mi contraseña del banco es 1234")
    chat(client, headers[alice], "Hideo, ¿qué tal?")
    heard = online.recent_lines(PLAZA, {alice, "RESIDENT_T"})
    assert heard[0] == "Alice: Hideo, ¿qué tal?" and not any("banco" in line for line in heard)


def add_resident(actor, name, location=PLAZA):
    with get_connection() as c:
        c.execute("INSERT INTO agents(id,name,faction,location,goal,energy,controller_type) "
                  "VALUES(?,?,'CIVILIAN',?,'DAILY_LIFE',1.0,'RESIDENT')", (actor, name, location))


def chat_near(client, headers, text, near):
    response = client.post("/api/v1/online/chat", headers=headers, json={"text": text, "near": near})
    assert response.status_code == 200, response.text


def test_only_residents_on_screen_take_part(plaza, monkeypatch):
    client, runtime, alice, bob, headers = plaza
    add_resident("RESIDENT_U", "Daichi Lejos")
    # Hideo is on Alice's screen; Daichi is somewhere else in the same zone.
    chat_near(client, headers[alice], "Daichi, ¿estás por ahí?", ["RESIDENT_T"])
    assert [line["name"] for line in lines(client, headers[alice])] == ["Alice"], "someone out of sight answers"
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setattr(zone_chat.random, "random", lambda: 0.0)
    monkeypatch.setattr(zone_chat, "reply_text", lambda resident, *args: resident)
    chat_near(client, headers[alice], "¿qué haces?", ["RESIDENT_T", "RESIDENT_U"])
    assert lines(client, headers[alice])[-1] == {**lines(client, headers[alice])[-1], "name": "Hideo"},         "a question to the room is not answered by the nearest"


def test_who_was_talking_with_you_keeps_answering(plaza, monkeypatch):
    client, runtime, alice, bob, headers = plaza
    add_resident("RESIDENT_U", "Daichi Cerca")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setattr(zone_chat, "REPLY_GAP", 0.0)
    monkeypatch.setattr(zone_chat.random, "random", lambda: 0.0)
    monkeypatch.setattr(zone_chat, "reply_text", lambda resident, *args: "Aquí, limpiando.")
    near = ["RESIDENT_T", "RESIDENT_U"]
    chat_near(client, headers[alice], "Daichi, ¿qué haces?", near)
    chat_near(client, headers[alice], "¿y dónde vives?", near)
    chat_near(client, headers[alice], "vale, gracias", near)
    said = [line["name"] for line in lines(client, headers[alice])]
    assert said == ["Alice", "Daichi", "Alice", "Daichi", "Alice", "Daichi"], said
    # Walking away from them ends it: the nearest one answers the next question instead.
    chat_near(client, headers[alice], "¿alguien sabe la hora?", ["RESIDENT_T"])
    assert lines(client, headers[alice])[-1]["name"] == "Hideo"


def test_a_resident_speaks_on_their_own_only_near_someone(plaza, monkeypatch):
    client, runtime, alice, bob, headers = plaza
    add_resident("RESIDENT_U", "Daichi Lejos")
    monkeypatch.setattr(zone_chat, "ambient_text", lambda resident, location: "Qué frío hace hoy.")
    assert presence(client, headers[alice], location=PLAZA, near=["RESIDENT_U"]).status_code == 200
    zone_chat.ambient_tick(now=0.0)
    assert zone_chat.ambient_tick(now=zone_chat.AMBIENT_EVERY * 2) == [(PLAZA, "RESIDENT_U")]
    presence(client, headers[alice], location=PLAZA, near=[])
    assert zone_chat.ambient_tick(now=zone_chat.AMBIENT_EVERY * 5) == [], "a resident nobody can see speaks up"


def test_every_speaker_can_be_found_on_screen(plaza):
    client, runtime, alice, bob, headers = plaza
    place(runtime, bob, PLAZA)
    presence(client, headers[bob], location=PLAZA)
    chat(client, headers[alice], "Hideo, hola")
    seen = presence(client, headers[bob], location=PLAZA).json()
    said = {line["name"]: line["who"] for line in seen["chat"]}
    assert said["Alice"] == next(player["who"] for player in seen["players"] if player["name"] == "Alice")
    actors = client.get("/api/v1/player/state", headers=headers[bob]).json()["visible_actors"]
    assert said["Hideo"] == next(actor["who"] for actor in actors if actor["id"] == "RESIDENT_T")
    assert presence(client, headers[alice], location=PLAZA).json()["me"] == said["Alice"]


def test_a_reply_that_repeats_the_question_loses_the_echo():
    assert zone_chat.unecho("Me preguntas cómo me va el día. Pues bien, tirando.") == "Pues bien, tirando."
    assert zone_chat.unecho("Me preguntas si quiero jugar al pádel. No creo que pueda.") == "No creo que pueda."
    assert zone_chat.unecho("You ask how my day is going. Busy, as always.") == "Busy, as always."
    assert zone_chat.unecho("Me preguntas demasiado.") == "Me preguntas demasiado.", "nothing left after it: kept"
    assert zone_chat.unecho("Bien, ¿y tú?") == "Bien, ¿y tú?"


def test_the_chat_asks_the_ai_to_write_like_a_person(monkeypatch):
    from server.world_core import llm_dialogue
    seen = {}

    def fake_post(request, timeout):
        seen["system"] = __import__("json").loads(request.data)["messages"][0]["content"]
        raise OSError("no network in tests")
    monkeypatch.setenv("LAIN_LLM_MODEL", "test")
    monkeypatch.setattr(llm_dialogue, "urlopen", fake_post)
    context = {"identity": {}, "situation": {"zone_chat": []}, "beliefs": {"nodes": [], "actors": [], "situations": []},
               "memory": [], "goals": {}, "conversation": None}
    with pytest.raises(OSError):
        llm_dialogue._provider_reply(context, "¿quieres jugar al pádel?")
    assert "CHAT DE GRUPO" in seen["system"] and "Me preguntas" in seen["system"]


def test_names_are_found_however_they_are_written(plaza):
    residents = [("RESIDENT_A", "Aiko Tanaka"), ("RESIDENT_B", "Óscar Ruiz")]
    assert zone_chat.addressed("eh, AIKO!", residents) == [residents[0]]
    assert zone_chat.addressed("oscar ven", residents) == [residents[1]]
    assert zone_chat.addressed("Aikoko no", residents) == []
    assert zone_chat.first_name("Hideo Sakamoto") == "Hideo"


def test_now_and_then_a_resident_speaks_on_their_own(plaza, monkeypatch):
    client, runtime, alice, bob, headers = plaza
    monkeypatch.setattr(zone_chat, "ambient_text", lambda resident, location: "¿Alguien ha visto pasar el autobús?")
    assert zone_chat.ambient_tick(now=0.0) == [], "the first line of a zone waits a while"
    later = zone_chat.AMBIENT_EVERY * 2
    assert zone_chat.ambient_tick(now=later) == [(PLAZA, "RESIDENT_T")]
    assert lines(client, headers[alice])[-1] == {**lines(client, headers[alice])[-1], "name": "Hideo",
                                                  "text": "¿Alguien ha visto pasar el autobús?"}
    assert zone_chat.ambient_tick(now=later + 5) == [], "not again right away"


def test_without_the_ai_residents_do_not_make_lines_up():
    assert zone_chat.ambient_text("RESIDENT_T", PLAZA) is None


def test_talking_to_someone_is_heard_in_the_zone_chat(world):  # noqa: F811
    client, runtime, alice, bob, headers = world
    k_place = runtime.all_agents["AGENT_K"].location
    place(runtime, alice, k_place)
    place(runtime, bob, k_place)
    presence(client, headers[alice], location=k_place)
    presence(client, headers[bob], location=k_place)
    opened = conversation(client, headers[alice])
    say(client, headers[alice], opened, "K, ¿qué ha pasado en la estación?")
    heard = lines(client, headers[bob], location=k_place)
    assert [line["name"] for line in heard] == ["Alice", "K"], heard
    assert heard[0]["text"] == "K, ¿qué ha pasado en la estación?"


def test_answers_arrive_later_from_the_worker(plaza, monkeypatch):
    import time
    client, runtime, alice, bob, headers = plaza
    monkeypatch.setattr(zone_chat, "SYNC", False)
    monkeypatch.setattr(zone_chat, "MIN_DELAY", 0.0)
    monkeypatch.setattr(zone_chat, "MAX_DELAY", 0.05)
    chat(client, headers[alice], "Hideo, buenas noches")
    for _ in range(60):
        if len(lines(client, headers[alice])) == 2:
            break
        time.sleep(0.05)
    said = lines(client, headers[alice])
    assert [line["name"] for line in said] == ["Alice", "Hideo"]
    assert said[1]["text"] in zone_chat.SHORT_ANSWERS
