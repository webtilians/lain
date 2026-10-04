import pytest

from server.world_core.goal_engine import (
    select_goal,
)

from server.world_core.models import (
    Agent,
    SituationBelief,
)

from server.world_core.situation_beliefs import (
    list_situation_hypotheses,
    load_situation_belief,
    save_situation_belief,
)


SITUATION_ID = (
    "SIGNAL_SURGE_NODE_12"
)


def hypothesis(
    source: str,
    location: str,
    confidence: float,
    minute: int = 100,
):

    return SituationBelief(
        agent_id="AGENT_K",

        situation_id=(
            SITUATION_ID
        ),

        believed_type=(
            "SIGNAL_SURGE"
        ),

        believed_location=(
            location
        ),

        believed_subject_id=(
            "NODE_12"
        ),

        believed_status="OPEN",

        believed_severity=0.80,

        confidence=confidence,

        source=source,

        updated_minute=minute,
    )

# ======================================================
# 1. CONTRADICTORY HYPOTHESES COEXIST
# ======================================================

def test_contradictory_hypotheses_are_preserved():

    save_situation_belief(
        hypothesis(
            source="REPORT_ALPHA",
            location="STATION",
            confidence=0.80,
        )
    )

    save_situation_belief(
        hypothesis(
            source="REPORT_BETA",
            location="OLD_DISTRICT",
            confidence=0.75,
        )
    )

    hypotheses = list_situation_hypotheses(
        agent_id="AGENT_K",
        situation_id=SITUATION_ID,
    )

    assert len(hypotheses) == 2

    locations = {
        item.believed_location
        for item in hypotheses
    }

    assert locations == {
        "STATION",
        "OLD_DISTRICT",
    }

# ======================================================
# 2. NEAR-TIE CREATES UNCERTAINTY
# ======================================================

def test_competing_claims_reduce_working_confidence():

    save_situation_belief(
        hypothesis(
            source="REPORT_ALPHA",
            location="STATION",
            confidence=0.80,
        )
    )

    save_situation_belief(
        hypothesis(
            source="REPORT_BETA",
            location="OLD_DISTRICT",
            confidence=0.75,
        )
    )

    belief = load_situation_belief(
        "AGENT_K",
        SITUATION_ID,
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "STATION"
    )

    assert (
        belief.confidence
        == pytest.approx(0.05)
    )

# ======================================================
# 3. AMBIGUITY PREVENTS PREMATURE ACTION
# ======================================================

def test_agent_does_not_act_on_near_tied_claims():

    save_situation_belief(
        hypothesis(
            source="REPORT_ALPHA",
            location="STATION",
            confidence=0.80,
        )
    )

    save_situation_belief(
        hypothesis(
            source="REPORT_BETA",
            location="OLD_DISTRICT",
            confidence=0.75,
        )
    )

    belief = load_situation_belief(
        "AGENT_K",
        SITUATION_ID,
    )

    k = Agent(
        id="AGENT_K",
        name="K",

        faction="PROTOCOL",

        location=(
            "APARTMENT_DISTRICT"
        ),

        goal="IDLE",
    )

    goal = select_goal(
        agent=k,

        situation_beliefs=[
            belief
        ],

        actor_beliefs=[],

        actor_location_beliefs=[],

        minute=100,
    )

    assert goal is None

# ======================================================
# 4. AGREEMENT REINFORCES A CLAIM
# ======================================================

def test_independent_agreement_strengthens_belief():

    save_situation_belief(
        hypothesis(
            source="REPORT_ALPHA",
            location="OLD_DISTRICT",
            confidence=0.80,
        )
    )

    save_situation_belief(
        hypothesis(
            source="REPORT_BETA",
            location="OLD_DISTRICT",
            confidence=0.75,
        )
    )

    belief = load_situation_belief(
        "AGENT_K",
        SITUATION_ID,
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "OLD_DISTRICT"
    )

    assert (
        belief.confidence
        == pytest.approx(0.85)
    )

# ======================================================
# 5. AUTHORITATIVE NETWORK SETTLES REPORT DISPUTE
# ======================================================

def test_network_information_supersedes_report_competition():

    save_situation_belief(
        hypothesis(
            source="REPORT_ALPHA",
            location="STATION",
            confidence=0.90,
        )
    )

    save_situation_belief(
        hypothesis(
            source="REPORT_BETA",
            location="APARTMENT",
            confidence=0.85,
        )
    )

    save_situation_belief(
        hypothesis(
            source="PROTOCOL_NETWORK",
            location="OLD_DISTRICT",
            confidence=0.80,
            minute=120,
        )
    )

    belief = load_situation_belief(
        "AGENT_K",
        SITUATION_ID,
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "OLD_DISTRICT"
    )

    assert (
        belief.confidence
        == pytest.approx(0.80)
    )

    assert (
        belief.source
        == "PROTOCOL_NETWORK"
    )

    hypotheses = list_situation_hypotheses(
        "AGENT_K",
        SITUATION_ID,
    )

    assert len(hypotheses) == 3

# ======================================================
# 6. DIRECT PERCEPTION HAS HIGHEST AUTHORITY
# ======================================================

def test_direct_observation_settles_network_disagreement():

    save_situation_belief(
        hypothesis(
            source="PROTOCOL_NETWORK",
            location="STATION",
            confidence=0.90,
        )
    )

    save_situation_belief(
        hypothesis(
            source=(
                "DIRECT_SITUATION_PERCEPTION"
            ),

            location="OLD_DISTRICT",

            confidence=0.95,

            minute=130,
        )
    )

    belief = load_situation_belief(
        "AGENT_K",
        SITUATION_ID,
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "OLD_DISTRICT"
    )

    assert (
        belief.confidence
        == pytest.approx(0.95)
    )

    assert (
        belief.source
        == "DIRECT_SITUATION_PERCEPTION"
    )
