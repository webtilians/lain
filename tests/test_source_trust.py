import pytest

from server.world_core.models import (
    Agent,
    SituationBelief,
)

from server.world_core.reports import (
    InformationReport,
    create_information_report,
    evaluate_accepted_reports_against_belief,
    process_information_reports,
)

from server.world_core.situation_beliefs import (
    load_situation_belief,
)

from server.world_core.source_trust import (
    get_source_trust,
    load_source_trust,
    record_source_contradiction,
)


SOURCE = (
    "COMPROMISED_PROTOCOL_RELAY"
)


def create_k():

    return Agent(
        id="AGENT_K",
        name="K",

        faction="PROTOCOL",

        location=(
            "APARTMENT_DISTRICT"
        ),

        goal="IDLE",
    )


def create_report(
    report_id: str,

    source: str = SOURCE,

    location: str = "STATION",

    confidence: float = 0.90,
):

    return InformationReport(
        id=report_id,

        situation_id=(
            "SIGNAL_SURGE_NODE_12"
        ),

        claimed_type="SIGNAL_SURGE",

        claimed_location=(
            location
        ),

        claimed_subject_id=(
            "NODE_12"
        ),

        claimed_status="OPEN",

        claimed_severity=0.90,

        confidence=confidence,

        source=source,

        target_actor_id=(
            "AGENT_K"
        ),

        target_faction=None,

        created_minute=0,
        deliver_minute=10,
    )


def authoritative_belief(
    location="OLD_DISTRICT",
):

    return SituationBelief(
        agent_id="AGENT_K",

        situation_id=(
            "SIGNAL_SURGE_NODE_12"
        ),

        believed_type="SIGNAL_SURGE",

        believed_location=(
            location
        ),

        believed_subject_id=(
            "NODE_12"
        ),

        believed_status="OPEN",

        believed_severity=0.80,
        confidence=0.80,

        source="PROTOCOL_NETWORK",

        updated_minute=30,
    )

# ======================================================
# 1. UNKNOWN SOURCE STARTS FULLY UNPENALIZED
# ======================================================

def test_new_source_starts_with_default_trust():

    trust = get_source_trust(
        agent_id="AGENT_K",
        source=SOURCE,
    )

    assert trust == pytest.approx(
        1.00
    )

# ======================================================
# 2. CONTRADICTION LOWERS TRUST
# ======================================================

def test_false_report_lowers_source_trust():

    k = create_k()

    create_information_report(
        create_report(
            "FALSE_1"
        )
    )

    accepted = (
        process_information_reports(
            agent=k,
            current_minute=10,
        )
    )

    assert len(accepted) == 1

    outcomes = (
        evaluate_accepted_reports_against_belief(
            agent=k,

            belief=(
                authoritative_belief(
                    location="OLD_DISTRICT"
                )
            ),

            current_minute=30,
        )
    )

    assert outcomes == [
        (
            "FALSE_1",
            "CONTRADICTED",
        )
    ]

    state = load_source_trust(
        agent_id="AGENT_K",
        source=SOURCE,
    )

    assert state.trust == pytest.approx(
        0.75
    )

    assert (
        state.contradictions
        == 1
    )

    assert (
        state.confirmations
        == 0
    )

# ======================================================
# 3. FUTURE REPORTS ARE DISCOUNTED
# ======================================================

def test_future_report_confidence_is_scaled_by_trust():

    k = create_k()

    record_source_contradiction(
        agent_id=k.id,
        source=SOURCE,
        minute=10,
    )

    assert (
        get_source_trust(
            agent_id=k.id,
            source=SOURCE,
        )
        == pytest.approx(
            0.75
        )
    )

    report = create_report(
        "FALSE_2",
        confidence=0.90,
    )

    report.created_minute = 20
    report.deliver_minute = 20

    create_information_report(
        report
    )

    process_information_reports(
        agent=k,
        current_minute=20,
    )

    belief = load_situation_belief(
        k.id,
        "SIGNAL_SURGE_NODE_12",
    )

    assert belief is not None

    assert (
        belief.confidence
        == pytest.approx(
            0.675
        )
    )

# ======================================================
# 4. CORRECT REPORT CAN REBUILD TRUST
# ======================================================

def test_confirmed_report_slowly_rebuilds_trust():

    k = create_k()

    record_source_contradiction(
        agent_id=k.id,
        source=SOURCE,
        minute=5,
    )

    assert (
        get_source_trust(
            k.id,
            SOURCE,
        )
        == pytest.approx(
            0.75
        )
    )

    report = create_report(
        report_id="TRUE_1",
        location="OLD_DISTRICT",
    )

    create_information_report(
        report
    )

    process_information_reports(
        agent=k,
        current_minute=10,
    )

    outcomes = (
        evaluate_accepted_reports_against_belief(
            agent=k,

            belief=(
                authoritative_belief(
                    location="OLD_DISTRICT"
                )
            ),

            current_minute=30,
        )
    )

    assert outcomes == [
        (
            "TRUE_1",
            "CONFIRMED",
        )
    ]

    state = load_source_trust(
        k.id,
        SOURCE,
    )

    assert state.trust == pytest.approx(
        0.80
    )

    assert (
        state.confirmations
        == 1
    )

    assert (
        state.contradictions
        == 1
    )

# ======================================================
# 5. TRUST IS PERSONAL, NOT GLOBAL
# ======================================================

def test_agents_have_independent_trust_in_same_source():

    record_source_contradiction(
        agent_id="AGENT_K",
        source=SOURCE,
        minute=10,
    )

    k_trust = get_source_trust(
        "AGENT_K",
        SOURCE,
    )

    nora_trust = get_source_trust(
        "AGENT_NORA",
        SOURCE,
    )

    assert (
        k_trust
        == pytest.approx(
            0.75
        )
    )

    assert (
        nora_trust
        == pytest.approx(
            1.00
        )
    )
