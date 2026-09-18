import pytest

from server.world_core.belief_provenance import (
    list_belief_revisions,
)

from server.world_core.models import (
    SituationBelief,
)

from server.world_core.situation_beliefs import (
    save_situation_belief,
)


AGENT_ID = "AGENT_K"

SITUATION_ID = (
    "SIGNAL_SURGE_NODE_12"
)


def belief(
    source: str,
    location: str,

    confidence: float,

    minute: int = 100,

    status: str = "OPEN",
):

    return SituationBelief(
        agent_id=AGENT_ID,

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

        believed_status=status,

        believed_severity=0.80,

        confidence=confidence,

        source=source,

        updated_minute=minute,
    )

# ======================================================
# 1. FIRST BELIEF CREATES INITIAL PROVENANCE
# ======================================================

def test_initial_working_belief_is_recorded():

    save_situation_belief(
        belief(
            source="REPORT_A",
            location="STATION",
            confidence=0.80,
        )
    )

    revisions = list_belief_revisions(
        AGENT_ID,
        SITUATION_ID,
    )

    assert len(revisions) == 1

    revision = revisions[0]

    assert (
        revision.revision_type
        == "INITIALIZED"
    )

    assert revision.previous_claim is None

    assert (
        revision.new_claim[
            "location"
        ]
        == "STATION"
    )

    assert revision.new_source == "REPORT_A"

# ======================================================
# 2. IDENTICAL INFORMATION DOES NOT CREATE NOISE
# ======================================================

def test_identical_belief_does_not_create_revision_noise():

    save_situation_belief(
        belief(
            source="REPORT_A",
            location="STATION",
            confidence=0.80,
            minute=100,
        )
    )

    save_situation_belief(
        belief(
            source="REPORT_A",
            location="STATION",
            confidence=0.80,
            minute=110,
        )
    )

    revisions = list_belief_revisions(
        AGENT_ID,
        SITUATION_ID,
    )

    assert len(revisions) == 1

# ======================================================
# 3. COMPETITION CREATES CONFIDENCE REVISION
# ======================================================

def test_epistemic_conflict_records_confidence_collapse():

    save_situation_belief(
        belief(
            source="REPORT_A",
            location="STATION",
            confidence=0.80,
        )
    )

    save_situation_belief(
        belief(
            source="REPORT_B",
            location="OLD_DISTRICT",
            confidence=0.75,
            minute=110,
        )
    )

    revisions = list_belief_revisions(
        AGENT_ID,
        SITUATION_ID,
    )

    assert len(revisions) == 2

    revision = revisions[-1]

    assert (
        revision.revision_type
        == "CONFIDENCE_SHIFT"
    )

    assert (
        revision.previous_confidence
        == pytest.approx(0.80)
    )

    assert (
        revision.new_confidence
        == pytest.approx(0.05)
    )

    assert "REPORT_A" in revision.supporting_sources
    assert "REPORT_B" in revision.opposing_sources

# ======================================================
# 4. DIRECT EVIDENCE RECORDS CLAIM REVISION
# ======================================================

def test_direct_perception_records_why_claim_changed():

    save_situation_belief(
        belief(
            source="REPORT_A",
            location="STATION",
            confidence=0.80,
        )
    )

    save_situation_belief(
        belief(
            source="REPORT_B",
            location="OLD_DISTRICT",
            confidence=0.75,
            minute=110,
        )
    )

    save_situation_belief(
        belief(
            source=(
                "DIRECT_SITUATION_PERCEPTION"
            ),
            location="OLD_DISTRICT",
            confidence=0.95,
            minute=120,
        )
    )

    revisions = list_belief_revisions(
        AGENT_ID,
        SITUATION_ID,
    )

    revision = revisions[-1]

    assert revision.revision_type == "CLAIM_CHANGED"

    assert (
        revision.previous_claim[
            "location"
        ]
        == "STATION"
    )

    assert (
        revision.new_claim[
            "location"
        ]
        == "OLD_DISTRICT"
    )

    assert (
        revision.new_source
        == "DIRECT_SITUATION_PERCEPTION"
    )

    assert (
        "DIRECT_SITUATION_PERCEPTION"
        in revision.supporting_sources
    )

    assert "REPORT_B" in revision.supporting_sources
    assert "REPORT_A" in revision.opposing_sources

# ======================================================
# 5. SOURCE CHANGE WITHOUT CLAIM CHANGE IS RECORDED
# ======================================================

def test_authoritative_source_takeover_is_recorded():

    save_situation_belief(
        belief(
            source="REPORT_A",
            location="OLD_DISTRICT",
            confidence=0.85,
        )
    )

    save_situation_belief(
        belief(
            source="PROTOCOL_NETWORK",
            location="OLD_DISTRICT",
            confidence=0.80,
            minute=120,
        )
    )

    revisions = list_belief_revisions(
        AGENT_ID,
        SITUATION_ID,
    )

    revision = revisions[-1]

    assert revision.revision_type == "SOURCE_CHANGED"
    assert revision.previous_source == "REPORT_A"
    assert revision.new_source == "PROTOCOL_NETWORK"
    assert revision.previous_claim == revision.new_claim

# ======================================================
# 6. PROVENANCE IS CHRONOLOGICAL
# ======================================================

def test_reasoning_history_is_persistent_and_ordered():

    save_situation_belief(
        belief(
            "REPORT_A",
            "STATION",
            0.80,
            minute=100,
        )
    )

    save_situation_belief(
        belief(
            "REPORT_B",
            "OLD_DISTRICT",
            0.75,
            minute=110,
        )
    )

    save_situation_belief(
        belief(
            "DIRECT_SITUATION_PERCEPTION",
            "OLD_DISTRICT",
            0.95,
            minute=120,
        )
    )

    revisions = list_belief_revisions(
        AGENT_ID,
        SITUATION_ID,
    )

    assert [
        revision.minute
        for revision in revisions
    ] == [
        100,
        110,
        120,
    ]

    assert [
        revision.revision_type
        for revision in revisions
    ] == [
        "INITIALIZED",
        "CONFIDENCE_SHIFT",
        "CLAIM_CHANGED",
    ]

    assert all(
        revision.reason
        for revision in revisions
    )
