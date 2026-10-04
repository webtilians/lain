import pytest

from server.world_core.models import (
    Agent,
)

from server.world_core.reports import (
    InformationReport,
    create_information_report,
    process_information_reports,
)

from server.world_core.situation_beliefs import (
    list_situation_hypotheses,
    load_situation_belief,
)


SITUATION_ID = (
    "SIGNAL_SURGE_NODE_12"
)


def make_k():

    return Agent(
        id="AGENT_K",
        name="K",

        faction="PROTOCOL",

        location=(
            "APARTMENT_DISTRICT"
        ),

        goal="IDLE",
    )


def report(
    report_id: str,
    source: str,
    location: str,
    confidence: float,
):

    return InformationReport(
        id=report_id,

        situation_id=(
            SITUATION_ID
        ),

        claimed_type=(
            "SIGNAL_SURGE"
        ),

        claimed_location=(
            location
        ),

        claimed_subject_id=(
            "NODE_12"
        ),

        claimed_status="OPEN",

        claimed_severity=0.80,

        confidence=confidence,

        source=source,

        target_actor_id=(
            "AGENT_K"
        ),

        target_faction=None,

        created_minute=0,
        deliver_minute=10,
    )

# ======================================================
# 1. TWO CONFLICTING REPORTS BOTH ENTER COGNITION
# ======================================================

def test_conflicting_reports_both_become_hypotheses():

    k = make_k()

    create_information_report(
        report(
            report_id="REPORT_A",
            source="SOURCE_A",
            location="STATION",
            confidence=0.80,
        )
    )

    create_information_report(
        report(
            report_id="REPORT_B",
            source="SOURCE_B",
            location="OLD_DISTRICT",
            confidence=0.75,
        )
    )

    delivered = process_information_reports(
        agent=k,
        current_minute=10,
    )

    assert len(delivered) == 2

    hypotheses = list_situation_hypotheses(
        agent_id=k.id,
        situation_id=SITUATION_ID,
    )

    assert len(hypotheses) == 2

    assert {
        belief.believed_location
        for belief in hypotheses
    } == {
        "STATION",
        "OLD_DISTRICT",
    }

# ======================================================
# 2. PIPELINE PRODUCES REAL UNCERTAINTY
# ======================================================

def test_conflicting_reports_reduce_working_confidence():

    k = make_k()

    create_information_report(
        report(
            "REPORT_A",
            "SOURCE_A",
            "STATION",
            0.80,
        )
    )

    create_information_report(
        report(
            "REPORT_B",
            "SOURCE_B",
            "OLD_DISTRICT",
            0.75,
        )
    )

    process_information_reports(
        agent=k,
        current_minute=10,
    )

    belief = load_situation_belief(
        k.id,
        SITUATION_ID,
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "STATION"
    )

    assert (
        belief.confidence
        == pytest.approx(
            0.05
        )
    )

# ======================================================
# 3. AGREEMENT THROUGH REPORT PIPELINE REINFORCES
# ======================================================

def test_agreeing_reports_reinforce_working_belief():

    k = make_k()

    create_information_report(
        report(
            "REPORT_A",
            "SOURCE_A",
            "OLD_DISTRICT",
            0.80,
        )
    )

    create_information_report(
        report(
            "REPORT_B",
            "SOURCE_B",
            "OLD_DISTRICT",
            0.75,
        )
    )

    process_information_reports(
        agent=k,
        current_minute=10,
    )

    belief = load_situation_belief(
        k.id,
        SITUATION_ID,
    )

    assert belief is not None

    assert (
        belief.believed_location
        == "OLD_DISTRICT"
    )

    assert (
        belief.confidence
        == pytest.approx(
            0.85
        )
    )

# ======================================================
# 4. LOW-TRUST REPORT SURVIVES BUT WEIGHS LESS
# ======================================================

def test_low_trust_report_is_preserved_not_erased():

    from server.world_core.source_trust import (
        record_source_contradiction,
    )

    k = make_k()

    record_source_contradiction(
        agent_id=k.id,
        source="SOURCE_B",
        minute=1,
    )

    record_source_contradiction(
        agent_id=k.id,
        source="SOURCE_B",
        minute=2,
    )

    create_information_report(
        report(
            "REPORT_A",
            "SOURCE_A",
            "STATION",
            0.80,
        )
    )

    create_information_report(
        report(
            "REPORT_B",
            "SOURCE_B",
            "OLD_DISTRICT",
            0.80,
        )
    )

    process_information_reports(
        agent=k,
        current_minute=10,
    )

    hypotheses = list_situation_hypotheses(
        k.id,
        SITUATION_ID,
    )

    assert len(hypotheses) == 2

    by_source = {
        belief.source: belief
        for belief in hypotheses
    }

    assert (
        by_source[
            "SOURCE_A"
        ].confidence
        == pytest.approx(
            0.80
        )
    )

    assert (
        by_source[
            "SOURCE_B"
        ].confidence
        == pytest.approx(
            0.40
        )
    )

    dominant = load_situation_belief(
        k.id,
        SITUATION_ID,
    )

    assert dominant is not None

    assert (
        dominant.believed_location
        == "STATION"
    )

    assert (
        dominant.confidence
        == pytest.approx(
            0.40
        )
    )
