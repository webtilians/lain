"""No player data and no real provider in the local LLM diagnostic checks."""
import io
import json

from server.world_core import llm_dialogue
from tools import diagnose_llm


def test_synthetic_context_has_no_player_or_memory_from_database():
    context = diagnose_llm.synthetic_context()
    assert context["memory"] == []
    assert context["conversation"]["turns"] == []
    assert context["beliefs"]["nodes"] == []
    assert context["identity"]["id"] == "AGENT_DIAGNOSTIC"


def test_diagnostic_distinguishes_simple_provider_ok_from_lain_context_error(
    monkeypatch, capsys,
):
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_REALITY_GENERATION", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "synthetic-test")
    monkeypatch.setenv("LAIN_LLM_ENDPOINT",
                       "http://127.0.0.1:11434/v1/chat/completions")
    requests = []

    def fake_network(request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        requests.append(body)
        answer = "OK" if len(requests) == 1 else "x" * 701
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": answer}}],
        }).encode("utf-8"))

    monkeypatch.setattr(diagnose_llm, "urlopen", fake_network)
    monkeypatch.setattr(llm_dialogue, "urlopen", fake_network)
    assert diagnose_llm.run() == 1
    output = capsys.readouterr().out
    assert "LAIN_DIAG // SIMPLE_OK; CHARS = 2" in output
    assert "LAIN_DIAG // LAIN_CONTEXT_INVALID_RESPONSE_OR_CONFIGURATION" in output
    assert "x" * 100 not in output
    assert len(requests) == 2
    assert requests[0]["messages"][0]["content"] == "Responde OK."
    assert "SYNTHETIC_DIAGNOSTIC" in requests[1]["messages"][1]["content"]
