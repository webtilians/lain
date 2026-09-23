"""First-run prologue contract; all tests use pytest's isolated temporary database."""
import pytest

from server.world_core.action_queue import queue_action
from server.world_core.database import (
    get_connection, record_event, save_agent,
)
from server.world_core.messages import INITIAL_MESSAGE_ID
from server.world_core.player_view import build_player_snapshot
from server.world_core.prologue import (
    gate_move, prologue_projection, stage_for,
    submit_terminal_command, talk_to_prologue_npc,
)
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement


def fresh_game(monkeypatch):
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED", "1")
    sim = Simulation()
    assert stage_for() == "FIND_TEACHER"
    assert build_player_snapshot()["wired"]["connected"] is False
    return sim


def walk(sim, destination):
    action_id = queue_action(
        actor_id="PLAYER_1", action="MOVE", target=destination,
        source="GODOT_CLIENT",
    )
    return sim.tick()[action_id]


def relocate(sim, destination):
    """Move through actual World Core routes, never write a fabricated position."""
    route = {
        "SCHOOL_LAB": [
            "APARTMENT_DISTRICT", "SCHOOL", "SCHOOL_LAB",
        ],
        "NIGHTCLUB": [
            "SCHOOL", "APARTMENT_DISTRICT", "NIGHTCLUB",
        ],
        "APARTMENT": [
            "APARTMENT_DISTRICT", "APARTMENT",
        ],
    }
    for step in route[destination]:
        outcome = walk(sim, step)
        assert outcome["accepted"], (step, outcome)
    assert sim.player.location == destination


def test_fresh_opted_in_player_starts_offline_and_receives_objective(monkeypatch):
    fresh_game(monkeypatch)
    snap = build_player_snapshot()
    assert snap["prologue"]["stage"] == "FIND_TEACHER"
    assert "SCHOOL" not in snap["wired"].get("signals", [])
    assert "STATION" not in snap["navigation"]["reachable_locations"]
    assert snap["character_sheets"]["player"]["id"] == "PLAYER_1"
    with get_connection() as conn:
        assert conn.execute(
            "SELECT acknowledged FROM world_messages WHERE id=?",
            (INITIAL_MESSAGE_ID,),
        ).fetchone() == (0,)


def test_location_and_legacy_connect_bypasses_are_rejected(monkeypatch):
    sim = fresh_game(monkeypatch)
    response = walk(sim, "STATION")
    assert response == {
        "accepted": False, "action": "MOVE", "target": "STATION",
        "reason": "WIRED_NOT_CONNECTED",
    }
    with pytest.raises(ValueError, match="PROLOGUE_TERMINAL_REQUIRED"):
        process_wired_message_acknowledgement(
            INITIAL_MESSAGE_ID, "PLAYER_1", sim.minute,
        )
    assert not submit_terminal_command(
        "PLAYER_1", "telnet wired 23", sim.minute
    )["accepted"]
    with get_connection() as conn:
        assert conn.execute(
            "SELECT acknowledged FROM world_messages WHERE id=?",
            (INITIAL_MESSAGE_ID,),
        ).fetchone() == (0,)


def test_teacher_ryoko_order_and_colocation(monkeypatch):
    sim = fresh_game(monkeypatch)
    with pytest.raises(ValueError, match="CHARACTER_NOT_PRESENT"):
        talk_to_prologue_npc("PLAYER_1", "PROFESSOR", sim.minute, "ASK_STUDENT")
    relocate(sim, "SCHOOL_LAB")
    introduction = talk_to_prologue_npc("PLAYER_1", "PROFESSOR", sim.minute)
    assert introduction["stage"] == "FIND_TEACHER"
    teacher = talk_to_prologue_npc(
        "PLAYER_1", "PROFESSOR", sim.minute, "ASK_STUDENT",
    )
    assert teacher["stage"] == "FIND_RYOKO"
    assert "Ryoko" in teacher["text"]
    with pytest.raises(ValueError, match="CHARACTER_NOT_PRESENT"):
        talk_to_prologue_npc("PLAYER_1", "RYOKO", sim.minute, "ASK_ADDRESS")
    relocate(sim, "NIGHTCLUB")
    introduction = talk_to_prologue_npc("PLAYER_1", "RYOKO", sim.minute)
    assert introduction["stage"] == "FIND_RYOKO"
    result = talk_to_prologue_npc(
        "PLAYER_1", "RYOKO", sim.minute, "ASK_ADDRESS",
    )
    assert result["stage"] == "FIND_TERMINAL"
    assert "WIRED" in result["text"]
    assert "23" in result["text"]
    assert "TELNET" not in result["text"].upper()
    assert "INTERNET" not in result["text"].upper()
    assert stage_for() == "FIND_TERMINAL"
    with pytest.raises(ValueError, match="TERMINAL_NOT_PRESENT"):
        submit_terminal_command("PLAYER_1", "telnet wired 23", sim.minute)


