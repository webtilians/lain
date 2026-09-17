from server.situations.engine import (
    evaluate_nodes,
    load_situation,
)

from server.world_core.database import (
    load_or_create_node,
    record_event,
)

from server.world_core.models import (
    WorldNode,
    WorldState,
)


def create_node(
    node_id: str,
    location: str,
    anomaly: float,
):

    return load_or_create_node(
        WorldNode(
            id=node_id,
            location=location,
            node_type="UNKNOWN_SIGNAL",
            discovered=False,
            active=True,
            anomaly_strength=anomaly,
        )
    )


# ======================================================
# 1. MULTIPLE NODES EXIST INDEPENDENTLY
# ======================================================

def test_multiple_nodes_generate_independent_situations():

    node_07 = create_node(
        node_id="NODE_07",
        location="STATION",
        anomaly=0.80,
    )

    node_12 = create_node(
        node_id="NODE_12",
        location="OLD_DISTRICT",
        anomaly=0.10,
    )

    world = WorldState(
        signal=0.10,
        stability=0.90,
        connection=0.35,
    )

    evaluate_nodes(
        world=world,
        nodes=[
            node_07,
            node_12,
        ],
        minute=100,
    )

    node_07_situation = (
        load_situation(
            "SIGNAL_SURGE_NODE_07"
        )
    )

    node_12_situation = (
        load_situation(
            "SIGNAL_SURGE_NODE_12"
        )
    )

    assert (
        node_07_situation
        is not None
    )

    assert (
        node_07_situation.location
        == "STATION"
    )

    assert (
        node_07_situation.subject_id
        == "NODE_07"
    )

    # NODE_12 is quiet.
    # It must NOT inherit NODE_07's crisis.

    assert (
        node_12_situation
        is None
    )


# ======================================================
# 2. PLAYER MANIPULATION IS NODE-SPECIFIC
# ======================================================

def test_unauthorized_manipulation_is_node_specific():

    node_07 = create_node(
        node_id="NODE_07",
        location="STATION",
        anomaly=0.10,
    )

    node_12 = create_node(
        node_id="NODE_12",
        location="OLD_DISTRICT",
        anomaly=0.10,
    )

    world = WorldState(
        signal=0.10,
        stability=0.90,
        connection=0.35,
    )

    record_event(
        minute=100,

        actor_id="PLAYER_1",

        action="AMPLIFY",

        target="NODE_12",

        details=(
            "Player manipulated NODE_12"
        ),
    )

    evaluate_nodes(
        world=world,
        nodes=[
            node_07,
            node_12,
        ],
        minute=110,
    )

    node_07_manipulation = (
        load_situation(
            "UNAUTHORIZED_MANIPULATION_NODE_07"
        )
    )

    node_12_manipulation = (
        load_situation(
            "UNAUTHORIZED_MANIPULATION_NODE_12"
        )
    )

    assert (
        node_07_manipulation
        is None
    )

    assert (
        node_12_manipulation
        is not None
    )

    assert (
        node_12_manipulation.subject_id
        == "NODE_12"
    )

    assert (
        node_12_manipulation.location
        == "OLD_DISTRICT"
    )

    assert (
        "PLAYER_1"
        in node_12_manipulation.reason
    )


def test_global_signal_does_not_activate_quiet_node():

    node = create_node(
        node_id="NODE_12",
        location="OLD_DISTRICT",
        anomaly=0.10,
    )

    world = WorldState(
        signal=0.90,
        stability=0.50,
        connection=0.80,
    )

    evaluate_nodes(
        world=world,
        nodes=[node],
        minute=100,
    )

    situation = load_situation(
        "SIGNAL_SURGE_NODE_12"
    )

    assert situation is None
