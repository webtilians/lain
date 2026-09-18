import pytest

from server.world_core.goal_engine import (
    select_goal,
)

from server.world_core.models import (
    ActorBelief,
    ActorLocationBelief,
    Agent,
    SituationBelief,
)

from server.world_core.situation_beliefs import (
    decay_situation_beliefs,
    list_situation_hypotheses,
    load_situation_belief,
    save_situation_belief,
)


def make_k():

    return Agent(
        id="AGENT_K",
        name="K",

        faction="PROTOCOL",

        location="STATION",

        goal="IDLE",
    )


def suspect_belief():

    return ActorBelief(
        observer_id="AGENT_K",

        subject_actor_id=(
            "PLAYER_1"
        ),

        belief_type=(
            "LIKELY_UNAUTHORIZED_MANIPULATOR"
        ),

        confidence=0.82,

        source_evidence_id="TRACE_1",

        updated_minute=100,
    )

# ======================================================
# 1. STALE DIRECT SIGHTING CANNOT CONTACT
# ======================================================

def test_stale_direct_actor_perception_cannot_contact():

    k = make_k()

    location = ActorLocationBelief(
        observer_id=k.id,

        subject_actor_id="PLAYER_1",

        believed_location="STATION",

        confidence=0.97,

        source=(
            "DIRECT_ACTOR_PERCEPTION"
        ),

        source_event_id=-1,

        updated_minute=90,
    )

    goal = select_goal(
        agent=k,

        situation_beliefs=[],

        actor_beliefs=[
            suspect_belief()
        ],

        actor_location_beliefs=[
            location
        ],

        minute=100,
    )

    assert goal is not None

    assert (
        goal.goal_type
        == "LOCATE_SUSPECT"
    )

# ======================================================
# 2. CURRENT DIRECT SIGHTING CAN CONTACT
# ======================================================

def test_current_direct_actor_perception_can_contact():

    k = make_k()

    location = ActorLocationBelief(
        observer_id=k.id,

        subject_actor_id="PLAYER_1",

        believed_location="STATION",

        confidence=0.99,

        source=(
            "DIRECT_ACTOR_PERCEPTION"
        ),

        source_event_id=-1,

        updated_minute=100,
    )

    goal = select_goal(
        agent=k,

        situation_beliefs=[],

        actor_beliefs=[
            suspect_belief()
        ],

        actor_location_beliefs=[
            location
        ],

        minute=100,
    )

    assert goal is not None

    assert (
        goal.goal_type
        == "CONTACT_SUSPECT"
    )

# ======================================================
# 3. HYPOTHESIS DECAY IS DETERMINISTIC
# ======================================================

def test_hypothesis_confidence_ages_without_compounding():

    save_situation_belief(
        SituationBelief(
            agent_id="AGENT_K",

            situation_id=(
                "SIGNAL_SURGE_NODE_12"
            ),

            believed_type="SIGNAL_SURGE",

            believed_location=(
                "OLD_DISTRICT"
            ),

            believed_subject_id=(
                "NODE_12"
            ),

            believed_status="OPEN",

            believed_severity=0.80,

            confidence=0.80,

            source="REPORT_A",

            updated_minute=100,
        )
    )

    decay_situation_beliefs(
        agent_id="AGENT_K",
        current_minute=120,
    )

    belief = load_situation_belief(
        "AGENT_K",
        "SIGNAL_SURGE_NODE_12",
    )

    assert belief is not None

    assert (
        belief.confidence
        == pytest.approx(0.70)
    )

    assert (
        belief.updated_minute
        == 100
    )

    decay_situation_beliefs(
        agent_id="AGENT_K",
        current_minute=120,
    )

    belief_again = load_situation_belief(
        "AGENT_K",
        "SIGNAL_SURGE_NODE_12",
    )

    assert (
        belief_again.confidence
        == pytest.approx(0.70)
    )

# ======================================================
# 4. OLD DIRECT OBSERVATION CANNOT DOMINATE FOREVER
# ======================================================

def test_new_network_information_supersedes_stale_direct_observation():

    situation_id = (
        "SIGNAL_SURGE_NODE_12"
    )

    save_situation_belief(
        SituationBelief(
            agent_id="AGENT_K",

            situation_id=situation_id,

            believed_type="SIGNAL_SURGE",

            believed_location="STATION",

            believed_subject_id=(
                "NODE_12"
            ),

            believed_status="OPEN",

            believed_severity=0.80,

            confidence=0.95,

            source=(
                "DIRECT_SITUATION_PERCEPTION"
            ),

            updated_minute=100,
        )
    )

    save_situation_belief(
        SituationBelief(
            agent_id="AGENT_K",

            situation_id=situation_id,

            believed_type="SIGNAL_SURGE",

            believed_location=(
                "OLD_DISTRICT"
            ),

            believed_subject_id=(
                "NODE_12"
            ),

            believed_status="OPEN",

            believed_severity=0.75,

            confidence=0.80,

            source="PROTOCOL_NETWORK",

            updated_minute=120,
        )
    )

    belief = load_situation_belief(
        "AGENT_K",
        situation_id,
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

    hypotheses = list_situation_hypotheses(
        "AGENT_K",
        situation_id,
    )

    assert {
        item.source
        for item in hypotheses
    } == {
        "DIRECT_SITUATION_PERCEPTION",
        "PROTOCOL_NETWORK",
    }