def test_real_telnet_syntax_and_network_free_validation(monkeypatch):
    sim = fresh_game(monkeypatch)
    relocate(sim, "SCHOOL_LAB")
    talk_to_prologue_npc("PLAYER_1", "PROFESSOR", sim.minute, "ASK_STUDENT")
    relocate(sim, "NIGHTCLUB")
    talk_to_prologue_npc("PLAYER_1", "RYOKO", sim.minute, "ASK_ADDRESS")
    relocate(sim, "APARTMENT")
    for malformed in [
        "telnet wired", "connect wired 23", "telnet wired 22",
        "telnet 127.0.0.1 23", "telnet wired 23; echo BAD",
        "telnet wired 23 | whoami", "telnet wired 23\nrm -rf /",
    ]:
        if "\n" in malformed:
            with pytest.raises(ValueError, match="INVALID_TERMINAL_INPUT"):
                submit_terminal_command("PLAYER_1", malformed, sim.minute)
        else:
            assert submit_terminal_command(
                "PLAYER_1", malformed, sim.minute
            ) == {"accepted": False, "reason": "COMMAND_NOT_RECOGNIZED"}
        assert stage_for() == "FIND_TERMINAL"
    assert submit_terminal_command(
        "PLAYER_1", "  TELNET   WIRED   23  ", sim.minute,
    ) == {"accepted": True, "reason": "LINK_ESTABLISHED"}
    assert stage_for() == "CONNECTED"
    # Connection to the fictional server has no OS, shell or socket step.
    assert not submit_terminal_command(
        "PLAYER_1", "telnet wired 23", sim.minute,
    )["accepted"]
    process_wired_message_acknowledgement(
        INITIAL_MESSAGE_ID, "PLAYER_1", sim.minute,
    )
    snap = build_player_snapshot()
    assert snap["wired"]["connected"] is True
    assert snap["prologue"]["stage"] == "CONNECTED"
    assert walk(sim, "APARTMENT_DISTRICT")["accepted"]
    assert walk(sim, "STATION")["accepted"]
    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM events WHERE action='PROLOGUE_CONNECTED'"
        ).fetchone()[0] == 1


def test_prologue_is_persistent_across_server_restart(monkeypatch):
    sim = fresh_game(monkeypatch)
    relocate(sim, "SCHOOL_LAB")
    talk_to_prologue_npc("PLAYER_1", "PROFESSOR", sim.minute, "ASK_STUDENT")
    restart = Simulation()
    assert restart.player.location == "SCHOOL_LAB"
    assert stage_for() == "FIND_RYOKO"
    assert build_player_snapshot()["prologue"]["stage"] == "FIND_RYOKO"


def test_legacy_seven_entity_save_does_not_restart_as_prologue(monkeypatch):
    monkeypatch.delenv("LAIN_PROLOGUE_ENABLED", raising=False)
    sim = Simulation()
    sim.tick()
    before = build_player_snapshot()
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED", "1")
    Simulation()
    assert stage_for() is None
    after = build_player_snapshot()
    assert after["prologue"]["enabled"] is False
    assert after["wired"]["connected"] == before["wired"]["connected"]
    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM player_prologue"
        ).fetchone()[0] == 0


def test_unenabled_new_game_remains_backward_compatible(monkeypatch):
    monkeypatch.delenv("LAIN_PROLOGUE_ENABLED", raising=False)
    Simulation()
    assert stage_for() is None
    assert gate_move("PLAYER_1", "STATION") == (True, "")
    with pytest.raises(ValueError, match="NO_ACTIVE_PROLOGUE"):
        submit_terminal_command("PLAYER_1", "telnet wired 23", 0)


def test_authored_character_sheets_are_visible_only_in_same_room(monkeypatch):
    sim = fresh_game(monkeypatch)
    assert build_player_snapshot()["station_case"]["status"] == "LOCKED"
    assert build_player_snapshot()["messages"] == []
    relocate(sim, "SCHOOL_LAB")
    cards = build_player_snapshot()["character_sheets"]["visible_npcs"]
    assert any(
        item["id"] == "PROFESSOR"
        and item["role_assignment"] == "AUTHORED_PROLOGUE"
        for item in cards
    )
    assert not any(item["id"] == "RYOKO" for item in cards)
    talk_to_prologue_npc("PLAYER_1", "PROFESSOR", sim.minute, "ASK_STUDENT")
    relocate(sim, "NIGHTCLUB")
    cards = build_player_snapshot()["character_sheets"]["visible_npcs"]
    assert any(item["id"] == "RYOKO" for item in cards)
    assert not any(item["id"] == "PROFESSOR" for item in cards)
    assert build_player_snapshot()["station_case"]["status"] == "LOCKED"


def test_recover_prologue_if_server_interrupted_after_command_before_ack(monkeypatch):
    import server.api as api
    sim = fresh_game(monkeypatch)
    relocate(sim, "SCHOOL_LAB")
    talk_to_prologue_npc("PLAYER_1", "PROFESSOR", sim.minute, "ASK_STUDENT")
    relocate(sim, "NIGHTCLUB")
    talk_to_prologue_npc("PLAYER_1", "RYOKO", sim.minute, "ASK_ADDRESS")
    relocate(sim, "APARTMENT")
    assert submit_terminal_command(
        "PLAYER_1", "telnet wired 23", sim.minute,
    )["accepted"]
    assert stage_for() == "CONNECTED"
    assert build_player_snapshot()["wired"]["connected"] is False
    monkeypatch.setattr(api, "_runtime", sim)
    repaired = api.prologue_terminal(
        api.PrologueCommandRequest(command="telnet wired 23")
    )
    assert repaired["result"]["accepted"] is True
    assert repaired["state"]["wired"]["connected"] is True
    assert repaired["state"]["station_case"]["status"] == "UNSEEN"
    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM events WHERE action='PROLOGUE_CONNECTED'"
        ).fetchone()[0] == 1
