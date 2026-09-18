from server.situations.engine import (
    load_situation,
)

from server.world_core.database import (
    save_node,
)

from server.world_core.models import (
    Agent,
)

from server.world_core.reports import (
    InformationReport,
    create_information_report,
    process_information_reports,
)

from server.world_core.situation_beliefs import (
    load_situation_belief,
)

from server.world_core.simulation import (
    Simulation,
)


def fake_report(
    report_id="FALSE_REPORT_1",
    deliver_minute=10,
):

    return InformationReport(
        id=report_id,

        situation_id=(
            "SIGNAL_SURGE_NODE_12"
        ),

        claimed_type=(
            "SIGNAL_SURGE"
        ),

        # False location.
        claimed_location="STATION",

        claimed_subject_id=(
            "NODE_12"
        ),

        claimed_status="OPEN",

        claimed_severity=0.95,
        confidence=0.90,

        source=(
            "COMPROMISED_PROTOCOL_RELAY"
        ),

        target_actor_id=(
            "AGENT_K"
        ),

        target_faction=None,

        created_minute=0,
        deliver_minute=deliver_minute,
    )

# ======================================================
# 1. REPORT RESPECTS DELIVERY TIME
# ======================================================

def test_false_report_is_not_known_before_delivery():

    k = Agent(
        id="AGENT_K",
        name="K",
        faction="PROTOCOL",

        location=(
            "APARTMENT_DISTRICT"
        ),

        goal="IDLE",
    )

    create_information_report(
        fake_report(
            deliver_minute=20
        )
    )

    accepted = (
        process_information_reports(
            agent=k,
            current_minute=10,
        )
    )

    assert accepted == []

    belief = load_situation_belief(
        "AGENT_K",
        "SIGNAL_SURGE_NODE_12",
    )

    assert belief is None

# ======================================================
# 2. FALSE INFORMATION CREATES A REAL BELIEF
# ======================================================

def test_false_report_creates_belief_without_changing_reality():

    k = Agent(
        id="AGENT_K",
        name="K",
        faction="PROTOCOL",

        location=(
            "APARTMENT_DISTRICT"
        ),

        goal="IDLE",
    )

    create_information_report(
        fake_report()
    )

    process_information_reports(
        agent=k,
        current_minute=10,
    )

    belief = load_situation_belief(
        "AGENT_K",
        "SIGNAL_SURGE_NODE_12",
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "STATION"
    )

    assert (
        belief.believed_severity
        == 0.95
    )

    assert (
        belief.source
        == "COMPROMISED_PROTOCOL_RELAY"
    )

    # Information alone does not create reality.

    assert (
        load_situation(
            "SIGNAL_SURGE_NODE_12"
        )
        is None
    )

# ======================================================
# 3. SAME REPORT IS DELIVERED ONLY ONCE
# ======================================================

def test_report_cannot_be_replayed_forever():

    k = Agent(
        id="AGENT_K",
        name="K",
        faction="PROTOCOL",

        location=(
            "APARTMENT_DISTRICT"
        ),

        goal="IDLE",
    )

    create_information_report(
        fake_report()
    )

    first = process_information_reports(
        agent=k,
        current_minute=10,
    )

    second = process_information_reports(
        agent=k,
        current_minute=20,
    )

    assert len(first) == 1
    assert second == []

# ======================================================
# 4. AGENT ACTS ON FALSE REPORT THEN CORRECTS
# ======================================================

def test_agent_moves_on_false_information_then_replans():

    simulation = Simulation()

    # Isolate K for this causal test.

    simulation.ai_actors = [
        simulation.k
    ]

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

    # NODE_07 is quiet.
    #
    # NODE_12 is really in crisis at
    # OLD_DISTRICT.

    node_07.anomaly_strength = 0.10
    node_12.anomaly_strength = 0.80

    save_node(node_07)
    save_node(node_12)

    # But K receives a compromised report
    # saying NODE_12 is at STATION.

    create_information_report(
        fake_report(
            deliver_minute=10
        )
    )

    # ==================================================
    # MINUTE 10
    #
    # Reality creates crisis at OLD_DISTRICT.
    #
    # Protocol network has not propagated it yet.
    #
    # False report says STATION.
    # ==================================================

    simulation.tick()

    reality = load_situation(
        "SIGNAL_SURGE_NODE_12"
    )

    assert reality is not None

    assert (
        reality.location
        == "OLD_DISTRICT"
    )

    belief = load_situation_belief(
        "AGENT_K",
        "SIGNAL_SURGE_NODE_12",
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "STATION"
    )

    assert (
        belief.source
        == "COMPROMISED_PROTOCOL_RELAY"
    )

    goal = (
        simulation.current_goals[
            "AGENT_K"
        ]
    )

    assert goal is not None

    assert (
        goal.target_id
        == "NODE_12"
    )

    assert (
        goal.believed_location
        == "STATION"
    )

    # K acts rationally on false information.

    assert (
        simulation.k.agent.location
        == "STATION"
    )

    # ==================================================
    # MINUTE 20
    #
    # Real Protocol information still has not
    # completed its 20 minute latency.
    # ==================================================

    simulation.tick()

    belief = load_situation_belief(
        "AGENT_K",
        "SIGNAL_SURGE_NODE_12",
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "STATION"
    )

    # ==================================================
    # MINUTE 30
    #
    # The real network report now arrives.
    #
    # It overwrites the compromised belief.
    # ==================================================

    simulation.tick()

    belief = load_situation_belief(
        "AGENT_K",
        "SIGNAL_SURGE_NODE_12",
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "OLD_DISTRICT"
    )

    assert (
        belief.source
        == "PROTOCOL_NETWORK"
    )

    goal = (
        simulation.current_goals[
            "AGENT_K"
        ]
    )

    assert goal is not None

    assert (
        goal.believed_location
        == "OLD_DISTRICT"
    )

    # STATION -> OLD_DISTRICT is one edge.
    #
    # K corrects its route as soon as its
    # belief is corrected.

    assert (
        simulation.k.agent.location
        == "OLD_DISTRICT"
    )
