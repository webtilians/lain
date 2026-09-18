from server.api import (
    perform_player_step,
)

from server.world_core.player_view import (
    build_player_snapshot,
)

from server.world_core.simulation import (
    Simulation,
)

# ======================================================
# 1. INITIAL PLAYER PROJECTION
# ======================================================

def test_player_snapshot_contains_only_player_projection():

    Simulation()

    snapshot = build_player_snapshot()

    assert snapshot["player"]["id"] == "PLAYER_1"
    assert snapshot["player"]["location"] == "APARTMENT"
    assert snapshot["minute"] == 0

# ======================================================
# 2. WORLD REALITY IS NOT EXPOSED
# ======================================================

def test_player_snapshot_does_not_expose_world_reality():

    Simulation()

    snapshot = build_player_snapshot()
    serialized = str(snapshot)

    forbidden = [
        "anomaly_strength",
        "world_state",
        "world_signal",
        "stability",
        "connection",
        "AGENT_K",
        "AGENT_NORA",
    ]

    for key in forbidden:
        assert key not in serialized

# ======================================================
# 3. ONLY PHYSICALLY REACHABLE LOCATIONS ARE EXPOSED
# ======================================================

def test_player_navigation_exposes_only_adjacent_locations():

    Simulation()

    snapshot = build_player_snapshot()

    assert snapshot["navigation"]["reachable_locations"] == [
        "APARTMENT_DISTRICT"
    ]

    assert "STATION" not in snapshot[
        "navigation"
    ]["reachable_locations"]

# ======================================================
# 4. UNKNOWN NODE IS NOT LEAKED
# ======================================================

def test_unknown_nodes_are_not_exposed_to_player():

    Simulation()

    snapshot = build_player_snapshot()

    ids = {
        node["id"]
        for node in snapshot["known_nodes"]
    }

    assert "NODE_07" not in ids
    assert "NODE_12" not in ids

# ======================================================
# 5. GODOT STEP USES THE SAME PLAYER ACTION CONTRACT
# ======================================================

def test_public_step_moves_player_one_physical_hop():

    simulation = Simulation()

    result = perform_player_step(
        action="MOVE",
        target="STATION",
        simulation=simulation,
    )

    state = result["state"]

    assert state["player"]["location"] == (
        "APARTMENT_DISTRICT"
    )

    assert state["minute"] == 10

# ======================================================
# 6. DISCOVERED INFORMATION BECOMES PUBLIC
# ======================================================

def test_player_projection_exposes_node_only_after_discovery():

    simulation = Simulation()

    perform_player_step(
        action="MOVE",
        target="STATION",
        simulation=simulation,
    )

    perform_player_step(
        action="MOVE",
        target="STATION",
        simulation=simulation,
    )

    snapshot = build_player_snapshot()

    assert snapshot["player"]["location"] == "STATION"

    perform_player_step(
        action="REST",
        target="PLAYER_1",
        simulation=simulation,
    )

    snapshot = build_player_snapshot()

    ids = {
        node["id"]
        for node in snapshot["known_nodes"]
    }

    assert "NODE_07" in ids
    assert "NODE_12" not in ids
