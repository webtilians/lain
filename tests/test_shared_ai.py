"""Owner relay routing, private projections and failure behavior; no live API."""
import io
import json
import time
from urllib.error import HTTPError

import pytest

from server.world_core import shared_ai, llm_dialogue, generated_entities, semantic_query
from tools.diagnose_llm import synthetic_context


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("LAIN_AI_GATEWAY_URL", "https://lain.example")
    monkeypatch.delenv("LAIN_AI_SESSION_FILE", raising=False)
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.delenv("LAIN_LLM_MODEL", raising=False)
    shared_ai._sessions.clear()
    shared_ai._cooldowns.clear()
    semantic_query._ask_local_model.cache_clear()


def response(value):
    return io.BytesIO(json.dumps(value).encode())


def test_automatic_session_has_no_provider_key_and_is_reused(monkeypatch, tmp_path):
    monkeypatch.setenv("LAIN_LLM_API_KEY", "must-never-leave-client")
    path = tmp_path / "ai-session.json"
    monkeypatch.setenv("LAIN_AI_SESSION_FILE", str(path))
    requests = []
    def network(request, timeout):
        requests.append(request)
        if request.full_url.endswith("/session"):
            assert request.get_header("Authorization") is None
            return response({"token": "anonymous-session-token", "expires_at": time.time() + 600})
        assert request.get_header("Authorization") == "Bearer anonymous-session-token"
        assert set(json.loads(request.data)) == {"messages", "purpose"}
        return response({"choices": [{"message": {"content": "Hola."}}]})
    monkeypatch.setattr(shared_ai, "_open", network)
    for _ in range(2):
        assert llm_dialogue._provider_reply(synthetic_context(), "Hola") == "Hola."
        shared_ai._sessions.clear()  # Simulate a launcher restart; reload the file.
    assert len(requests) == 3
    assert "must-never" not in path.read_text()


@pytest.mark.parametrize("url", ["http://lain.example", "https://user:secret@lain.example",
    "https://lain.example/?key=secret", "https://lain.example/#secret",
    "https://lain.example/path", "https://lain.example:8443", "not-a-url"])
def test_relay_requires_plain_https_origin(monkeypatch, url):
    monkeypatch.setenv("LAIN_AI_GATEWAY_URL", url)
    with pytest.raises(ValueError):
        llm_dialogue._endpoint()


def test_direct_remote_still_requires_explicit_key_and_permission(monkeypatch):
    monkeypatch.delenv("LAIN_AI_GATEWAY_URL")
    monkeypatch.setenv("LAIN_LLM_ENDPOINT", "https://provider.example/v1/chat/completions")
    monkeypatch.setenv("LAIN_LLM_ALLOW_REMOTE", "0")
    with pytest.raises(ValueError):
        llm_dialogue._endpoint()


def test_cooldown_prevents_dialogue_and_entity_hammering(monkeypatch):
    shared_ai._sessions["https://lain.example"] = {
        "origin": "https://lain.example", "token": "anonymous-session-token", "expires_at": time.time() + 600,
    }
    calls = []
    def limited(request, timeout):
        calls.append(request)
        raise HTTPError(request.full_url, 429, "private upstream body", {"Retry-After": "60"}, None)
    monkeypatch.setattr(shared_ai, "_open", limited)
    for purpose in ["dialogue", "entity"]:
        with pytest.raises(HTTPError):
            shared_ai.completion({"messages": []}, purpose, 10)
    assert len(calls) == 1


def test_invalid_session_is_not_retried_and_is_removed(monkeypatch, tmp_path):
    path = tmp_path / "ai-session.json"
    monkeypatch.setenv("LAIN_AI_SESSION_FILE", str(path))
    token = {"origin": "https://lain.example", "token": "anonymous-session-token", "expires_at": time.time() + 600}
    path.write_text(json.dumps(token))
    def invalid(request, timeout):
        raise HTTPError(request.full_url, 401, "invalid", {}, None)
    monkeypatch.setattr(shared_ai, "_open", invalid)
    with pytest.raises(HTTPError):
        shared_ai.completion({"messages": []}, "dialogue", 10)
    assert not path.exists()
    assert not shared_ai._sessions


