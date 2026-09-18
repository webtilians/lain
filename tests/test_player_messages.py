from server.api import (
    acknowledge_player_message,
)

from server.world_core.database import (
    get_connection,
)

from server.world_core.messages import (
    INITIAL_MESSAGE_ID,
    acknowledge_message,
)

from server.world_core.player_view import (
    build_player_snapshot,
)

from server.world_core.simulation import (
    Simulation,
)

# ======================================================
# 1. INITIAL MESSAGE EXISTS
# ======================================================

def test_initial_player_message_is_visible():

    Simulation()

    snapshot = build_player_snapshot()

    assert snapshot["unread_messages"] == 1
    assert len(snapshot["messages"]) == 1

    message = snapshot["messages"][0]

    assert message["id"] == INITIAL_MESSAGE_ID
    assert message["sender"] == "unknown@wired"

# ======================================================
# 2. NARRATIVE LIVES ON SERVER
# ======================================================

def test_initial_message_contains_bootstrap_text():

    Simulation()

    snapshot = build_player_snapshot()
    body = snapshot["messages"][0]["body"]

    assert "NO ESTOY MUERTA" in body
    assert "SOLO DEJÉ DE ESTAR AHÍ" in body

# ======================================================
# 3. CONNECT PERSISTS
# ======================================================

def test_message_acknowledgement_is_persistent():

    Simulation()

    result = acknowledge_player_message(
        INITIAL_MESSAGE_ID
    )

    state = result["state"]
    message = state["messages"][0]

    assert message["acknowledged"] is True
    assert message["read"] is True
    assert state["unread_messages"] == 0

# ======================================================
# 4. CONNECT CREATES ONLY ONE WORLD EVENT
# ======================================================

def test_acknowledgement_is_idempotent():

    simulation = Simulation()

    acknowledge_message(
        message_id=INITIAL_MESSAGE_ID,
        player_id="PLAYER_1",
        minute=simulation.minute,
    )

    acknowledge_message(
        message_id=INITIAL_MESSAGE_ID,
        player_id="PLAYER_1",
        minute=simulation.minute,
    )

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT COUNT(*)

            FROM events

            WHERE actor_id = 'PLAYER_1'
              AND action = 'MESSAGE_ACKNOWLEDGED'
              AND target = ?
            """,
            (INITIAL_MESSAGE_ID,),
        ).fetchone()

    assert row[0] == 1

# ======================================================
# 5. PLAYER CANNOT ACK UNKNOWN MESSAGE
# ======================================================

def test_unknown_message_cannot_be_acknowledged():

    Simulation()

    try:
        acknowledge_message(
            message_id="DOES_NOT_EXIST",
            player_id="PLAYER_1",
            minute=0,
        )
        assert False

    except ValueError:
        assert True
