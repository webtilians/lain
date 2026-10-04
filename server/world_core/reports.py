from dataclasses import dataclass

from .database import (
    get_connection,
)

from .models import (
    Agent,
    SituationBelief,
)

from .situation_beliefs import (
    save_situation_belief,
)

from .source_trust import (
    get_source_trust,
    record_source_confirmation,
    record_source_contradiction,
)


AUTHORITATIVE_SITUATION_SOURCES = {
    "DIRECT_SITUATION_PERCEPTION",
    "PROTOCOL_NETWORK",
    "WIRED_NETWORK",
}


@dataclass
class InformationReport:

    id: str

    situation_id: str

    claimed_type: str
    claimed_location: str
    claimed_subject_id: str | None
    claimed_status: str

    claimed_severity: float
    confidence: float

    source: str

    target_actor_id: str | None
    target_faction: str | None

    created_minute: int
    deliver_minute: int


def clamp(
    value: float,
) -> float:

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def initialize_reports():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            information_reports (

                id TEXT PRIMARY KEY,
                situation_id TEXT NOT NULL,

                claimed_type TEXT NOT NULL,
                claimed_location TEXT NOT NULL,
                claimed_subject_id TEXT,
                claimed_status TEXT NOT NULL,

                claimed_severity REAL NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,

                target_actor_id TEXT,
                target_faction TEXT,

                created_minute INTEGER NOT NULL,
                deliver_minute INTEGER NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            information_report_deliveries (

                report_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                delivered_minute INTEGER NOT NULL,

                accepted INTEGER NOT NULL DEFAULT 0,
                evaluated INTEGER NOT NULL DEFAULT 0,

                PRIMARY KEY (report_id, agent_id)
            )
            """
        )

        columns = {
            row[1]
            for row in conn.execute(
                """
                PRAGMA table_info(
                    information_report_deliveries
                )
                """
            ).fetchall()
        }

        if "accepted" not in columns:

            conn.execute(
                """
                ALTER TABLE information_report_deliveries
                ADD COLUMN accepted INTEGER
                NOT NULL DEFAULT 0
                """
            )

        if "evaluated" not in columns:

            conn.execute(
                """
                ALTER TABLE information_report_deliveries
                ADD COLUMN evaluated INTEGER
                NOT NULL DEFAULT 0
                """
            )

        conn.commit()


def create_information_report(
    report: InformationReport,
):

    initialize_reports()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT INTO information_reports (
                id, situation_id,
                claimed_type, claimed_location,
                claimed_subject_id, claimed_status,
                claimed_severity, confidence, source,
                target_actor_id, target_faction,
                created_minute, deliver_minute
            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                report.id,
                report.situation_id,
                report.claimed_type,
                report.claimed_location,
                report.claimed_subject_id,
                report.claimed_status,
                report.claimed_severity,
                report.confidence,
                report.source,
                report.target_actor_id,
                report.target_faction,
                report.created_minute,
                report.deliver_minute,
            ),
        )

        conn.commit()


def row_to_report(
    row,
) -> InformationReport:

    return InformationReport(
        id=row[0],
        situation_id=row[1],
        claimed_type=row[2],
        claimed_location=row[3],
        claimed_subject_id=row[4],
        claimed_status=row[5],
        claimed_severity=row[6],
        confidence=row[7],
        source=row[8],
        target_actor_id=row[9],
        target_faction=row[10],
        created_minute=row[11],
        deliver_minute=row[12],
    )


def list_deliverable_reports(
    agent: Agent,
    current_minute: int,
) -> list[InformationReport]:

    initialize_reports()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                r.id, r.situation_id,
                r.claimed_type, r.claimed_location,
                r.claimed_subject_id, r.claimed_status,
                r.claimed_severity, r.confidence, r.source,
                r.target_actor_id, r.target_faction,
                r.created_minute, r.deliver_minute

            FROM information_reports r

            LEFT JOIN information_report_deliveries d
              ON d.report_id = r.id
             AND d.agent_id = ?

            WHERE d.report_id IS NULL
              AND r.deliver_minute <= ?
              AND (
                    r.target_actor_id IS NULL
                    OR r.target_actor_id = ?
              )
              AND (
                    r.target_faction IS NULL
                    OR r.target_faction = ?
              )

            ORDER BY r.deliver_minute, r.id
            """,
            (
                agent.id,
                current_minute,
                agent.id,
                agent.faction,
            ),
        ).fetchall()

    return [
        row_to_report(row)
        for row in rows
    ]