def test_sessions_are_scoped_to_service_origin(monkeypatch, tmp_path):
    path = tmp_path / "ai-session.json"
    path.write_text(json.dumps({"origin": "https://other.example", "token": "other-service-private-token", "expires_at": time.time() + 600}))
    monkeypatch.setenv("LAIN_AI_SESSION_FILE", str(path))
    def network(request, timeout):
        assert request.full_url.endswith("/session")
        assert request.get_header("Authorization") is None
        return response({"token": "new-service-session-token", "expires_at": time.time() + 600})
    monkeypatch.setattr(shared_ai, "_open", network)
    assert shared_ai._session("https://lain.example", 5) == "new-service-session-token"


def test_private_context_retains_full_provenance_and_current_message(monkeypatch):
    context = synthetic_context()
    context.update({"resident": {"name": "K"}, "role": "OBSERVER", "received_station_echo": {"owner_id": "K"}})
    record = {"id": 18, "owner_id": "K", "text": "Antes tenía otro perro", "source_kind": "PLAYER_TESTIMONY",
        "source_actor_id": "PLAYER_1", "received_minute": 41, "origin_turn_id": 19,
        "parent_memory_id": 8, "location": "STATION", "interaction_id": "PRIVATE_K", "chronology_known": True}
    context["memory_records"] = [record]
    context["memory"] = [record["text"]]
    context["private_other_npc"] = "Nora's private knowledge must not be sent"
    seen = []
    def completion(body, purpose, timeout):
        seen.append(json.loads(body["messages"][1]["content"]))
        return json.dumps({"choices": [{"message": {"content": "Me lo contaste."}}]}).encode()
    monkeypatch.setattr(shared_ai, "completion", completion)
    llm_dialogue._provider_reply(context, "¿Y hoy?")
    projected = seen[0]["agent_context"]
    assert projected["memory_records"] == [record]
    assert projected["resident"] == context["resident"]
    assert projected["received_station_echo"] == context["received_station_echo"]
    assert projected["memory"] == []
    assert seen[0]["player_utterance"] == "¿Y hoy?"
    assert "Nora's private" not in json.dumps(seen)
    assert context["memory"] == [record["text"]]


def test_entity_and_optional_search_use_same_relay(monkeypatch):
    monkeypatch.setenv("LAIN_REALITY_GENERATION", "1")
    monkeypatch.setenv("LAIN_MEMORY_SEMANTIC", "1")
    seen = []
    def completion(body, purpose, timeout):
        seen.append(purpose)
        value = '{"proposal":null}' if purpose == "entity" else "estación, encuentro"
        return json.dumps({"choices": [{"message": {"content": value}}]}).encode()
    monkeypatch.setattr(shared_ai, "completion", completion)
    assert generated_entities.suggest_entity("K", "Hola", location="STATION") is None
    assert "encuentro" in semantic_query.expanded_query("¿Dónde nos vimos?")
    assert seen == ["entity", "search"]


def test_down_service_preserves_playable_fallback_without_leaking_error(monkeypatch, capsys):
    def offline(*args):
        raise HTTPError("https://lain.example", 503, "secret provider diagnostics", {}, None)
    monkeypatch.setattr(shared_ai, "completion", offline)
    monkeypatch.setenv("LAIN_LLM_TRACE", "1")
    result = llm_dialogue.generate_dialogue_reply(synthetic_context(), "FREE_TEXT", "¿Qué imaginas?")
    assert result.source != "LLM"
    assert "secret provider" not in result.text + capsys.readouterr().out


def test_redirects_never_forward_private_prompt():
    assert shared_ai._NoRedirect().redirect_request(None, None, 307, "", {}, "https://other.example") is None
