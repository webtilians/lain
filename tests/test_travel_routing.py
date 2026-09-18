import pytest

from server.world_core.action_queue import (
    queue_action,
)

from server.world_core.database import (
    get_connection,
)

from server.world_core.locations import (
    next_hop,
    shortest_hops,
    shortest_path,
)

from server.world_core.simulation import (
    Simulation,
)

# ======================================================
# 1. ROUTE IS DETERMINISTIC
# ======================================================

def test_shortest_path_is_deterministic():

    path = shortest_path(
        "APARTMENT",
        "OLD_DISTRICT",
    )

    assert path == [
        "APARTMENT",
        "APARTMENT_DISTRICT",
        "STATION",
        "OLD_DISTRICT",
    ]

    assert (
        shortest_hops(
            "APARTMENT",
            "OLD_DISTRICT",
        )
        == 3
    )

    assert (
        next_hop(
            "APARTMENT",
            "OLD_DISTRICT",
        )
        == "APARTMENT_DISTRICT"
    )

# ======================================================
# 2. MOVE ONLY CROSSES ONE EDGE
# ======================================================

def test_move_does_not_teleport():

    simulation = Simulation()

    assert (
        simulation.player.location
        == "APARTMENT"
    )

    queue_action(
        actor_id="PLAYER_1",
        action="MOVE",

        target="OLD_DISTRICT",

        source="HUMAN",
    )

    simulation.tick()

    assert (
        simulation.player.location
        == "APARTMENT_DISTRICT"
    )

    assert (
        simulation.player.location
        != "OLD_DISTRICT"
    )

# ======================================================
# 3. EACH HOP COSTS ENERGY
# ======================================================

def test_travel_costs_energy_per_hop():

    simulation = Simulation()

    energy_before = (
        simulation.player.energy
    )

    queue_action(
        actor_id="PLAYER_1",
        action="MOVE",

        target="OLD_DISTRICT",

        source="HUMAN",
    )

    simulation.tick()

    assert (
        simulation.player.energy
        == pytest.approx(
            energy_before - 0.05
        )
    )

# ======================================================
# 4. MOVEMENT EVENT STORES ACTUAL ARRIVAL
# ======================================================

def test_movement_event_records_actual_arrival():

    simulation = Simulation()

    queue_action(
        actor_id="PLAYER_1",
        action="MOVE",

        target="OLD_DISTRICT",

        source="HUMAN",
    )

    simulation.tick()

    with get_connection() as conn:

        event = conn.execute(
            """
            SELECT
                target,
                details

            FROM events

            WHERE actor_id = 'PLAYER_1'
              AND action = 'MOVE'

            ORDER BY id DESC

            LIMIT 1
            """
        ).fetchone()

    assert event is not None

    target = event[0]
    details = event[1]

    assert (
        target
        == "APARTMENT_DISTRICT"
    )

    assert (
        "OLD_DISTRICT"
        in details
    )

    assert (
        "APARTMENT_DISTRICT"
        in details
    )