def mark_report_delivered(
    report_id: str,
    agent_id: str,
    minute: int,
    accepted: bool,
):

    initialize_reports()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT OR IGNORE INTO information_report_deliveries (
                report_id, agent_id, delivered_minute,
                accepted, evaluated
            )
            VALUES (?, ?, ?, ?, 0)
            """,
            (
                report_id,
                agent_id,
                minute,
                int(accepted),
            ),
        )

        conn.commit()


def list_unevaluated_accepted_reports(
    agent_id: str,
    situation_id: str,
) -> list[InformationReport]:

    initialize_reports()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                r.id, r.situation_id,
                r.claimed_type, r.claimed_location,
                r.claimed_subject_id, r.claimed_status,
                r.claimed_severity, r.confidence, r.source,
                r.target_actor_id, r.target_faction,
                r.created_minute, r.deliver_minute

            FROM information_reports r
            JOIN information_report_deliveries d
              ON d.report_id = r.id

            WHERE d.agent_id = ?
              AND r.situation_id = ?
              AND d.accepted = 1
              AND d.evaluated = 0

            ORDER BY d.delivered_minute, r.id
            """,
            (
                agent_id,
                situation_id,
            ),
        ).fetchall()

    return [
        row_to_report(row)
        for row in rows
    ]


def mark_report_evaluated(
    report_id: str,
    agent_id: str,
):

    initialize_reports()

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE information_report_deliveries
            SET evaluated = 1
            WHERE report_id = ?
              AND agent_id = ?
            """,
            (
                report_id,
                agent_id,
            ),
        )

        conn.commit()


def stable_claims_match(
    report: InformationReport,
    belief: SituationBelief,
) -> bool:

    if report.claimed_type != belief.believed_type:
        return False

    if report.claimed_location != belief.believed_location:
        return False

    if (
        report.claimed_subject_id is not None
        and report.claimed_subject_id
        != belief.believed_subject_id
    ):
        return False

    return True


def evaluate_accepted_reports_against_belief(
    agent: Agent,
    belief: SituationBelief,
    current_minute: int,
):

    if belief.source not in AUTHORITATIVE_SITUATION_SOURCES:
        return []

    reports = list_unevaluated_accepted_reports(
        agent_id=agent.id,
        situation_id=belief.situation_id,
    )

    outcomes = []

    for report in reports:

        confirmed = stable_claims_match(
            report=report,
            belief=belief,
        )

        if confirmed:

            record_source_confirmation(
                agent_id=agent.id,
                source=report.source,
                minute=current_minute,
            )

            outcome = "CONFIRMED"

        else:

            record_source_contradiction(
                agent_id=agent.id,
                source=report.source,
                minute=current_minute,
            )

            outcome = "CONTRADICTED"

        mark_report_evaluated(
            report_id=report.id,
            agent_id=agent.id,
        )

        outcomes.append(
            (
                report.id,
                outcome,
            )
        )

    return outcomes


def process_information_reports(
    agent: Agent,
    current_minute: int,
) -> list[InformationReport]:

    reports = list_deliverable_reports(
        agent=agent,
        current_minute=current_minute,
    )

    accepted = []

    for report in reports:

        trust = get_source_trust(
            agent_id=agent.id,
            source=report.source,
        )

        effective_confidence = clamp(
            report.confidence * trust
        )

        # Delivery and epistemic dominance are now
        # separate concepts.
        #
        # Every delivered report becomes a hypothesis.
        # The competition layer decides whether it
        # influences the working belief.

        belief = SituationBelief(
            agent_id=agent.id,
            situation_id=report.situation_id,
            believed_type=report.claimed_type,
            believed_location=report.claimed_location,
            believed_subject_id=report.claimed_subject_id,
            believed_status=report.claimed_status,
            believed_severity=report.claimed_severity,
            confidence=effective_confidence,
            source=report.source,
            updated_minute=current_minute,
        )

        save_situation_belief(belief)
        accepted.append(report)

        mark_report_delivered(
            report_id=report.id,
            agent_id=agent.id,
            minute=current_minute,
            accepted=True,
        )

    return accepted
