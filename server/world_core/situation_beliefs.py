from .database import (
    get_connection,
)

from .belief_provenance import (
    record_belief_revision,
)

from .models import (
    SituationBelief,
)


# ======================================================
# EPISTEMIC AUTHORITY
# ======================================================

DIRECT_AUTHORITY = 3
NETWORK_AUTHORITY = 2
REPORT_AUTHORITY = 1


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


def source_authority(
    source: str,
) -> int:

    if (
        source
        == "DIRECT_SITUATION_PERCEPTION"
    ):
        return DIRECT_AUTHORITY

    if source.endswith(
        "_NETWORK"
    ):
        return NETWORK_AUTHORITY

    return REPORT_AUTHORITY


# ======================================================
# TABLES
# ======================================================


def initialize_situation_beliefs():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            situation_beliefs (

                agent_id TEXT NOT NULL,
                situation_id TEXT NOT NULL,

                believed_type TEXT NOT NULL,
                believed_location TEXT NOT NULL,
                believed_subject_id TEXT,
                believed_status TEXT NOT NULL,

                believed_severity REAL NOT NULL,
                confidence REAL NOT NULL,

                source TEXT NOT NULL,
                updated_minute INTEGER NOT NULL,

                PRIMARY KEY (
                    agent_id,
                    situation_id
                )
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            situation_hypotheses (

                agent_id TEXT NOT NULL,
                situation_id TEXT NOT NULL,
                source TEXT NOT NULL,

                believed_type TEXT NOT NULL,
                believed_location TEXT NOT NULL,
                believed_subject_id TEXT,
                believed_status TEXT NOT NULL,

                believed_severity REAL NOT NULL,
                confidence REAL NOT NULL,
                updated_minute INTEGER NOT NULL,

                PRIMARY KEY (
                    agent_id,
                    situation_id,
                    source
                )
            )
            """
        )

        conn.commit()


# ======================================================
# RAW HYPOTHESES
# ======================================================


def save_situation_hypothesis(
    belief: SituationBelief,
):

    initialize_situation_beliefs()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT OR REPLACE INTO
            situation_hypotheses (

                agent_id,
                situation_id,
                source,

                believed_type,
                believed_location,
                believed_subject_id,
                believed_status,

                believed_severity,
                confidence,
                updated_minute
            )

            VALUES (
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?
            )
            """,
            (
                belief.agent_id,
                belief.situation_id,
                belief.source,

                belief.believed_type,
                belief.believed_location,
                belief.believed_subject_id,
                belief.believed_status,

                belief.believed_severity,
                belief.confidence,
                belief.updated_minute,
            ),
        )

        conn.commit()


def _row_to_belief(row) -> SituationBelief:

    return SituationBelief(
        agent_id=row[0],
        situation_id=row[1],

        believed_type=row[2],
        believed_location=row[3],
        believed_subject_id=row[4],
        believed_status=row[5],

        believed_severity=row[6],
        confidence=row[7],

        source=row[8],
        updated_minute=row[9],
    )


def list_situation_hypotheses(
    agent_id: str,
    situation_id: str,
) -> list[SituationBelief]:

    initialize_situation_beliefs()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                agent_id,
                situation_id,

                believed_type,
                believed_location,
                believed_subject_id,
                believed_status,

                believed_severity,
                confidence,

                source,
                updated_minute

            FROM situation_hypotheses

            WHERE agent_id = ?
              AND situation_id = ?

            ORDER BY
                confidence DESC,
                updated_minute DESC,
                source
            """,
            (
                agent_id,
                situation_id,
            ),
        ).fetchall()

    return [
        _row_to_belief(row)
        for row in rows
    ]


# ======================================================
# CLAIM GROUPS
# ======================================================


def claim_signature(
    belief: SituationBelief,
):

    return (
        belief.believed_type,
        belief.believed_location,
        belief.believed_subject_id,
        belief.believed_status,
    )


def group_support(
    hypotheses: list[SituationBelief],
) -> float:

    if not hypotheses:
        return 0.0

    strongest = max(
        hypothesis.confidence
        for hypothesis in hypotheses
    )

    agreement_bonus = (
        0.05
        * (
            len(hypotheses) - 1
        )
    )

    return clamp(
        strongest
        + agreement_bonus
    )


# ======================================================
# PROJECT COMPETING HYPOTHESES INTO ONE WORKING BELIEF
# ======================================================


def build_dominant_belief(
    agent_id: str,
    situation_id: str,
) -> SituationBelief | None:

    hypotheses = list_situation_hypotheses(
        agent_id=agent_id,
        situation_id=situation_id,
    )

    if not hypotheses:
        return None

    highest_authority = max(
        source_authority(
            hypothesis.source
        )
        for hypothesis in hypotheses
    )

    eligible = [
        hypothesis
        for hypothesis in hypotheses
        if source_authority(
            hypothesis.source
        ) == highest_authority
    ]

    groups = {}

    for hypothesis in eligible:

        signature = claim_signature(
            hypothesis
        )

        groups.setdefault(
            signature,
            [],
        ).append(
            hypothesis
        )

    ranked_groups = []

    for signature, members in groups.items():

        support = group_support(
            members
        )

        representative = max(
            members,
            key=lambda item: (
                item.confidence,
                item.updated_minute,
                item.source,
            ),
        )

        ranked_groups.append(
            (
                support,
                representative.updated_minute,
                signature,
                representative,
                members,
            )
        )

    ranked_groups.sort(
        reverse=True,
        key=lambda item: (
            item[0],
            item[1],
            str(item[2]),
        ),
    )

    winner = ranked_groups[0]
    winner_support = winner[0]
    representative = winner[3]

    if len(ranked_groups) == 1:

        working_confidence = winner_support

    else:

        runner_up_support = ranked_groups[1][0]

        working_confidence = max(
            0.05,
            winner_support - runner_up_support,
        )

    return SituationBelief(
        agent_id=representative.agent_id,
        situation_id=representative.situation_id,

        believed_type=representative.believed_type,
        believed_location=representative.believed_location,
        believed_subject_id=representative.believed_subject_id,
        believed_status=representative.believed_status,

        believed_severity=representative.believed_severity,
        confidence=clamp(
            working_confidence
        ),

        source=representative.source,
        updated_minute=max(
            member.updated_minute
            for member in winner[4]
        ),
    )


# ======================================================
# WORKING BELIEF
# ======================================================


def write_working_belief(
    belief: SituationBelief,
):

    initialize_situation_beliefs()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT OR REPLACE INTO
            situation_beliefs (

                agent_id,
                situation_id,

                believed_type,
                believed_location,
                believed_subject_id,
                believed_status,

                believed_severity,
                confidence,

                source,
                updated_minute
            )

            VALUES (
                ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?
            )
            """,
            (
                belief.agent_id,
                belief.situation_id,

                belief.believed_type,
                belief.believed_location,
                belief.believed_subject_id,
                belief.believed_status,

                belief.believed_severity,
                belief.confidence,

                belief.source,
                belief.updated_minute,
            ),
        )

        conn.commit()


