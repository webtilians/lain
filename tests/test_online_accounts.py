"""Self-service accounts: invite-gated registration, login, legacy password claim."""
import uuid

import pytest
from fastapi.testclient import TestClient

from server import api
from server.world_core import online, online_accounts
from server.world_core.simulation import Simulation


@pytest.fixture
def server(monkeypatch):
    for flag in ("LAIN_ONLINE", "LAIN_PROLOGUE_ENABLED", "LAIN_CITY_RESIDENTS_ENABLED"):
        monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("LAIN_WORLD_CLOCK", "0")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    monkeypatch.setenv("LAIN_SIGNUP_CODE", "Cable-Nodo-482")
    monkeypatch.delenv("LAIN_SIGNUP_OPEN", raising=False)
    for collection in (online._presence, online._connections, online._limits, online_accounts._attempts):
        collection.clear()
    runtime = Simulation()
    monkeypatch.setattr(api, "_runtime", runtime)
    return TestClient(api.app), runtime


def client_headers(token):
    return {"Authorization": "Bearer " + token, "X-Lain-Client": uuid.uuid4().hex}


def register(client, name="Mio", password="lluvia-neon", invite="cable-nodo-482"):
    return client.post("/api/v1/auth/register", json={"name": name, "password": password, "invite": invite})


def test_register_play_and_login_from_another_pc(server):
    client, runtime = server
    created = register(client, name="  Mio   Chan ")
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "Mio Chan" and body["actor_id"].startswith("PLAYER_")
    runtime.refresh_human_players()
    first = client_headers(body["token"])
    state = client.get("/api/v1/player/state", headers=first)
    assert state.status_code == 200 and state.json()["player"]["name"] == "Mio Chan"
    me = client.get("/api/v1/auth/me", headers=first).json()
    assert me["has_password"] and me["signup"] == "INVITE"
    online._connections.clear()
    again = client.post("/api/v1/auth/login", json={"name": "MIO chan", "password": "lluvia-neon"})
    assert again.status_code == 200 and again.json()["actor_id"] == body["actor_id"]
    # A login on a new PC signs the old token out.
    assert client.get("/api/v1/player/state", headers=client_headers(body["token"])).status_code == 401
    assert client.get("/api/v1/player/state", headers=client_headers(again.json()["token"])).status_code == 200


@pytest.mark.parametrize("invite,name,password,code,detail", [
    ("otro-codigo-111", "Mio", "lluvia-neon", 409, "INVALID_INVITE"),
    ("cable-nodo-482", "Nora", "lluvia-neon", 409, "INVALID_NAME"),
    ("cable-nodo-482", "xy", "lluvia-neon", 409, "INVALID_NAME"),
    ("cable-nodo-482", "Mio<script>", "lluvia-neon", 409, "INVALID_NAME"),
    ("cable-nodo-482", "Mio", "corta", 409, "WEAK_PASSWORD"),
])
def test_registration_rejects_bad_requests_without_creating_anyone(server, invite, name, password, code, detail):
    client, _ = server
    online_accounts.initialize()
    reply = register(client, name=name, password=password, invite=invite)
    assert reply.status_code == code and reply.json()["detail"] == detail
    from server.world_core.database import get_connection
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM online_logins").fetchone()[0] == 0


def test_names_are_unique_against_players_and_characters(server):
    client, _ = server
    assert register(client).status_code == 200
    assert register(client, name="mio").json()["detail"] == "NAME_TAKEN"
    from server.world_core.database import get_connection
    with get_connection() as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM agents WHERE controller_type!='HUMAN'")]
    resident = next(name for name in names if online_accounts._valid_name(name))
    assert register(client, name=resident.upper()).json()["detail"] == "NAME_TAKEN"


def test_closed_and_open_registration(server, monkeypatch):
    client, _ = server
    monkeypatch.delenv("LAIN_SIGNUP_CODE")
    assert register(client).status_code == 403
    monkeypatch.setenv("LAIN_SIGNUP_OPEN", "1")
    assert register(client, invite="").status_code == 200


def test_wrong_passwords_and_unknown_names_look_the_same_and_are_throttled(server):
    client, _ = server
    register(client)
    wrong = client.post("/api/v1/auth/login", json={"name": "Mio", "password": "otra-cosa"})
    unknown = client.post("/api/v1/auth/login", json={"name": "Nadie", "password": "otra-cosa"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "INVALID_LOGIN"}
    codes = [client.post("/api/v1/auth/login", json={"name": "Mio", "password": "x" * 8}).status_code for _ in range(12)]
    assert 429 in codes


def test_registration_is_limited_per_address(server, monkeypatch):
    client, _ = server
    monkeypatch.setenv("LAIN_SIGNUP_OPEN", "1")
    codes = [register(client, name=f"Jugador{n}x", invite="").status_code for n in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429


def test_owner_created_player_claims_a_password_then_logs_in(server):
    client, runtime = server
    actor, token = online.create_player("Enrique")
    runtime.refresh_human_players()
    headers = client_headers(token)
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me == {"name": "Enrique", "has_password": False, "actor_id": actor, "signup": "INVITE"}
    assert client.post("/api/v1/auth/password", headers=headers, json={"new": "mi-clave-nueva"}).json()["has_password"]
    # Changing it again needs the current one.
    assert client.post("/api/v1/auth/password", headers=headers,
                       json={"current": "mal", "new": "otra-clave-1"}).status_code == 401
    online._connections.clear()
    login = client.post("/api/v1/auth/login", json={"name": "enrique", "password": "mi-clave-nueva"})
    assert login.status_code == 200 and login.json()["actor_id"] == actor


def test_owner_reset_gives_a_working_password(server):
    client, _ = server
    actor = register(client).json()["actor_id"]
    password = online_accounts.reset_password("MIO")
    login = client.post("/api/v1/auth/login", json={"name": "Mio", "password": password})
    assert login.status_code == 200 and login.json()["actor_id"] == actor
    with pytest.raises(ValueError, match="UNKNOWN_PLAYER"):
        online_accounts.reset_password("Nadie")


def test_accounts_do_not_exist_offline(monkeypatch):
    monkeypatch.delenv("LAIN_ONLINE", raising=False)
    Simulation()
    reply = TestClient(api.app).post("/api/v1/auth/login", json={"name": "Mio", "password": "lluvia-neon"})
    assert reply.status_code == 404
