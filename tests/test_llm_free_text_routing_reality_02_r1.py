"""Reality 0.2-r1: opt-in free dialogue must not be shadowed by generic recall."""
from urllib.error import HTTPError

import pytest

from server.world_core import llm_dialogue


def context():
    return {
        "player_claims": [],
        "general_claims": [{"reported_text": "Mi perro se llama Eco."}],
        "knowledge_timeline": None,
        "experiences": {"request": None, "records": []},
        "beliefs": {"nodes": []},
    }


@pytest.mark.parametrize("utterance", [
    "¿Qué piensas de esa nueva presencia en la Wired?",
    "Quizá alguien esté despertando entre los cables.",
])
def test_enabled_free_text_reaches_model_even_with_generic_memories(
    monkeypatch, utterance,
):
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    seen = []
    def provider(ctx, message):
        seen.append(message)
        return "Tal vez una presencia nueva esté naciendo en la red."
    monkeypatch.setattr(llm_dialogue, "_provider_reply", provider)
    result = llm_dialogue.generate_dialogue_reply(
        context(), "FREE_TEXT", utterance,
    )
    assert seen == [utterance]
    assert result.source == "LLM_DIALOGUE"
    assert "presencia nueva" in result.text


def test_disabled_model_keeps_original_current_testimony_guard(monkeypatch):
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    monkeypatch.setattr(
        llm_dialogue, "_provider_reply",
        lambda *a: pytest.fail("provider must not run when disabled"),
    )
    result = llm_dialogue.generate_dialogue_reply(
        context(), "FREE_TEXT", "Mi perro se llama Eco.",
    )
    assert result.source == "CURRENT_TESTIMONY"


@pytest.mark.parametrize("utterance,expected_source", [
    ("Mi contraseña es Alfa123.", "CURRENT_TESTIMONY"),
    ("¿Necesito un código para acceder a NODE_07?", "RULE_GROUNDED"),
])
def test_critical_security_boundaries_remain_deterministic_with_model(
    monkeypatch, utterance, expected_source,
):
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setattr(
        llm_dialogue, "_provider_reply",
        lambda *a: pytest.fail("security boundary must not call provider"),
    )
    result = llm_dialogue.generate_dialogue_reply(
        context(), "FREE_TEXT", utterance,
    )
    assert result.source == expected_source


@pytest.mark.parametrize("error,code", [
    (HTTPError("http://localhost:11434/v1/chat/completions", 404,
               "private body should not appear", None, None), "HTTP_404"),
    (TimeoutError("private url / message should not appear"), "TIMEOUT"),
    (ConnectionRefusedError("secret server details"), "CONNECTION_ERROR"),
])
def test_provider_failure_logs_only_sanitized_reason(monkeypatch, capsys, error, code):
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_TRACE", "1")
    def failure(*_):
        raise error
    monkeypatch.setattr(llm_dialogue, "_provider_reply", failure)
    reply = llm_dialogue.generate_dialogue_reply(
        context(), "FREE_TEXT", "Hola, ¿qué hay en los cables?",
    )
    output = capsys.readouterr().out
    assert reply.source == "DETERMINISTIC_FALLBACK"
    assert "LLM // REQUESTED" in output
    assert f"LLM // FALLBACK_{code}" in output
    assert "private" not in output
    assert "secret" not in output
    assert "Hola" not in output


def test_explicit_current_statement_is_kept_grounded_even_with_model(monkeypatch):
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setattr(
        llm_dialogue, "_provider_reply",
        lambda *a: pytest.fail("an explicit personal statement must be attributed"),
    )
    reply = llm_dialogue.generate_dialogue_reply(
        context(), "FREE_TEXT", "Mi perro se llama Eco.",
    )
    assert reply.source == "CURRENT_TESTIMONY"
    assert "Mi perro se llama Eco" in reply.text
