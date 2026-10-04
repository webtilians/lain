import pytest

from server.world_core.database import (
    save_agent,
    save_node,
)

from server.world_core.goal_engine import (
    select_goal,
)

from server.world_core.locations import (
    shortest_hops,
)

from server.world_core.models import (
    Agent,
    SituationBelief,
)

from server.world_core.simulation import (
    Simulation,
)


def situation_belief(
    agent_id: str,

    situation_id: str,

    node_id: str,
    location: str,

    severity: float,
    confidence: float,
):

    return SituationBelief(
        agent_id=agent_id,

        situation_id=(
            situation_id
        ),

        believed_type=(
            "SIGNAL_SURGE"
        ),

        believed_location=(
            location
        ),

        believed_subject_id=(
            node_id
        ),

        believed_status="OPEN",

        believed_severity=(
            severity
        ),

        confidence=(
            confidence
        ),

        source="TEST",

        updated_minute=100,
    )


# ======================================================
# 1. WORLD TOPOLOGY
# ======================================================

def test_location_graph_has_deterministic_distance():

    assert (
        shortest_hops(
            "STATION",
            "OLD_DISTRICT",
        )
        == 1
    )

    assert (
        shortest_hops(
            "APARTMENT_DISTRICT",
            "OLD_DISTRICT",
        )
        == 2
    )

    assert (
        shortest_hops(
            "APARTMENT",
            "OLD_DISTRICT",
        )
        == 3
    )

    assert (
        shortest_hops(
            "STATION",
            "STATION",
        )
        == 0
    )


# ======================================================
# 2. DISTANCE CAN CHANGE WHICH CRISIS WINS
# ======================================================

def test_agent_balances_severity_against_distance():

    k = Agent(
        id="AGENT_K",
        name="K",

        faction="PROTOCOL",

        location=(
            "APARTMENT_DISTRICT"
        ),

        goal="IDLE",
    )

    station_crisis = (
        situation_belief(
            agent_id=k.id,

            situation_id=(
                "SIGNAL_SURGE_NODE_07"
            ),

            node_id="NODE_07",
            location="STATION",

            severity=0.70,
            confidence=0.80,
        )
    )

    old_district_crisis = (
        situation_belief(
            agent_id=k.id,

            situation_id=(
                "SIGNAL_SURGE_NODE_12"
            ),

            node_id="NODE_12",

            location="OLD_DISTRICT",

            severity=0.80,
            confidence=0.80,
        )
    )

    goal = select_goal(
        agent=k,

        situation_beliefs=[
            station_crisis,
            old_district_crisis,
        ],

        actor_beliefs=[],

        actor_location_beliefs=[],

        minute=100,
    )

    assert goal is not None

    # NODE_12 is somewhat more severe,
    # but NODE_07 is one hop closer.

    assert (
        goal.target_id
        == "NODE_07"
    )


# ======================================================
# 3. LIVE SIMULATION SPLITS AGENTS BETWEEN CRISES
# ======================================================

def test_simulation_splits_agents_between_two_crises():

    simulation = Simulation()

    simulation.nora.agent.energy = 0.0

    save_agent(
        simulation.nora.agent
    )

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

    node_07.anomaly_strength = 0.70
    node_12.anomaly_strength = 0.65

    save_node(
        node_07
    )

    save_node(
        node_12
    )

    simulation.tick()
    simulation.tick()
    simulation.tick()

    k_goal = (
        simulation.current_goals[
            "AGENT_K"
        ]
    )

    nora_goal = (
        simulation.current_goals[
            "AGENT_NORA"
        ]
    )

    assert k_goal is not None
    assert nora_goal is not None

    # K starts in APARTMENT_DISTRICT.
    # STATION is closer than OLD_DISTRICT.

    assert (
        k_goal.target_id
        == "NODE_07"
    )

    assert (
        k_goal.goal_type
        == "REDUCE_SIGNAL_SURGE"
    )

    # Nora starts directly in OLD_DISTRICT
    # and sees NODE_12 with high confidence.

    assert (
        nora_goal.target_id
        == "NODE_12"
    )

    assert (
        nora_goal.goal_type
        == "EXPAND_SIGNAL_SURGE"
    )

    # K should begin moving towards NODE_07.

    assert (
        simulation.k.agent.location
        == "STATION"
    )

