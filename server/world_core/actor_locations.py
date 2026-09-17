from .database import get_connection

from .models import (
    ActorBelief,
    ActorLocationBelief,
    Agent,
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


def initialize_actor_locations():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS actor_location_beliefs (
                observer_id TEXT NOT NULL,
                subject_actor_id TEXT NOT NULL,

                believed_location TEXT NOT NULL,

                confidence REAL NOT NULL,

                source TEXT NOT NULL,

                source_event_id INTEGER NOT NULL,

                updated_minute INTEGER NOT NULL,

                PRIMARY KEY (
                    observer_id,
                    subject_actor_id
                )
            )
            """
        )

        conn.commit()


def save_actor_location_belief(
    belief: ActorLocationBelief,
):

    initialize_actor_locations()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT OR REPLACE INTO actor_location_beliefs (
                observer_id,
                subject_actor_id,

                believed_location,

                confidence,

                source,

                source_event_id,

                updated_minute
            )

            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                belief.observer_id,
                belief.subject_actor_id,

                belief.believed_location,

                belief.confidence,

                belief.source,

                belief.source_event_id,

                belief.updated_minute,
            ),
        )

        conn.commit()


def list_actor_location_beliefs(
    observer_id: str,
) -> list[ActorLocationBelief]:

    initialize_actor_locations()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                observer_id,
                subject_actor_id,

                believed_location,

                confidence,

                source,

                source_event_id,

                updated_minute

            FROM actor_location_beliefs

            WHERE observer_id = ?

            ORDER BY confidence DESC
            """,
            (observer_id,),
        ).fetchall()

    return [
        ActorLocationBelief(
            observer_id=row[0],
            subject_actor_id=row[1],

            believed_location=row[2],

            confidence=row[3],

            source=row[4],

            source_event_id=row[5],

            updated_minute=row[6],
        )
        for row in rows
    ]


def find_latest_actor_movement(
    actor_id: str,
    current_minute: int,
):

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                minute,
                target

            FROM events

            WHERE actor_id = ?
              AND action = 'MOVE'
              AND minute <= ?

            ORDER BY
                minute DESC,
                id DESC

            LIMIT 1
            """,
            (
                actor_id,
                current_minute,
            ),
        ).fetchone()

    return row


def update_actor_location_intelligence(
    observer: Agent,
    actor_beliefs: list[ActorBelief],
    current_minute: int,
):

    """
    Protocol puede consultar actividad histórica
    de la red.

    Importante:
    esto NO proporciona la posición real actual.

    Solo recupera la última localización registrada.
    """

    if observer.faction != "PROTOCOL":
        return

    for actor_belief in actor_beliefs:

        if (
            actor_belief.belief_type
            != "LIKELY_UNAUTHORIZED_MANIPULATOR"
        ):
            continue

        if actor_belief.confidence < 0.65:
            continue

        movement = find_latest_actor_movement(
            actor_id=(
                actor_belief.subject_actor_id
            ),
            current_minute=current_minute,
        )

        if movement is None:
            continue

        source_event_id = movement[0]
        event_minute = movement[1]
        location = movement[2]

        age = max(
            0,
            current_minute - event_minute,
        )

        # La última localización conocida
        # pierde fiabilidad con el tiempo.

        confidence = clamp(
            0.95 - (age / 800.0)
        )

        confidence = max(
            0.20,
            confidence,
        )

        belief = ActorLocationBelief(
            observer_id=observer.id,

            subject_actor_id=(
                actor_belief.subject_actor_id
            ),

            believed_location=location,

            confidence=confidence,

            source="PROTOCOL_ACTIVITY_LOG",

            source_event_id=(
                source_event_id
            ),

            updated_minute=current_minute,
        )

        save_actor_location_belief(
            belief
        )
        