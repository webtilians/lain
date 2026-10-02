"""Hosted providers: operator-set request options (LAIN_LLM_EXTRA_BODY)."""
import io
import json

import pytest

from server.world_core import llm_dialogue
from server.world_core.player_conversation import (
    reply_to_player_conversation,
    start_player_conversation,
)
from tests.test_dialogue_d6 import setup_contact

GROQ_OPTIONS = '{"reasoning_effort": "none", "reasoning_format": "hidden"}'


def test_provider_options_reach_the_hosted_model(monkeypatch):
    sim, _ = setup_contact()
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "qwen/test")
    monkeypatch.setenv("LAIN_LLM_ENDPOINT", "https://api.example.org/openai/v1/chat/completions")
    monkeypatch.setenv("LAIN_LLM_ALLOW_REMOTE", "1")
    monkeypatch.setenv("LAIN_LLM_API_KEY", "test-only-value")
    monkeypatch.setenv("LAIN_LLM_EXTRA_BODY", GROQ_OPTIONS)
    seen = []

    def fake_network(request, timeout):
        seen.append(json.loads(request.data.decode("utf-8")))
        # Groq's Cloudflare front answers 403 (error 1010) to urllib's default agent.
        assert request.get_header("User-agent") == "LAIN-WorldCore/0.1"
        assert request.get_header("Authorization") == "Bearer test-only-value"
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "Sigo aquí, bajo la lluvia."}}]
        }).encode("utf-8"))

    monkeypatch.setattr(llm_dialogue, "urlopen", fake_network)
    first = start_player_conversation("AGENT_K", sim.minute)
    response = reply_to_player_conversation("AGENT_K", "ASK_IDENTITY", first["turn_id"], sim.minute)
    assert response["line"] == "Sigo aquí, bajo la lluvia."
    assert seen[0]["reasoning_effort"] == "none"
    assert seen[0]["reasoning_format"] == "hidden"
    assert seen[0]["model"] == "qwen/test"
    assert seen[0]["max_tokens"] == 170


def test_no_options_leaves_the_request_unchanged(monkeypatch):
    monkeypatch.delenv("LAIN_LLM_EXTRA_BODY", raising=False)
    body = {"model": "m", "messages": [], "temperature": 0}
    assert llm_dialogue.with_provider_options(body) == body


@pytest.mark.parametrize("value", [
    "not json",
    "[1, 2]",
    '{"model": "other"}',
    '{"messages": []}',
    '{"stream": true}',
    '{"tools": "x"}',
    '{"nested": {"a": 1}}',
])
def test_options_cannot_replace_the_conversation_or_inject_structures(monkeypatch, value):
    monkeypatch.setenv("LAIN_LLM_EXTRA_BODY", value)
    with pytest.raises(ValueError, match="INVALID_LLM_EXTRA_BODY"):
        llm_dialogue.with_provider_options({"model": "m", "messages": []})
