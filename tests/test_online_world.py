"""Two authenticated clients in one world; identities, privacy and persistence."""

from concurrent.futures import ThreadPoolExecutor
import json
import importlib
import threading
import uuid

from fastapi.testclient import TestClient
import pytest

from server import api
from server.world_core import online, database, free_conversation
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.llm_dialogue import DialogueReply
from server.world_core.messages import initial_message_id
from server.world_core.realtime import WorldClock
from server.world_core.simulation import Simulation


def test_online_npc_recognizes_the_current_players_signal_testimony(world):
    from server.world_core.beliefs import save_belief
    from server.world_core.models import NodeBelief

    client, runtime, alice, bob, headers = world
    for actor in (alice, bob, "AGENT_K"):
        place(runtime, actor, "APARTMENT_DISTRICT")
    save_belief(
        NodeBelief(
            alice, "NODE_07", "STATION", 0.6, 0.85, "DIRECT_PERCEPTION", runtime.minute
        )
    )
    turn = conversation(client, headers[alice])
    for expected in ("testimonio", "Recuerdo"):
        response = client.post(
            "/api/v1/player/conversations/AGENT_K/reply",
            headers=headers[alice],
            json={"choice_id": "TELL_OBSERVED", "after_turn_id": turn["turn_id"]},
        )
        assert response.status_code == 200, response.text
        turn = response.json()
        assert expected in turn["line"]
    other = conversation(client, headers[bob])
    response = client.post(
        "/api/v1/player/conversations/AGENT_K/reply",
        headers=headers[bob],
        json={"choice_id": "ASK_SIGNAL", "after_turn_id": other["turn_id"]},
    )
    assert response.status_code == 200, response.text
    assert "recuerdo" not in response.json()["line"].lower()


def test_chat_ids_remain_unique_when_server_memory_is_restarted(world):
    client, runtime, alice, bob, headers = world
    for actor in (alice, bob):
        place(runtime, actor, "APARTMENT_DISTRICT")
        presence(client, headers[actor])
    assert (
        client.post(
            "/api/v1/online/chat", headers=headers[alice], json={"text": "Antes"}
        ).status_code
        == 200
    )
    old_id = presence(client, headers[bob]).json()["chat"][-1]["id"]
    importlib.reload(online)
    for actor in (alice, bob):
        presence(client, headers[actor])
    assert (
        client.post(
            "/api/v1/online/chat", headers=headers[alice], json={"text": "Después"}
        ).status_code
        == 200
    )
    new_id = presence(client, headers[bob]).json()["chat"][-1]["id"]
    assert (
        old_id != new_id
    ), "Clients deduplicate by id; reused ids hide new chat after reconnecting"


@pytest.fixture
def world(monkeypatch):
    for flag in (
        "LAIN_ONLINE",
        "LAIN_PROLOGUE_ENABLED",
        "LAIN_CITY_RESIDENTS_ENABLED",
        "LAIN_CHAPTER_ONE",
        "LAIN_CORPORATION",
        "LAIN_WORKSHOP",
        "LAIN_NOEMA",
        "LAIN_CIRCLES",
        "LAIN_CAFE_EVENTS",
        "LAIN_CODE_EXCHANGE",
    ):
        monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("LAIN_WORLD_CLOCK", "0")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    for collection in (
        online._presence,
        online._connections,
        online._limits,
        online._chat,
        api._dialogue_locks,
    ):
        collection.clear()
    runtime = Simulation()
    alice, a_token = online.create_player("Alice")
    bob, b_token = online.create_player("Bob")
    runtime.refresh_human_players()
    monkeypatch.setattr(api, "_runtime", runtime)
    headers = {
        alice: {
            "Authorization": "Bearer " + a_token,
            "X-Lain-Client": "instance-alice",
        },
        bob: {"Authorization": "Bearer " + b_token, "X-Lain-Client": "instance-bob"},
    }
    with TestClient(api.app) as client:
        yield client, runtime, alice, bob, headers


def place(runtime, actor_id, location):
    person = runtime.all_agents[actor_id]
    person.location = location
    database.save_agent(person)
    online.clear_location(actor_id)


