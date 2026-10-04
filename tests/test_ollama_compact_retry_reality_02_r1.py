"""Ollama HTTP 400 retry keeps current utterance but shrinks accumulated context."""
import io
import json
from urllib.error import HTTPError

from server.world_core import llm_dialogue


def full_context():
    return {
        "identity": {
            "id": "AGENT_K", "name": "K", "faction": "PROTOCOL",
            "controller_type": "AI",
        },
        "situation": {"location": "STATION", "conversation_with": {"id": "PLAYER_1"}},
        "beliefs": {
            "nodes": [{"node_id": f"NODE_{i}", "blob": "n" * 120} for i in range(30)],
            "actors": [{"subject_actor_id": f"A{i}", "blob": "a" * 120} for i in range(20)],
            "situations": [{"situation_id": f"S{i}", "blob": "s" * 120} for i in range(20)],
        },
        "memory": ["m" * 500 for _ in range(12)],
        "memory_records": [
            {
                "text": "r" * 500, "source_kind": "PLAYER_TESTIMONY",
                "source_actor_id": "PLAYER_1", "received_minute": i,
                "location": "STATION", "id": i, "owner_id": "AGENT_K",
                "origin_turn_id": i, "parent_memory_id": None,
                "interaction_id": "I", "chronology_known": True,
            }
            for i in range(12)
        ],
        "player_claims": [],
        "general_claims": [],
        "knowledge_timeline": {"versions": [{"x": "z" * 1000}] * 20},
        "experiences": {
            "request": None,
            "records": [{"kind": "ENCOUNTER", "x": "e" * 500} for _ in range(20)],
        },
        "goals": {"current": "OBSERVE_WORLD"},
        "conversation": {
            "id": "CONTACT_TEST", "status": "OPEN",
            "turns": [
                {"speaker_id": "PLAYER_1", "text": "t" * 600, "source": "PLAYER_FREE_TEXT"}
                for _ in range(16)
            ],
        },
    }


def test_http_400_retries_once_with_compact_context(monkeypatch, capsys):
    monkeypatch.setenv("LAIN_LLM_MODEL", "lain-qwen7b")
    monkeypatch.setenv("LAIN_LLM_ENDPOINT",
                       "http://127.0.0.1:11434/v1/chat/completions")
    monkeypatch.setenv("LAIN_LLM_TRACE", "1")
    payloads = []

    def fake_network(request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        payloads.append(body)
        if len(payloads) == 1:
            raise HTTPError(request.full_url, 400, "too large", None, None)
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "Ahora sí respondo."}}],
        }).encode("utf-8"))

    monkeypatch.setattr(llm_dialogue, "urlopen", fake_network)
    current = "¿Qué imaginas al otro lado de la Wired?"
    reply = llm_dialogue._provider_reply(full_context(), current)
    assert reply == "Ahora sí respondo."
    assert len(payloads) == 2

    first = json.loads(payloads[0]["messages"][1]["content"])
    second = json.loads(payloads[1]["messages"][1]["content"])
    assert first["player_utterance"] == current == second["player_utterance"]
    compact = second["agent_context"]
    assert len(compact["memory"]) == 4
    assert len(compact["memory_records"]) == 4
    assert len(compact["beliefs"]["nodes"]) == 8
    assert len(compact["conversation"]["turns"]) == 6
    assert compact["knowledge_timeline"] is None
    assert len(compact["experiences"]["records"]) == 4
    assert len(payloads[1]["messages"][1]["content"]) < len(payloads[0]["messages"][1]["content"])

    output = capsys.readouterr().out
    assert "LLM // RETRY_COMPACT_HTTP_400" in output
    assert "LLM // COMPACT_RESPONSE_RECEIVED" in output
    assert "too large" not in output


def test_second_http_400_is_not_retried_forever(monkeypatch):
    monkeypatch.setenv("LAIN_LLM_MODEL", "lain-qwen7b")
    monkeypatch.setenv("LAIN_LLM_ENDPOINT",
                       "http://127.0.0.1:11434/v1/chat/completions")
    calls = 0

    def always_bad(request, timeout):
        nonlocal calls
        calls += 1
        raise HTTPError(request.full_url, 400, "still bad", None, None)

    monkeypatch.setattr(llm_dialogue, "urlopen", always_bad)
    try:
        llm_dialogue._provider_reply(full_context(), "Prueba")
    except HTTPError as error:
        assert error.code == 400
    else:
        raise AssertionError("second HTTP 400 must propagate")
    assert calls == 2
