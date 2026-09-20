import pytest

from server.api import (
    perform_player_step,
)

from server.world_core.beliefs import (
    load_belief,
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

from server.world_core.wired import (
    process_wired_message_acknowledgement,
)


def connect_to_wired(
    simulation: Simulation,
):

    process_wired_message_acknowledgement(
        message_id=INITIAL_MESSAGE_ID,
        player_id="PLAYER_1",
        minute=simulation.minute,
    )


def travel_to_station(
    simulation: Simulation,
):

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


def test_station_lead_starts_unverified():

    simulation = Simulation()
    connect_to_wired(simulation)

    belief = load_belief(
        "PLAYER_1",
        "NODE_07",
    )

    assert belief is not None
    assert belief.believed_location == "STATION"
    assert belief.source == "WIRED_MESSAGE"
    assert belief.confidence == pytest.approx(0.35)


def test_arriving_at_station_does_not_verify_until_next_perception():

    simulation = Simulation()
    connect_to_wired(simulation)
    travel_to_station(simulation)

    snapshot = build_player_snapshot()
    assert snapshot["player"]["location"] == "STATION"

    belief = load_belief("PLAYER_1", "NODE_07")
    assert belief.source == "WIRED_MESSAGE"
    assert belief.confidence == pytest.approx(0.35)


def test_observing_node_at_station_verifies_signal():

    simulation = Simulation()
    connect_to_wired(simulation)
    travel_to_station(simulation)

    perform_player_step(
        action="OBSERVE",
        target="NODE_07",
        simulation=simulation,
    )

    belief = load_belief("PLAYER_1", "NODE_07")
    assert belief is not None
    assert belief.believed_location == "STATION"
    assert belief.source == "DIRECT_PERCEPTION"
    assert belief.confidence == pytest.approx(0.85)


def test_verified_signal_remains_in_wired_projection():

    simulation = Simulation()
    connect_to_wired(simulation)
    travel_to_station(simulation)

    perform_player_step(
        action="OBSERVE",
        target="NODE_07",
        simulation=simulation,
    )

    signal_data = build_player_snapshot()["wired"]["signals"][0]

    assert signal_data["node_id"] == "NODE_07"
    assert signal_data["origin_source"] == "WIRED_MESSAGE"
    assert signal_data["current_source"] == "DIRECT_PERCEPTION"
    assert signal_data["verified"] is True
    assert signal_data["confidence"] == pytest.approx(0.85)


def test_station_verification_is_persistent():

    simulation = Simulation()
    connect_to_wired(simulation)
    travel_to_station(simulation)

    perform_player_step(
        action="OBSERVE",
        target="NODE_07",
        simulation=simulation,
    )

    Simulation()
    snapshot = build_player_snapshot()
    signal_data = snapshot["wired"]["signals"][0]

    assert snapshot["player"]["location"] == "STATION"
    assert signal_data["verified"] is True
    assert signal_data["current_source"] == "DIRECT_PERCEPTION"
