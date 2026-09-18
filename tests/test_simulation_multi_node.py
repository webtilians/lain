import pytest

from server.situations.engine import (
    load_situation,
)

from server.world_core.action_queue import (
    queue_action,
)

from server.world_core.knowledge import (
    knows_node,
)

from server.world_core.simulation import (
    Simulation,
)


def move_player_to(
    simulation,
    destination,
    max_ticks=10,
):

    for _ in range(
        max_ticks
    ):

        if (
            simulation.player.location
            == destination
        ):
            return

        queue_action(
            actor_id="PLAYER_1",
            action="MOVE",
            target=destination,
            source="HUMAN",
        )

        simulation.tick()

    pytest.fail(
        f"PLAYER_1 failed to reach "
        f"{destination}"
    )


def test_simulation_bootstraps_multiple_nodes():

    simulation = Simulation()

    assert set(
        simulation.nodes.keys()
    ) == {
        "NODE_07",
        "NODE_12",
    }

    assert (
        simulation.nodes[
            "NODE_07"
        ].location
        == "STATION"
    )

    assert (
        simulation.nodes[
            "NODE_12"
        ].location
        == "OLD_DISTRICT"
    )


def test_player_can_discover_and_modify_second_node():

    simulation = Simulation()

    # ----------------------------------------------
    # PLAYER MOVES TO NODE_12
    # ----------------------------------------------

    move_player_to(
        simulation,
        "OLD_DISTRICT",
    )

    assert (
        simulation.player.location
        == "OLD_DISTRICT"
    )

    # Perception happens before actions,
    # therefore one more tick is required.

    simulation.tick()

    assert knows_node(
        "PLAYER_1",
        "NODE_12",
    )

    node_12_before = (
        simulation.nodes[
            "NODE_12"
        ].anomaly_strength
    )

    # ----------------------------------------------
    # PLAYER MANIPULATES NODE_12
    # ----------------------------------------------

    queue_action(
        actor_id="PLAYER_1",
        action="AMPLIFY",
        target="NODE_12",
        source="HUMAN",
    )

    simulation.tick()

    node_12_after = (
        simulation.nodes[
            "NODE_12"
        ].anomaly_strength
    )

    assert (
        node_12_after
        == pytest.approx(
            min(
                1.0,
                node_12_before + 0.10,
            )
        )
    )

    # ----------------------------------------------
    # CONSEQUENCE BELONGS TO NODE_12
    # ----------------------------------------------

    situation = load_situation(
        "UNAUTHORIZED_MANIPULATION_NODE_12"
    )

    assert situation is not None

    assert (
        situation.subject_id
        == "NODE_12"
    )

    assert (
        situation.location
        == "OLD_DISTRICT"
    )
