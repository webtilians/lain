"""English players: what a newcomer sees in the first hour must not leak Spanish."""
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from server import api
from server.world_core import i18n, layer_three, online
from server.world_core.prologue import submit_terminal_command
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement
from tests.test_chapter_one import move

# Accents, inverted marks and frequent Spanish words. Names (Ryoko, Kissa,
# NODE_07, KAGAMI) and identifiers are fine.
SPANISH = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|tus|está|hay|puedes|eres|quién|qué)\b", re.I)


def leaks(value, path="") -> list:
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in i18n.PRIVATE_FIELDS or key in {"name", "actor_name", "id", "stage", "location"}:
                continue
            found += leaks(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += leaks(item, f"{path}[{index}]")
    elif (isinstance(value, str) and path.rsplit(".", 1)[-1] in i18n.DISPLAY_FIELDS
          and SPANISH.search(value.replace("Café", "").replace("café", ""))):
        found.append(f"{path}: {value[:90]!r}")
    return found


@pytest.fixture
def english(monkeypatch):
    for flag in ("LAIN_PROLOGUE_ENABLED", "LAIN_CITY_RESIDENTS_ENABLED", "LAIN_LAYER_THREE", "LAIN_CORPORATION",
                 "LAIN_WORKSHOP", "LAIN_CHAPTER_ONE"):
        monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    monkeypatch.setenv("LAIN_WORLD_CLOCK", "0")
    runtime = Simulation()
    monkeypatch.setattr(api, "_runtime", runtime)
    client = TestClient(api.app, headers={"X-Lain-Language": "en"})
    return client, runtime


def test_prologue_and_first_conversations_are_english(english):
    client, runtime = english
    move(runtime, "SCHOOL_LAB")
    for choice in ("INTRO", "ASK_CLASS", "ASK_STUDENT", "ASK_WHERE", "GOODBYE"):
        reply = client.post("/api/v1/prologue/talk/PROFESSOR", json={"choice": choice})
        assert reply.status_code == 200, reply.text
        assert not leaks(reply.json(), "talk"), leaks(reply.json(), "talk")
    move(runtime, "NIGHTCLUB")
    for choice in ("INTRO", "ASK_SCHOOL", "ASK_WIRED", "ASK_ADDRESS", "ASK_METHOD", "GOODBYE"):
        reply = client.post("/api/v1/prologue/talk/RYOKO", json={"choice": choice})
        assert not leaks(reply.json(), "talk"), leaks(reply.json(), "talk")
    state = client.get("/api/v1/player/state").json()
    assert not leaks(state.get("prologue"), "prologue"), leaks(state.get("prologue"), "prologue")
    assert not leaks(state.get("messages"), "messages"), leaks(state.get("messages"), "messages")


def test_conversation_with_k_is_english(english):
    client, runtime = english
    runtime.player.location = runtime.k.agent.location = "STATION"
    from server.world_core.database import save_agent
    from server.world_core.interactions import create_or_get_interaction
    from server.world_core.player_conversation import initialize_conversation_turns
    for agent in (runtime.player, runtime.k.agent):
        save_agent(agent)
    initialize_conversation_turns()
    create_or_get_interaction("PLAYER_1", "AGENT_K", "PLAYER_INITIATED_CONVERSATION", "UNKNOWN", runtime.minute)
    first = client.post("/api/v1/player/conversations/AGENT_K/start")
    assert first.status_code == 200, first.text
    assert not leaks(first.json(), "start"), leaks(first.json(), "start")
    for choice in ("ASK_IDENTITY", "ASK_SIGNAL"):
        turn = client.post("/api/v1/player/conversations/AGENT_K/reply",
                           json={"choice_id": choice, "after_turn_id": first.json()["turn_id"]})
        assert not leaks(turn.json(), "reply"), leaks(turn.json(), "reply")
        first = turn


def test_layer_three_terminal_is_english_for_a_new_english_player(english):
    client, runtime = english
    move(runtime, "SCHOOL_LAB")
    from server.world_core.prologue import talk_to_prologue_npc
    talk_to_prologue_npc("PLAYER_1", "PROFESSOR", runtime.minute, "ASK_STUDENT")
    move(runtime, "NIGHTCLUB")
    talk_to_prologue_npc("PLAYER_1", "RYOKO", runtime.minute, "ASK_ADDRESS")
    move(runtime, "APARTMENT")
    assert submit_terminal_command("PLAYER_1", "telnet wired 23", runtime.minute)["accepted"]
    token = i18n.set_language("en")
    try:
        process_wired_message_acknowledgement("MSG_BOOTSTRAP_001", "PLAYER_1", runtime.minute)
    finally:
        i18n.reset(token)
    state = client.get("/api/v1/player/state").json()
    assert not leaks(state["layer_three"], "layer_three"), leaks(state["layer_three"], "layer_three")
    packet = state["layer_three"]["packet"]
    for command in ("help", "man ttl", "man cadena", "man chain", "cat ~/correo/ttl1.eml", f"traceroute {packet}",
                    "cat /net/hosts", "cat /etc/motd", "whoami", "uptime", "last", "ping k", "cat /var/log/wired/diario",
                    "report 1", "frobnicate"):
        reply = client.post("/api/v1/layer-three/shell", json={"host": "navi", "cwd": "/", "command": command})
        assert reply.status_code == 200, reply.text
        output = reply.json()["result"]["output"]
        offending = [line for line in output.splitlines() if SPANISH.search(line) and "Sesión" not in line]
        assert not offending, (command, offending[:3])
