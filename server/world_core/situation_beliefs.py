from .database import get_connection

from .models import SituationBelief


def initialize_situation_beliefs():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS situation_beliefs (
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

        conn.commit()


def save_situation_belief(
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
            (agent_id,),
        ).fetchall()

    return [
        SituationBelief(
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
        for row in rows
    ]


def decay_situation_beliefs(
    agent_id: str,
    current_minute: int,
):

    """
    Si una creencia no recibe información
    nueva, poco a poco pierde confianza.

    De momento usamos un decay sencillo
    y determinista.
    """

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
            (agent_id,),
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