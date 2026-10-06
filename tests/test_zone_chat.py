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
