from server.situations.engine import (
    Situation,
    load_situation,
)

from server.world_core.database import (
    save_node,
)

from server.world_core.models import (
    Agent,
)

from server.world_core.situation_beliefs import (
    load_situation_belief,
)

from server.world_core.situation_perception import (
    perceive_situation,
)

from server.world_core.simulation import (
    Simulation,
)


def make_situation():

    return Situation(
        id="SIGNAL_SURGE_NODE_TEST",

        situation_type=(
            "SIGNAL_SURGE"
        ),

        location="OLD_DISTRICT",
        subject_id="NODE_TEST",

        status="OPEN",
        severity=0.60,

        created_minute=100,
        updated_minute=100,

        reason="test",

        status_changed_minute=100,
    )

# ======================================================
# 1. PROTOCOL HAS 20 MIN LATENCY
# ======================================================

def test_protocol_network_is_delayed():

    k = Agent(
        id="AGENT_K",
        name="K",
        faction="PROTOCOL",

        location=(
            "APARTMENT_DISTRICT"
        ),

        goal="IDLE",
    )

    situation = make_situation()

    early = perceive_situation(
        agent=k,
        situation=situation,
        minute=110,
    )

    assert early is None

    delivered = perceive_situation(
        agent=k,
        situation=situation,
        minute=120,
    )

    assert delivered is not None

    assert (
        delivered.source
        == "PROTOCOL_NETWORK"
    )

# ======================================================
# 2. WIRED IS FASTER
# ======================================================

def test_wired_network_arrives_before_protocol():

    nora = Agent(
        id="AGENT_NORA",
        name="Nora",
        faction="WIRED",

        location="STATION",

        goal="IDLE",
    )

    situation = make_situation()

    belief = perceive_situation(
        agent=nora,
        situation=situation,
        minute=110,
    )

    assert belief is not None

    assert (
        belief.source
        == "WIRED_NETWORK"
    )

# ======================================================
# 3. DIRECT PERCEPTION BYPASSES LATENCY
# ======================================================

def test_direct_perception_is_immediate():

    k = Agent(
        id="AGENT_K",
        name="K",
        faction="PROTOCOL",

        location="OLD_DISTRICT",

        goal="IDLE",
    )

    situation = make_situation()

    belief = perceive_situation(
        agent=k,
        situation=situation,
        minute=100,
    )

    assert belief is not None

    assert (
        belief.source
        == "DIRECT_SITUATION_PERCEPTION"
    )

    assert (
        belief.confidence
        == 0.95
    )

# ======================================================
# 4. AGENT ACTS ON STALE INFORMATION
# ======================================================

def test_agent_continues_toward_resolved_crisis_until_it_knows():

    simulation = Simulation()

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

    # NODE_07 quiet.
    # Remote NODE_12 crisis.

    node_07.anomaly_strength = 0.10
    node_12.anomaly_strength = 0.60

    save_node(node_07)
    save_node(node_12)

    # ----------------------------------------------
    # minute 10
    #
    # Situation exists, but Protocol does not
    # know yet.
    # ----------------------------------------------

    simulation.tick()

    assert (
        simulation.current_goals[
            "AGENT_K"
        ]
        is None
    )

    # ----------------------------------------------
    # minute 20
    #
    # Still only 10 minutes old.
    # ----------------------------------------------

    simulation.tick()

    assert (
        simulation.current_goals[
            "AGENT_K"
        ]
        is None
    )

    # ----------------------------------------------
    # minute 30
    #
    # Protocol receives the crisis.
    # K starts travelling.
    # ----------------------------------------------

    simulation.tick()

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
        simulation.k.agent.location
        == "STATION"
    )

    # ----------------------------------------------
    # Reality changes now.
    # K does NOT magically know it.
    # ----------------------------------------------

    node_12.anomaly_strength = 0.20

    save_node(
        node_12
    )

    # ----------------------------------------------
    # minute 40
    #
    # World Core resolves the situation.
    #
    # Protocol has not received that resolution.
    # K still believes it is OPEN.
    # ----------------------------------------------

    simulation.tick()

    reality = load_situation(
        "SIGNAL_SURGE_NODE_12"
    )

    assert reality is not None

    assert (
        reality.status
        == "RESOLVED"
    )

    belief = load_situation_belief(
        "AGENT_K",
        "SIGNAL_SURGE_NODE_12",
    )

    assert belief is not None

    assert (
        belief.believed_status
        == "OPEN"
    )

    # K therefore continues to the location.

    assert (
        simulation.k.agent.location
        == "OLD_DISTRICT"
    )

    # ----------------------------------------------
    # minute 50
    #
    # K is physically there.
    # Direct perception overrides stale network info.
    # ----------------------------------------------

    simulation.tick()

    belief = load_situation_belief(
        "AGENT_K",
        "SIGNAL_SURGE_NODE_12",
    )

    assert belief is not None

    assert (
        belief.believed_status
        == "RESOLVED"
    )

    assert (
        belief.source
        == "DIRECT_SITUATION_PERCEPTION"
    )
