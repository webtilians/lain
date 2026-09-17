from .database import get_connection

from .models import (
    ActorBelief,
    Evidence,
)


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


def initialize_evidence():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,

                evidence_type TEXT NOT NULL,

                discoverer_id TEXT NOT NULL,
                subject_actor_id TEXT NOT NULL,

                target_id TEXT NOT NULL,

                strength REAL NOT NULL,

                source_event_id INTEGER NOT NULL,

                discovered_minute INTEGER NOT NULL,

                details TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS actor_beliefs (
                observer_id TEXT NOT NULL,

                subject_actor_id TEXT NOT NULL,

                belief_type TEXT NOT NULL,

                confidence REAL NOT NULL,

                source_evidence_id TEXT NOT NULL,

                updated_minute INTEGER NOT NULL,

                PRIMARY KEY (
                    observer_id,
                    subject_actor_id,
                    belief_type
                )
            )
            """
        )

        conn.commit()


def save_evidence(
    evidence: Evidence,
):

    initialize_evidence()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT OR IGNORE INTO evidence (
                id,

                evidence_type,

                discoverer_id,
                subject_actor_id,

                target_id,

                strength,

                source_event_id,

                discovered_minute,

                details
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.id,

                evidence.evidence_type,

                evidence.discoverer_id,
                evidence.subject_actor_id,

                evidence.target_id,

                evidence.strength,

                evidence.source_event_id,

                evidence.discovered_minute,

                evidence.details,
            ),
        )

        conn.commit()


def save_actor_belief(
    belief: ActorBelief,
):

    initialize_evidence()

    with get_connection() as conn:

        existing = conn.execute(
            """
            SELECT confidence

            FROM actor_beliefs

            WHERE observer_id = ?
              AND subject_actor_id = ?
              AND belief_type = ?
            """,
            (
                belief.observer_id,
                belief.subject_actor_id,
                belief.belief_type,
            ),
        ).fetchone()

        confidence = belief.confidence

        if existing is not None:
            confidence = max(
                existing[0],
                confidence,
            )

        conn.execute(
            """
            INSERT OR REPLACE INTO actor_beliefs (
                observer_id,

                subject_actor_id,

                belief_type,

                confidence,

                source_evidence_id,

                updated_minute
            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                belief.observer_id,

                belief.subject_actor_id,

                belief.belief_type,

                confidence,

                belief.source_evidence_id,

                belief.updated_minute,
            ),
        )

        conn.commit()


def list_actor_beliefs(
    observer_id: str,
) -> list[ActorBelief]:

    initialize_evidence()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                observer_id,

                subject_actor_id,

                belief_type,

                confidence,

                source_evidence_id,

                updated_minute

            FROM actor_beliefs

            WHERE observer_id = ?

            ORDER BY confidence DESC
            """,
            (observer_id,),
        ).fetchall()

    return [
        ActorBelief(
            observer_id=row[0],

            subject_actor_id=row[1],

            belief_type=row[2],

            confidence=row[3],

            source_evidence_id=row[4],

            updated_minute=row[5],
        )
        for row in rows
    ]


def find_recent_player_manipulation(
    node_id: str,
    current_minute: int,
    window_minutes: int = 180,
):

    minimum_minute = (
        current_minute - window_minutes
    )

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                minute,
                actor_id,
                action,
                target

            FROM events

            WHERE actor_id LIKE 'PLAYER_%'

              AND target = ?

              AND action IN (
                  'AMPLIFY',
                  'STABILIZE'
              )

              AND minute >= ?
              AND minute <= ?

            ORDER BY
                minute DESC,
                id DESC

            LIMIT 1
            """,
            (
                node_id,
                minimum_minute,
                current_minute,
            ),
        ).fetchone()

    return row


def discover_unauthorized_manipulation_evidence(
    discoverer_id: str,
    node_id: str,
    current_minute: int,
) -> Evidence | None:

    event = (
        find_recent_player_manipulation(
            node_id=node_id,
            current_minute=current_minute,
        )
    )

    if event is None:
        return None

    source_event_id = event[0]
    event_minute = event[1]
    subject_actor_id = event[2]
    action = event[3]

    age = max(
        0,
        current_minute - event_minute,
    )

    # Cuanto más antiguo sea el rastro,
    # menos fiable resulta.
    #
    # No damos nunca certeza absoluta.

    strength = clamp(
        0.95 - (age / 600.0)
    )

    strength = max(
        0.35,
        strength,
    )

    evidence_id = (
        f"TRACE_{source_event_id}_"
        f"{discoverer_id}"
    )

    evidence = Evidence(
        id=evidence_id,

        evidence_type=(
            "SIGNAL_ACCESS_TRACE"
        ),

        discoverer_id=discoverer_id,

        subject_actor_id=(
            subject_actor_id
        ),

        target_id=node_id,

        strength=strength,

        source_event_id=(
            source_event_id
        ),

        discovered_minute=(
            current_minute
        ),

        details=(
            f"Recovered trace linking "
            f"{subject_actor_id} to "
            f"{action} on {node_id}"
        ),
    )

    save_evidence(
        evidence
    )

    belief = ActorBelief(
        observer_id=discoverer_id,

        subject_actor_id=(
            subject_actor_id
        ),

        belief_type=(
            "LIKELY_UNAUTHORIZED_MANIPULATOR"
        ),

        confidence=strength,

        source_evidence_id=(
            evidence.id
        ),

        updated_minute=(
            current_minute
        ),
    )

    save_actor_belief(
        belief
    )

    return evidence