def save_situation_belief(
    belief: SituationBelief,
):

    # ==================================================
    # STATE BEFORE NEW INFORMATION
    # ==================================================

    previous = load_situation_belief(
        agent_id=belief.agent_id,
        situation_id=belief.situation_id,
    )

    # ==================================================
    # PRESERVE INCOMING INFORMATION AS HYPOTHESIS
    # ==================================================

    save_situation_hypothesis(
        belief
    )

    dominant = build_dominant_belief(
        agent_id=belief.agent_id,
        situation_id=belief.situation_id,
    )

    if dominant is None:
        return

    hypotheses = list_situation_hypotheses(
        agent_id=belief.agent_id,
        situation_id=belief.situation_id,
    )

    # ==================================================
    # AUDIT COGNITIVE REVISION
    # ==================================================

    record_belief_revision(
        previous=previous,
        new=dominant,
        hypotheses=hypotheses,
        minute=belief.updated_minute,
    )

    # ==================================================
    # COMMIT WORKING BELIEF
    # ==================================================

    write_working_belief(
        dominant
    )


def load_situation_belief(
    agent_id: str,
    situation_id: str,
) -> SituationBelief | None:

    initialize_situation_beliefs()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                agent_id,
                situation_id,

                believed_type,
                believed_location,
                believed_subject_id,
                believed_status,

                believed_severity,
                confidence,

                source,
                updated_minute

            FROM situation_beliefs

            WHERE agent_id = ?
              AND situation_id = ?
            """,
            (
                agent_id,
                situation_id,
            ),
        ).fetchone()

    if row is None:
        return None

    return _row_to_belief(row)


def list_agent_situation_beliefs(
    agent_id: str,
) -> list[SituationBelief]:

    initialize_situation_beliefs()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                agent_id,
                situation_id,

                believed_type,
                believed_location,
                believed_subject_id,
                believed_status,

                believed_severity,
                confidence,

                source,
                updated_minute

            FROM situation_beliefs

            WHERE agent_id = ?

            ORDER BY
                confidence DESC,
                believed_severity DESC
            """,
            (
                agent_id,
            ),
        ).fetchall()

    return [
        _row_to_belief(row)
        for row in rows
    ]


# ======================================================
# AGING
# ======================================================


def decay_situation_beliefs(
    agent_id: str,
    current_minute: int,
):

    initialize_situation_beliefs()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                situation_id,
                confidence,
                updated_minute

            FROM situation_beliefs

            WHERE agent_id = ?
            """,
            (
                agent_id,
            ),
        ).fetchall()

        for row in rows:

            situation_id = row[0]
            confidence = row[1]
            updated_minute = row[2]

            if updated_minute >= current_minute:
                continue

            new_confidence = max(
                0.05,
                confidence - 0.05,
            )

            conn.execute(
                """
                UPDATE situation_beliefs

                SET confidence = ?

                WHERE agent_id = ?
                  AND situation_id = ?
                """,
                (
                    new_confidence,
                    agent_id,
                    situation_id,
                ),
            )

        conn.commit()
