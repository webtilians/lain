import pytest
import sqlite3

from server.api import (
    acknowledge_player_message,
)

from server.world_core.beliefs import (
    load_belief,
)

from server.world_core.database import (
    get_connection,
)

from server.world_core.knowledge import (
    knows_node,
)

from server.world_core.messages import (
    INITIAL_MESSAGE_ID,
)

from server.world_core.player_view import (
    build_player_snapshot,
)

from server.world_core.simulation import (
    Simulation,
)


def test_retry_recovers_lead_after_acknowledgement_was_already_committed(monkeypatch):
    from server.world_core import wired

    Simulation()
    original = wired.grant_initial_wired_lead

    def interrupted(*args, **kwargs):
        raise RuntimeError("simulated interruption before lead")

    monkeypatch.setattr(wired, "grant_initial_wired_lead", interrupted)
    with pytest.raises(RuntimeError):
        acknowledge_player_message(INITIAL_MESSAGE_ID)
    monkeypatch.setattr(wired, "grant_initial_wired_lead", original)
    acknowledge_player_message(INITIAL_MESSAGE_ID)
    assert knows_node("PLAYER_1", "NODE_07")
    assert load_belief("PLAYER_1", "NODE_07") is not None


def test_initial_lead_rolls_back_as_one_unit_and_can_be_retried():
    Simulation()
    with get_connection() as conn:
        conn.execute(
            """CREATE TRIGGER fail_initial_lead BEFORE INSERT ON node_beliefs
            WHEN NEW.agent_id='PLAYER_1' AND NEW.source='WIRED_MESSAGE'
            BEGIN SELECT RAISE(ABORT, 'simulated disk failure'); END"""
        )
    with pytest.raises(sqlite3.IntegrityError, match="simulated disk failure"):
        acknowledge_player_message(INITIAL_MESSAGE_ID)
    assert not knows_node(
        "PLAYER_1", "NODE_07"
    ), "Knowledge and belief must commit together"
    with get_connection() as conn:
        conn.execute("DROP TRIGGER fail_initial_lead")
    acknowledge_player_message(INITIAL_MESSAGE_ID)
    assert load_belief("PLAYER_1", "NODE_07") is not None


def test_reconnect_preserves_newer_direct_observation():
    from server.world_core.beliefs import save_belief
    from server.world_core.models import NodeBelief

    Simulation()
    acknowledge_player_message(INITIAL_MESSAGE_ID)
    direct = NodeBelief(
        "PLAYER_1", "NODE_07", "STATION", 0.8, 0.99, "ACTIVE_INVESTIGATION", 120
    )
    save_belief(direct)
    acknowledge_player_message(INITIAL_MESSAGE_ID)
    assert load_belief("PLAYER_1", "NODE_07") == direct


def test_retry_repairs_older_partial_save_with_original_chronology():
    from server.world_core.knowledge import learn_node
    from server.world_core.messages import acknowledge_message
    from server.world_core.wired import process_wired_message_acknowledgement

    Simulation()
    acknowledge_message(INITIAL_MESSAGE_ID, "PLAYER_1", 17)
    learn_node("PLAYER_1", "NODE_07", 0.35, "WIRED_MESSAGE")
    for minute in (50, 70):
        process_wired_message_acknowledgement(INITIAL_MESSAGE_ID, "PLAYER_1", minute)
    belief = load_belief("PLAYER_1", "NODE_07")
    assert belief.updated_minute == 17
    assert belief.source == "WIRED_MESSAGE"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT minute FROM events WHERE actor_id='PLAYER_1' AND action='WIRED_LEAD_RECEIVED'"
        ).fetchall()
    assert [row[0] for row in rows] == [17]


# ======================================================
# 1. CONNECT GRANTS NODE_07 LEAD
# ======================================================

def test_connect_grants_initial_wired_lead():

    Simulation()

    acknowledge_player_message(
        INITIAL_MESSAGE_ID
    )

    assert knows_node(
        "PLAYER_1",
        "NODE_07",
    )

    belief = load_belief(
        "PLAYER_1",
        "NODE_07",
    )

    assert belief is not None
    assert belief.believed_location == "STATION"
    assert belief.confidence == pytest.approx(0.35)
    assert belief.source == "WIRED_MESSAGE"

# ======================================================
# 2. CONNECT DOES NOT LEAK NODE_12
# ======================================================

def test_connect_does_not_reveal_unrelated_nodes():

    Simulation()

    acknowledge_player_message(
        INITIAL_MESSAGE_ID
    )

    assert not knows_node(
        "PLAYER_1",
        "NODE_12",
    )

# ======================================================
# 3. WIRED PROJECTION BECOMES ACTIVE
# ======================================================

def test_player_projection_contains_wired_signal():

    Simulation()

    acknowledge_player_message(
        INITIAL_MESSAGE_ID
    )

    snapshot = build_player_snapshot()
    wired = snapshot["wired"]

    assert wired["connected"] is True
    assert len(wired["signals"]) == 1

    signal = wired["signals"][0]

    assert signal["node_id"] == "NODE_07"
    assert signal["location"] == "STATION"
    assert signal["confidence"] == pytest.approx(0.35)

# ======================================================
# 4. EFFECT IS IDEMPOTENT
# ======================================================

def test_reconnecting_does_not_duplicate_wired_lead():

    Simulation()

    acknowledge_player_message(
        INITIAL_MESSAGE_ID
    )

    acknowledge_player_message(
        INITIAL_MESSAGE_ID
    )

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT COUNT(*)

            FROM events

            WHERE actor_id = 'PLAYER_1'
              AND action = 'WIRED_LEAD_RECEIVED'
              AND target = 'NODE_07'
            """
        ).fetchone()

    assert row[0] == 1

# ======================================================
# 5. WIRED STATE SURVIVES NEW SIMULATION INSTANCE
# ======================================================

def test_wired_connection_survives_restart():

    Simulation()

    acknowledge_player_message(
        INITIAL_MESSAGE_ID
    )

    Simulation()

    snapshot = build_player_snapshot()

    assert snapshot["wired"]["connected"] is True
    assert snapshot["wired"]["signals"][0]["node_id"] == "NODE_07"
