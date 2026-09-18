import pytest

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
