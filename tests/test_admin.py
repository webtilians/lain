"""The owner's server panel: only reachable through the SSH tunnel, read only, no chat contents."""
import re
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server import api
from server.world_core import admin, online
from tests.test_online_world import place, presence, world  # noqa: F401 (fixture)


def test_only_a_loopback_request_without_proxy_headers_gets_in():
    assert admin.local_request("127.0.0.1", {})
    assert admin.local_request("::1", {})
    assert not admin.local_request("127.0.0.1", {"x-forwarded-for": "203.0.113.9"})
    assert not admin.local_request("203.0.113.9", {})
    assert not admin.local_request(None, {})


def tunnel(headers=None):
    """A request as the SSH tunnel delivers it: loopback, no proxy headers."""
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers=headers or {})


def field_names(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from field_names(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from field_names(item)


def test_panel_is_hidden_from_public_requests(world):
    client, *_ = world
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/data").status_code == 404
    with pytest.raises(HTTPException):
        api.admin_data(tunnel({"x-forwarded-for": "203.0.113.9"}))


def test_panel_shows_connections_progress_and_no_chat_text(world):
    client, runtime, alice, bob, headers = world
    online._session_seen.clear()
    for actor in (alice, bob):
        place(runtime, actor, "APARTMENT_DISTRICT")
        assert presence(client, headers[actor]).status_code == 200
    assert client.post("/api/v1/online/chat", headers=headers[alice], json={"text": "secreto"}).status_code == 200
    assert "panel del servidor" in api.admin_page(tunnel()).body.decode("utf-8")
    data = api.admin_data(tunnel())
    assert {item["name"] for item in data["connected"]} == {"Alice", "Bob"}
    assert {item["location"] for item in data["connected"]} == {"APARTMENT_DISTRICT"}
    players = {item["name"]: item for item in data["players"]}
    assert players["Alice"]["sessions"] == 1 and players["Alice"]["fragments"] == 0
    assert any(session["name"] == "Bob" and session["open"] for session in data["sessions"])
    assert data["server"]["chat_messages"] == 1 and "secreto" not in str(data)
    # Field names, not words: the server's last commit message may say anything ("resaltado").
    assert not any("hash" in key or "salt" in key for key in field_names(data))


def test_a_long_gap_opens_a_new_session(world, monkeypatch):
    client, runtime, alice, bob, headers = world
    online._session_seen.clear()
    place(runtime, alice, "APARTMENT_DISTRICT")
    presence(client, headers[alice])
    later = online.time.time() + online.SESSION_GAP + 30
    with monkeypatch.context() as clock:
        clock.setattr(online.time, "time", lambda: later)
        online._session_seen.clear()
        presence(client, headers[alice])
    assert {item["name"]: item for item in admin.overview()["players"]}["Alice"]["sessions"] == 2


def test_the_panel_script_runs(tmp_path):
    """The whole panel stops loading on one JavaScript syntax error (a variable declared twice did)."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = tmp_path / "panel.js"
    script.write_text(re.search(r"<script>(.*)</script>", admin.PAGE, re.S).group(1), encoding="utf-8")
    checked = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr

