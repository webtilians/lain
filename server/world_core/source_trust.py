from dataclasses import dataclass

from .database import (
    get_connection,
)


DEFAULT_SOURCE_TRUST = 1.00

MIN_SOURCE_TRUST = 0.10
MAX_SOURCE_TRUST = 1.00

CONTRADICTION_PENALTY = 0.25
CONFIRMATION_REWARD = 0.05


@dataclass
class SourceTrust:

    agent_id: str
    source: str

    trust: float

    confirmations: int
    contradictions: int

    updated_minute: int


def clamp(
    value: float,
) -> float:

    return max(
        MIN_SOURCE_TRUST,
        min(
            MAX_SOURCE_TRUST,
            value,
        ),
    )


def initialize_source_trust():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            source_trust (

                agent_id TEXT NOT NULL,
                source TEXT NOT NULL,

                trust REAL NOT NULL,

                confirmations INTEGER
                    NOT NULL DEFAULT 0,

                contradictions INTEGER
                    NOT NULL DEFAULT 0,

                updated_minute INTEGER
                    NOT NULL,

                PRIMARY KEY (
                    agent_id,
                    source
                )
            )
            """
        )

        conn.commit()


def load_source_trust(
    agent_id: str,
    source: str,
) -> SourceTrust:

    initialize_source_trust()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                agent_id,
                source,

                trust,

                confirmations,
                contradictions,

                updated_minute

            FROM source_trust

            WHERE agent_id = ?
              AND source = ?
            """,
            (
                agent_id,
                source,
            ),
        ).fetchone()

    if row is None:

        return SourceTrust(
            agent_id=agent_id,
            source=source,

            trust=DEFAULT_SOURCE_TRUST,

            confirmations=0,
            contradictions=0,

            updated_minute=0,
        )

    return SourceTrust(
        agent_id=row[0],
        source=row[1],

        trust=row[2],

        confirmations=row[3],
        contradictions=row[4],

        updated_minute=row[5],
    )


def get_source_trust(
    agent_id: str,
    source: str,
) -> float:

    return load_source_trust(
        agent_id=agent_id,
        source=source,
    ).trust


def save_source_trust(
    state: SourceTrust,
):

    initialize_source_trust()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT OR REPLACE INTO
            source_trust (

                agent_id,
                source,

                trust,

                confirmations,
                contradictions,

                updated_minute
            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                state.agent_id,
                state.source,

                clamp(
                    state.trust
                ),

                state.confirmations,
                state.contradictions,

                state.updated_minute,
            ),
        )

        conn.commit()


def record_source_contradiction(
    agent_id: str,
    source: str,
    minute: int,
) -> SourceTrust:

    state = load_source_trust(
        agent_id=agent_id,
        source=source,
    )

    state.trust = clamp(
        state.trust
        - CONTRADICTION_PENALTY
    )

    state.contradictions += 1

    state.updated_minute = (
        minute
    )

    save_source_trust(
        state
    )

    return state


def record_source_confirmation(
    agent_id: str,
    source: str,
    minute: int,
) -> SourceTrust:

    state = load_source_trust(
        agent_id=agent_id,
        source=source,
    )

    state.trust = clamp(
        state.trust
        + CONFIRMATION_REWARD
    )

    state.confirmations += 1

    state.updated_minute = (
        minute
    )

    save_source_trust(
        state
    )

    return state
