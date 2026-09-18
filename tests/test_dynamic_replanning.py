from server.world_core.database import (
    get_connection,
    load_or_create_node,
    save_node,
)

from server.world_core.models import (
    WorldNode,
)

from server.world_core.simulation import (
    Simulation,
)


def test_agent_replans_and_reverses_route_when_world_changes():

    simulation = Simulation()

    k = simulation.k.agent

    # ==================================================
    # INITIAL WORLD
    #
    # K starts here:
    #
    # APARTMENT
    #      |
    # APARTMENT_DISTRICT   <- K
    #      |
    # STATION              NODE_07 quiet
    #      |
    # OLD_DISTRICT         NODE_12 crisis
    #
    # ==================================================

    node_07 = (
        simulation.nodes[
            "NODE_07"
        ]
    )

    node_12 = (
        simulation.nodes[
            "NODE_12"
        ]
    )

    node_07.anomaly_strength = 0.10
    node_12.anomaly_strength = 0.95

    save_node(
        node_07
    )

    save_node(
        node_12
    )

    # Add another possible crisis behind K.
    #
    # It starts quiet.

    node_21 = load_or_create_node(
        WorldNode(
            id="NODE_21",
            location="APARTMENT",
            node_type="UNKNOWN_SIGNAL",
            discovered=False,
            active=True,
            anomaly_strength=0.10,
        )
    )

    simulation.nodes[
        node_21.id
    ] = node_21

    assert (
        k.location
        == "APARTMENT_DISTRICT"
    )

    # ==================================================
    # TICK 1
    #
    # NODE_12 is the only important crisis.
    # K should start travelling toward OLD_DISTRICT.
    #
    # APARTMENT_DISTRICT
    #       |
    #       v
    #    STATION
    #       |
    # OLD_DISTRICT
    #
    # ==================================================

    simulation.tick()

    first_goal = (
        simulation.current_goals[
            "AGENT_K"
        ]
    )

    assert first_goal is not None

    assert (
        first_goal.target_id
        == "NODE_12"
    )

    assert (
        first_goal.goal_type
        == "REDUCE_SIGNAL_SURGE"
    )

    # K has only crossed one edge.

    assert (
        k.location
        == "STATION"
    )

    # ==================================================
    # WORLD CHANGES WHILE K IS TRAVELLING
    #
    # NODE_12 suddenly stabilizes.
    #
    # NODE_21, behind K, becomes critical.
    #
    # ==================================================

    node_12.anomaly_strength = 0.20

    node_21.anomaly_strength = 0.95

    save_node(
        node_12
    )

    save_node(
        node_21
    )

    # ==================================================
    # TICK 2
    #
    # K must NOT continue blindly to OLD_DISTRICT.
    #
    # It should recalculate the world,
    # choose NODE_21,
    # and reverse direction.
    #
    # OLD_DISTRICT
    #      |
    #   STATION        <- K was here
    #      |
    # APARTMENT_DISTRICT
    #      ^
    #      |
    # K moves back this way
    #
    #      |
    # APARTMENT        NODE_21 crisis
    #
    # ==================================================

    simulation.tick()

    second_goal = (
        simulation.current_goals[
            "AGENT_K"
        ]
    )

    assert second_goal is not None

    assert (
        second_goal.target_id
        == "NODE_21"
    )

    assert (
        second_goal.goal_type
        == "REDUCE_SIGNAL_SURGE"
    )

    # This is the crucial assertion.
    #
    # If K were following a stored OLD_DISTRICT
    # route blindly it would now be there.
    #
    # Instead it has reversed toward APARTMENT.

    assert (
        k.location
        == "APARTMENT_DISTRICT"
    )

    assert (
        k.location
        != "OLD_DISTRICT"
    )

    # ==================================================
    # EVENT HISTORY MUST ALSO SHOW THE NEW DIRECTION
    # ==================================================

    with get_connection() as conn:

        event = conn.execute(
            """
            SELECT
                target,
                details

            FROM events

            WHERE actor_id = 'AGENT_K'
              AND action = 'MOVE'

            ORDER BY id DESC

            LIMIT 1
            """
        ).fetchone()

    assert event is not None

    actual_arrival = event[0]
    details = event[1]

    assert (
        actual_arrival
        == "APARTMENT_DISTRICT"
    )

    assert (
        "APARTMENT"
        in details
    )

    # ==================================================
    # TICK 3
    #
    # K should finish the new journey.
    # ==================================================

    simulation.tick()

    third_goal = (
        simulation.current_goals[
            "AGENT_K"
        ]
    )

    assert third_goal is not None

    assert (
        third_goal.target_id
        == "NODE_21"
    )

    assert (
        k.location
        == "APARTMENT"
    )
