"""English free text: the same grounded memory as Spanish, answered in English."""
import pytest

from server.world_core import i18n
from server.world_core.autobiographical_memory import timeline_request
from server.world_core.dialogue_guard import asserts_unverified_node_access_code, misattributes_player_password
from server.world_core.free_conversation import say_to_player_conversation
from server.world_core.general_claims import parse_personal_statement, requested_topic
from server.world_core.player_claims import extract_password_claim
from server.world_core.shared_experiences import experience_request
from tests.test_dialogue_d9 import contact


@pytest.fixture
def english():
    token = i18n.set_language("en")
    yield
    i18n.reset(token)


@pytest.mark.parametrize(("statement", "topic", "value"), [
    ("My dog is called Tango.", "dog", "Tango"),
    ("my dog's name is Lupo", "dog", "Lupo"),
    ("My favourite colour is blue.", "favourite colour", "blue"),
    ("My dog is now called Bimba!", "dog", "Bimba"),
    ("My name is Ana", "name", "Ana"),
])
def test_english_personal_statements(statement, topic, value):
    key, _, parsed, quote = parse_personal_statement(statement)
    assert (key, parsed, quote) == (topic, value, statement)


@pytest.mark.parametrize("statement", [
    "My password is REAL-123.",
    "My dog is a spy because he controls NODE_07.",
    "Is my dog called Tango?",
    "They told me my dog is called Tango.",
])
def test_english_statements_that_are_not_personal_facts(statement):
    assert parse_personal_statement(statement) is None


@pytest.mark.parametrize("question", [
    "What's my dog's name?", "what is my dog called?", "Do you remember what I told you about my dog?",
    "What do you know about my dog?",
])
def test_english_questions_find_the_topic(question):
    assert requested_topic(question) == "dog"


def test_english_passwords_timelines_experiences_and_guards():
    assert extract_password_claim("my password is Killo13") == "Killo13"
    assert extract_password_claim("My new password: Rex-99") == "Rex-99"
    assert extract_password_claim("Mi contraseña es Tango7") == "Tango7"
    assert timeline_request("What did I first tell you about my dog?") == ("dog", "first")
    assert timeline_request("what did I tell you before about my dog?") == ("dog", "previous")
    assert timeline_request("What's my dog called now?") == ("dog", "current")
    assert experience_request("What happened last time we met?") == {"mode": "encounter"}
    assert experience_request("what happened the last time we were at the station?")["location"] == "STATION"
    assert experience_request("Were you with me when we investigated NODE_07?") == {"mode": "shared", "target": "NODE_07"}
    assert misattributes_player_password("As I told you, your password is Tango7.")
    assert asserts_unverified_node_access_code("You need the password to access NODE_07.")
    assert not asserts_unverified_node_access_code("NODE_07 is pulsing near the station.")


def test_english_player_is_remembered_and_answered_in_english(english):
    sim, _, greeting = contact()
    earlier = say_to_player_conversation("AGENT_K", "My dog is called Tango.", greeting["turn_id"], sim.minute)
    latest = say_to_player_conversation("AGENT_K", "My dog is now called Lupo.", earlier["turn_id"], sim.minute)
    answer = say_to_player_conversation("AGENT_K", "What's my dog's name?", latest["turn_id"], sim.minute)
    assert answer["response_source"] == "GROUNDED_RECALL"
    assert "Lupo" in answer["line"] and "Tango" not in answer["line"]
    assert "dijiste" not in answer["line"] and "told me" in answer["line"]
