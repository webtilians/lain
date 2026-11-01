"""A lost player asking a neighbour how to play (the first players did) is sent to help and pista."""
from server.world_core import i18n
from server.world_core.llm_dialogue import asks_for_help, generate_dialogue_reply


def test_asking_for_commands_points_to_help_and_hint_in_every_language():
    for question in ("dime los principales comandos por favor", "¿Qué hago ahora?", "how do I play?",
                     "Как играть?", "что мне делать"):
        assert asks_for_help(question), question
    for question in ("¿Has visto a Ryoko?", "hola", "¿Qué sabes de NODE_07?", "Where is the school?"):
        assert not asks_for_help(question), question
    reply = generate_dialogue_reply({}, "FREE_TEXT", "dime los principales comandos por favor")
    assert reply.source == "RULE_GROUNDED" and "help" in reply.text and "pista" in reply.text
    token = i18n.set_language("en")
    try:
        assert "hint" in generate_dialogue_reply({}, "FREE_TEXT", "what do I do now?").text
    finally:
        i18n.reset(token)
    token = i18n.set_language("ru")
    try:
        assert "help" in generate_dialogue_reply({}, "FREE_TEXT", "Как играть?").text
    finally:
        i18n.reset(token)

