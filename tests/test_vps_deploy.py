"""deploy/vps: files the Linux server reads must stay usable from a Windows checkout."""
import importlib.util
import io
import json
import re
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
VPS = ROOT / "deploy" / "vps"


def test_server_scripts_use_unix_line_endings_and_shebangs():
    for path in [VPS / "setup.sh", *sorted((VPS / "bin").iterdir())]:
        data = path.read_bytes()
        assert b"\r" not in data, path
        assert data.startswith(b"#!/usr/bin/env bash\n"), path
    for path in [*sorted((VPS / "systemd").iterdir()), VPS / "Caddyfile.template"]:
        assert b"\r" not in path.read_bytes(), path


def test_service_runs_the_real_online_server_command():
    unit = (VPS / "systemd" / "lain.service").read_text(encoding="utf-8")
    command = re.search(r"^ExecStart=(.+)$", unit, re.M).group(1).split()
    assert command[1:4] == ["-m", "tools.online_server", "--data-dir"]
    assert command[5:] == ["serve", "--host", "127.0.0.1", "--port", "8000"]
    assert "ReadWritePaths=/var/lib/lain" in unit
    caddy = (VPS / "Caddyfile.template").read_text(encoding="utf-8")
    assert "reverse_proxy 127.0.0.1:8000" in caddy


def test_ai_key_helper_matches_what_the_engine_reads():
    helper = (VPS / "bin" / "lain-set-ai-key").read_text(encoding="utf-8")
    for name in ("LAIN_LLM_ENABLED", "LAIN_LLM_MODEL", "LAIN_LLM_ENDPOINT",
                 "LAIN_LLM_ALLOW_REMOTE", "LAIN_LLM_API_KEY", "LAIN_LLM_EXTRA_BODY"):
        assert name + "=" in helper
    # The key is read silently and reaches Python only through the environment.
    assert "read -rsp" in helper
    assert 'LAIN_TEST_KEY="$key"' in helper


def _probe_module():
    spec = importlib.util.spec_from_file_location("ai_probe", VPS / "ai_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeGoogle:
    """Answers like the Gemini OpenAI-compatible API, scripted per model."""

    def __init__(self, models, replies):
        self.models, self.replies, self.calls = models, replies, []

    def __call__(self, request, timeout):
        assert request.get_header("Authorization") == "Bearer test-only-value"
        assert request.get_header("User-agent") == "LAIN-WorldCore/0.1"
        if request.full_url.endswith("/models"):
            return io.BytesIO(json.dumps({"data": [{"id": m} for m in self.models]}).encode())
        body = json.loads(request.data)
        self.calls.append((body["model"], body.get("reasoning_effort")))
        assert body["max_tokens"] == 170
        outcome = self.replies.get((body["model"], body.get("reasoning_effort")), 404)
        if isinstance(outcome, int):
            raise HTTPError(request.full_url, outcome, "error", {}, io.BytesIO(b"{}"))
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": outcome}}]}).encode())


def test_gemini_probe_skips_models_that_think_away_the_answer():
    probe = _probe_module()
    google = FakeGoogle(
        ["models/gemini-2.5-flash", "models/gemini-flash-lite-latest", "models/gemini-2.5-flash-preview-tts",
         "models/text-embedding-004"],
        {
            ("gemini-flash-lite-latest", "none"): 400,   # thinking cannot be disabled
            ("gemini-flash-lite-latest", None): "",       # budget spent thinking
            ("gemini-2.5-flash", "none"): "Soy K. Te estaba esperando.",
        },
    )
    assert probe.probe("gemini", "test-only-value", google) == 'OK gemini-2.5-flash {"reasoning_effort":"none"}'
    assert google.calls[0][0] == "gemini-flash-lite-latest"
    assert all("tts" not in model and "embedding" not in model for model, _ in google.calls)
    assert probe.endpoint("gemini") == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def test_gemini_probe_reports_bad_keys_and_rate_limits_without_saving():
    probe = _probe_module()
    assert probe.probe("gemini", "test-only-value", FakeGoogle(["models/gemini-2.5-flash"], {
        ("gemini-2.5-flash", "none"): 401})) == "ERROR KEY"
    assert probe.probe("gemini", "test-only-value", FakeGoogle(["models/gemini-2.5-flash"], {
        ("gemini-2.5-flash", "none"): 429, ("gemini-2.5-flash", None): 429})) == "ERROR LIMIT"


def test_groq_probe_keeps_the_qwen_reasoning_switches():
    probe = _probe_module()
    google = FakeGoogle([], {("qwen/qwen3.8-27b", "none"): "Hola."})
    assert probe.probe("groq", "test-only-value", google) ==         'OK qwen/qwen3.8-27b {"reasoning_effort":"none","reasoning_format":"hidden"}'


def test_server_python_lives_outside_the_checkout():
    # The repository tracks a Windows .venv/pyvenv.cfg; git removes it from a
    # sparse checkout on update, which broke a venv kept at /opt/lain/.venv.
    for path in [VPS / "setup.sh", *(VPS / "bin").iterdir(), *(VPS / "systemd").iterdir()]:
        assert "/opt/lain/.venv/" not in path.read_text(encoding="utf-8"), path