def step(client, headers, action, target, request_id=None):
    return client.post(
        "/api/v1/player/step",
        headers=headers,
        json={
            "action": action,
            "target": target,
            "request_id": request_id or uuid.uuid4().hex,
        },
    )


def conversation(client, headers, actor="AGENT_K"):
    result = step(client, headers, "CONTACT", actor)
    assert result.status_code == 200, result.text
    assert result.json()["action_result"]["accepted"], result.text
    response = client.post(
        f"/api/v1/player/conversations/{actor}/start", headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def say(client, headers, turn, text, actor="AGENT_K"):
    response = client.post(
        f"/api/v1/player/conversations/{actor}/say",
        headers=headers,
        json={"text": text, "after_turn_id": turn["turn_id"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def presence(client, headers, location="APARTMENT_DISTRICT", **extra):
    return client.post(
        "/api/v1/online/presence",
        headers=headers,
        json={"location": location, "x": 0, "y": 0.91, "z": 0, **extra},
    )


def test_no_anonymous_access_and_no_client_selected_identity(world):
    client, runtime, alice, bob, headers = world
    assert client.get("/api/v1/player/state").status_code == 401
    assert (
        client.post(
            "/api/v1/player/step", json={"action": "REST", "target": ""}
        ).status_code
        == 401
    )
    own = client.get("/api/v1/player/state?player_id=" + bob, headers=headers[alice])
    assert own.status_code == 200
    assert own.json()["player"]["id"] == alice
    assert own.json()["prologue"]["stage"] == "FIND_TEACHER"
    assert (
        client.post(
            "/api/v1/player/step",
            headers=headers[alice],
            json={
                "action": "REST",
                "target": "",
                "actor_id": bob,
                "request_id": "spoof-id-0001",
            },
        ).status_code
        == 422
    )
    assert bob not in json.dumps(own.json())
    with database.get_connection() as conn:
        saved = str(conn.execute("SELECT * FROM online_credentials").fetchall())
    assert headers[alice]["Authorization"][7:] not in saved


def test_forged_revoked_and_duplicate_access(world):
    client, runtime, alice, bob, headers = world
    assert (
        client.get(
            "/api/v1/player/state",
            headers={
                "Authorization": "Bearer " + "z" * 43,
                "X-Lain-Client": "attacker-1",
            },
        ).status_code
        == 401
    )
    assert client.get("/api/v1/player/state", headers=headers[alice]).status_code == 200
    assert (
        client.get(
            "/api/v1/player/state",
            headers={**headers[alice], "X-Lain-Client": "different-instance"},
        ).status_code
        == 409
    )
    assert (
        client.post("/api/v1/online/leave", headers=headers[alice]).status_code == 200
    )
    assert (
        client.get(
            "/api/v1/player/state",
            headers={**headers[alice], "X-Lain-Client": "different-instance"},
        ).status_code
        == 200
    )
    online.revoke_player(alice)
    assert client.get("/api/v1/player/state", headers=headers[alice]).status_code == 401
    assert client.get("/api/v1/player/state", headers=headers[bob]).status_code == 200


def test_moves_are_individual_and_do_not_advance_shared_clock(world):
    client, runtime, alice, bob, headers = world
    minute = runtime.minute
    result = step(client, headers[alice], "MOVE", "APARTMENT_DISTRICT", "move-alice-01")
    assert result.status_code == 200, result.text
    assert result.json()["action_result"]["accepted"]
    assert result.json()["state"]["player"]["location"] == "APARTMENT_DISTRICT"
    assert (
        client.get("/api/v1/player/state", headers=headers[bob]).json()["player"][
            "location"
        ]
        == "APARTMENT"
    )
    replay = step(client, headers[alice], "MOVE", "APARTMENT_DISTRICT", "move-alice-01")
    assert replay.json()["action_id"] == result.json()["action_id"]
    assert (
        step(client, headers[alice], "MOVE", "SCHOOL", "move-alice-01").status_code
        == 409
    )
    assert runtime.minute == minute
    assert WorldClock(runtime, api._world_lock).tick_once()
    assert runtime.minute > minute
    with database.get_connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM events WHERE actor_id=? AND action='MOVE'",
                (alice,),
            ).fetchone()[0]
            == 1
        )


def test_prologue_and_wired_connection_are_separate(world):
    client, runtime, alice, bob, headers = world
    place(runtime, alice, "SCHOOL_LAB")
    reply = client.post(
        "/api/v1/prologue/talk/PROFESSOR",
        headers=headers[alice],
        json={"choice": "ASK_STUDENT"},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["state"]["prologue"]["stage"] == "FIND_RYOKO"
    assert (
        client.get("/api/v1/player/state", headers=headers[bob]).json()["prologue"][
            "stage"
        ]
        == "FIND_TEACHER"
    )
    place(runtime, alice, "NIGHTCLUB")
    assert (
        client.post(
            "/api/v1/prologue/talk/RYOKO",
            headers=headers[alice],
            json={"choice": "ASK_ADDRESS"},
        ).status_code
        == 200
    )
    place(runtime, alice, "APARTMENT")
    wired = client.post(
        "/api/v1/prologue/terminal",
        headers=headers[alice],
        json={"command": "telnet wired 23"},
    )
    assert wired.status_code == 200, wired.text
    assert wired.json()["state"]["wired"]["connected"]
    assert wired.json()["state"]["workshop"]["active"]
    assert not client.get("/api/v1/player/state", headers=headers[bob]).json()["wired"][
        "connected"
    ]
    stolen = client.post(
        f"/api/v1/player/messages/{initial_message_id(alice)}/ack", headers=headers[bob]
    )
    assert stolen.status_code == 404
    place(runtime, bob, "APARTMENT_DISTRICT")
    assert not step(client, headers[bob], "MOVE", "STATION").json()["action_result"][
        "accepted"
    ]


def test_dialogue_recall_and_provenance_are_bound_to_speaker(world):
    client, runtime, alice, bob, headers = world
    for actor in (alice, bob, "AGENT_K", "AGENT_NORA"):
        place(runtime, actor, "APARTMENT_DISTRICT")
    a = conversation(client, headers[alice])
    b = conversation(client, headers[bob])
    a = say(client, headers[alice], a, "Mi perro se llama Pipo")
    a = say(client, headers[alice], a, "Mi perro se llama Sora")
    b = say(client, headers[bob], b, "Mi perro se llama Kira")
    a = say(client, headers[alice], a, "¿Cómo se llamaba mi perro antes?")
    assert "Pipo" in a["line"] and "Sora" in a["line"] and "Kira" not in a["line"]
    b = say(client, headers[bob], b, "¿Cómo se llama mi perro ahora?")
    assert "Kira" in b["line"] and "Sora" not in b["line"]
    context = AgentContextBuilder().build(
        "AGENT_K", b["interaction_id"], "¿Qué sabes de mi perro?"
    )
    serialized = json.dumps(context)
    assert (
        "Kira" in serialized and "Pipo" not in serialized and "Sora" not in serialized
    )
    assert all(item["source_actor_id"] == bob for item in context["memory_records"])
    nora = conversation(client, headers[bob], "AGENT_NORA")
    nora = say(
        client, headers[bob], nora, "¿Cómo se llama mi perro ahora?", "AGENT_NORA"
    )
    assert "Kira" not in nora["line"]
    assert (
        client.post(
            "/api/v1/player/conversations/AGENT_K/pause",
            headers=headers[bob],
            json={"interaction_id": a["interaction_id"]},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/player/conversations/AGENT_K/say",
            headers=headers[bob],
            json={"text": "Otra cosa", "after_turn_id": a["turn_id"]},
        ).status_code
        == 409
    )


def test_encounters_do_not_confuse_two_visitors(world):
    client, runtime, alice, bob, headers = world
    for actor in (alice, bob, "AGENT_K"):
        place(runtime, actor, "STATION")
    a = conversation(client, headers[alice])
    b = conversation(client, headers[bob])
    # Bob has no encounter BEFORE his current greeting, even though Alice does.
    b = say(
        client,
        headers[bob],
        b,
        "¿Qué pasó la última vez que nos encontramos en la estación?",
    )
    assert "No tengo registrado" in b["line"]
    with database.get_connection() as conn:
        participants = [
            json.loads(row[0])
            for row in conn.execute(
                "SELECT participants FROM agent_experiences WHERE owner_id='AGENT_K'"
            )
        ]
    assert sorted(["AGENT_K", alice]) in participants
    assert sorted(["AGENT_K", bob]) in participants


def test_presence_chat_areas_and_expiry(world, monkeypatch):
    client, runtime, alice, bob, headers = world
    for actor in (alice, bob):
        place(runtime, actor, "APARTMENT_DISTRICT")
        assert presence(client, headers[actor]).status_code == 200
    visible = presence(client, headers[alice]).json()["players"]
    assert [item["id"] for item in visible] == [bob]
    assert set(visible[0]) == {"id", "name", "x", "y", "z", "yaw", "who"}
    assert (
        client.post(
            "/api/v1/online/chat",
            headers=headers[alice],
            json={"text": "Vamos al colegio"},
        ).status_code
        == 200
    )
    assert (
        presence(client, headers[bob]).json()["chat"][0]["text"] == "Vamos al colegio"
    )
    place(runtime, bob, "SCHOOL")
    assert presence(client, headers[bob], location="SCHOOL").json()["chat"] == []
    assert presence(client, headers[alice]).json()["players"] == []
    place(runtime, alice, "APARTMENT")
    assert (
        presence(client, headers[alice], location="APARTMENT").json()["players"] == []
    )
    assert (
        client.post(
            "/api/v1/online/chat", headers=headers[alice], json={"text": "Desde casa"}
        ).status_code
        == 409
    )


def test_presence_cannot_move_world_or_teleport_visual_replica(world):
    client, runtime, alice, bob, headers = world
    place(runtime, alice, "APARTMENT_DISTRICT")
    assert presence(client, headers[alice]).status_code == 200
    jump = presence(client, headers[alice], x=90)
    assert jump.status_code == 200 and not jump.json()["accepted"]
    assert jump.json()["position"]["x"] == 0
    assert presence(client, headers[alice], location="STATION").status_code == 409
    assert runtime.all_agents[alice].location == "APARTMENT_DISTRICT"
    assert presence(client, headers[alice], x=1000).status_code == 409


def test_presence_is_not_delayed_by_a_clock_tick_or_snapped_back(world):
    client, runtime, alice, bob, headers = world
    place(runtime, alice, "APARTMENT_DISTRICT")
    assert presence(client, headers[alice]).json()["accepted"]
    # A clock tick (possibly waiting on the LLM) holds the world lock.
    with ThreadPoolExecutor(max_workers=1) as pool:
        with api._world_lock:
            walking = pool.submit(presence, client, headers[alice], x=0.5)
            assert walking.result(timeout=2).json()["accepted"]
    # A heartbeat that arrived on time but was processed late keeps its timing:
    # 7 m walked over 2.2 s of arrivals is a normal walk, not a teleport.
    instance = headers[alice]["X-Lain-Client"]
    start = online.time.monotonic()
    online.heartbeat(alice, instance, "APARTMENT_DISTRICT", 2.0, 0.91, 0.0, 0.0, received_at=start)
    late = online.heartbeat(alice, instance, "APARTMENT_DISTRICT", 9.0, 0.91, 0.0, 0.0, received_at=start + 2.2)
    assert late["accepted"] and late["position"]["x"] == 9.0
    # An instant jump is still rejected.
    jump = online.heartbeat(alice, instance, "APARTMENT_DISTRICT", 60.0, 0.91, 0.0, 0.0, received_at=start + 2.3)
    assert not jump["accepted"] and jump["position"]["x"] == 9.0


def test_npc_generation_does_not_hold_other_players_or_clock(world, monkeypatch):
    client, runtime, alice, bob, headers = world
    for actor in (alice, bob, "AGENT_K"):
        place(runtime, actor, "APARTMENT_DISTRICT")
    a = conversation(client, headers[alice])
    entered = threading.Event()
    release = threading.Event()

    def delayed_reply(**kwargs):
        entered.set()
        assert release.wait(5)
        return DialogueReply("Estoy aquí.", "DETERMINISTIC")

    monkeypatch.setattr(free_conversation, "generate_dialogue_reply", delayed_reply)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(
            say, client, headers[alice], a, "¿Qué piensas de este lugar?"
        )
        try:
            assert entered.wait(3)
            second = pool.submit(
                client.get, "/api/v1/player/state", headers=headers[bob]
            )
            assert second.result(timeout=2).json()["player"]["id"] == bob
            assert presence(client, headers[alice], dialogue=True).status_code == 200
            before = runtime.minute
            assert WorldClock(runtime, api._world_lock).tick_once()
            assert runtime.minute > before
            assert runtime.all_agents["AGENT_K"].location == "APARTMENT_DISTRICT"
            duplicate = client.post(
                "/api/v1/player/conversations/AGENT_K/say",
                headers=headers[alice],
                json={"text": "¿Qué piensas?", "after_turn_id": a["turn_id"]},
            )
            assert duplicate.status_code == 429
        finally:
            release.set()
        assert future.result(timeout=3)["line"] == "Estoy aquí."


def test_restart_keeps_identity_and_personal_progress(world, monkeypatch):
    client, runtime, alice, bob, headers = world
    place(runtime, alice, "SCHOOL_LAB")
    assert (
        client.post(
            "/api/v1/prologue/talk/PROFESSOR",
            headers=headers[alice],
            json={"choice": "ASK_STUDENT"},
        ).status_code
        == 200
    )
    monkeypatch.setattr(api, "_runtime", None)
    online._presence.clear()
    online._connections.clear()
    resumed = client.get("/api/v1/player/state", headers=headers[alice]).json()
    assert resumed["player"]["id"] == alice
    assert resumed["player"]["location"] == "SCHOOL_LAB"
    assert resumed["prologue"]["stage"] == "FIND_RYOKO"
    assert (
        client.get("/api/v1/player/state", headers=headers[bob]).json()["prologue"][
            "stage"
        ]
        == "FIND_TEACHER"
    )


def test_second_world_owner_is_rejected(world):
    with pytest.raises(RuntimeError, match="ya está abierto"):
        with online.world_host_lock():
            pytest.fail("Two servers must not own one world")


def test_disconnected_humans_are_not_seen_by_npcs(world):
    from server.world_core.actor_locations import (
        perceive_colocated_actors,
        load_actor_location_belief,
    )

    client, runtime, alice, bob, headers = world
    for actor in (alice, bob, "AGENT_K"):
        place(runtime, actor, "APARTMENT_DISTRICT")
    client.get("/api/v1/player/state", headers=headers[alice])
    perceive_colocated_actors(runtime.all_agents["AGENT_K"], runtime.minute)
    assert load_actor_location_belief("AGENT_K", alice) is not None
    assert load_actor_location_belief("AGENT_K", bob) is None


def test_interrupted_response_never_replays_effects_on_retry_or_next_tick(
    world, monkeypatch
):
    client, runtime, alice, bob, headers = world
    original = api.build_player_snapshot

    def fail_snapshot(actor_id):
        raise ValueError("SIMULATED_INTERRUPTION_AFTER_EFFECT")

    monkeypatch.setattr(api, "build_player_snapshot", fail_snapshot)
    result = step(
        client, headers[alice], "MOVE", "APARTMENT_DISTRICT", "interrupted-01"
    )
    assert result.status_code == 400
    monkeypatch.setattr(api, "build_player_snapshot", original)
    assert (
        step(
            client, headers[alice], "MOVE", "APARTMENT_DISTRICT", "interrupted-01"
        ).status_code
        == 409
    )
    assert WorldClock(runtime, api._world_lock).tick_once()
    with database.get_connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM events WHERE actor_id=? AND action='MOVE'",
                (alice,),
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM pending_actions WHERE actor_id=? AND processed=0",
                (alice,),
            ).fetchone()[0]
            == 0
        )
