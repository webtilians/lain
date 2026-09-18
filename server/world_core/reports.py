from dataclasses import dataclass

from .database import (
    get_connection,
)

from .models import (
    Agent,
    SituationBelief,
)

from .situation_beliefs import (
    load_situation_belief,
    save_situation_belief,
)


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

                PRIMARY KEY (
                    report_id,
                    agent_id
                )
            )
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
                id,
                situation_id,

                claimed_type,
                claimed_location,
                claimed_subject_id,
                claimed_status,

                claimed_severity,
                confidence,

                source,

                target_actor_id,
                target_faction,

                created_minute,
                deliver_minute
            )

            VALUES (
                ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?,
                ?, ?,
                ?, ?
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
                r.id,
                r.situation_id,

                r.claimed_type,
                r.claimed_location,
                r.claimed_subject_id,
                r.claimed_status,

                r.claimed_severity,
                r.confidence,

                r.source,

                r.target_actor_id,
                r.target_faction,

                r.created_minute,
                r.deliver_minute

            FROM information_reports r

            LEFT JOIN information_report_deliveries d

              ON d.report_id = r.id
             AND d.agent_id = ?

            WHERE d.report_id IS NULL

              AND r.deliver_minute <= ?

              AND (
                    r.target_actor_id IS NULL
                    OR
                    r.target_actor_id = ?
              )

              AND (
                    r.target_faction IS NULL
                    OR
                    r.target_faction = ?
              )

            ORDER BY
                r.deliver_minute,
                r.id
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
):

    initialize_reports()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT OR IGNORE INTO
            information_report_deliveries (
                report_id,
                agent_id,
                delivered_minute
            )

            VALUES (?, ?, ?)
            """,
            (
                report_id,
                agent_id,
                minute,
            ),
        )

        conn.commit()


def report_can_replace_belief(
    report: InformationReport,
    existing: SituationBelief | None,
) -> bool:

    if existing is None:
        return True

    # A direct physical observation made after
    # the report was created is stronger than
    # the report.

    if (
        existing.source
        == "DIRECT_SITUATION_PERCEPTION"

        and

        existing.updated_minute
        >= report.created_minute
    ):
        return False

    # More recent, equally or more confident
    # information should not be downgraded.

    if (
        existing.updated_minute
        > report.created_minute

        and

        existing.confidence
        >= report.confidence
    ):
        return False

    return True


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

        existing = load_situation_belief(
            agent_id=agent.id,
            situation_id=report.situation_id,
        )

        if report_can_replace_belief(
            report=report,
            existing=existing,
        ):

            belief = SituationBelief(
                agent_id=agent.id,

                situation_id=(
                    report.situation_id
                ),

                believed_type=(
                    report.claimed_type
                ),

                believed_location=(
                    report.claimed_location
                ),

                believed_subject_id=(
                    report.claimed_subject_id
                ),

                believed_status=(
                    report.claimed_status
                ),

                believed_severity=(
                    report.claimed_severity
                ),

                confidence=(
                    report.confidence
                ),

                source=(
                    report.source
                ),

                updated_minute=(
                    current_minute
                ),
            )

            save_situation_belief(
                belief
            )

            accepted.append(
                report
            )

        # Delivery is consumed even when rejected.
        #
        # Otherwise the same message would attempt
        # to overwrite knowledge forever.

        mark_report_delivered(
            report_id=report.id,
            agent_id=agent.id,
            minute=current_minute,
        )

    return accepted
