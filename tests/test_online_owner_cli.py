"""Exercise the owner's actual command in a disposable directory."""

import os
from pathlib import Path
import subprocess
import sys


def run_owner(directory, *arguments):
    environment = {k: v for k, v in os.environ.items() if not k.startswith("LAIN_")}
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.online_server",
            "--data-dir",
            str(directory),
            *arguments,
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        encoding="utf-8",
        timeout=45,
    )


def test_list_before_first_player_is_read_only(tmp_path):
    directory = tmp_path / "new-host"
    result = run_owner(directory, "list-players")
    assert result.returncode == 0, result.stderr
    assert "Todavía no hay jugadores" in result.stdout
    assert not directory.exists()


def test_list_shows_existing_players_without_credentials(tmp_path):
    import json

    created = run_owner(
        tmp_path, "add-player", "--name", "Alice", "--url", "https://example.com"
    )
    assert created.returncode == 0, created.stderr
    private_file = next((tmp_path / "access").glob("*/lain-online.json"))
    token = json.loads(private_file.read_text(encoding="utf-8"))["player_token"]
    listed = run_owner(tmp_path, "list-players")
    assert listed.returncode == 0, listed.stderr
    assert "Alice ACTIVO" in listed.stdout
    assert token not in created.stdout + created.stderr + listed.stdout + listed.stderr
