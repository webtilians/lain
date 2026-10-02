"""deploy/vps: files the Linux server reads must stay usable from a Windows checkout."""
import re
from pathlib import Path

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


def test_groq_helper_matches_what_the_engine_reads():
    helper = (VPS / "bin" / "lain-set-groq-key").read_text(encoding="utf-8")
    for name in ("LAIN_LLM_ENABLED", "LAIN_LLM_MODEL", "LAIN_LLM_ENDPOINT",
                 "LAIN_LLM_ALLOW_REMOTE", "LAIN_LLM_API_KEY", "LAIN_LLM_EXTRA_BODY"):
        assert name + "=" in helper
    assert "https://api.groq.com/openai/v1/chat/completions" in helper
    # The key is read silently and never passed on a command line.
    assert "read -rsp" in helper
