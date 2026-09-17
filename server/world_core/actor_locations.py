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


def load_actor_location_belief(
    observer_id: str,
    subject_actor_id: str,
) -> ActorLocationBelief | None:

    initialize_actor_locations()

    with get_connection() as conn:

        row = conn.execute(
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
              AND subject_actor_id = ?
            """,
            (
                observer_id,
                subject_actor_id,
            ),
        ).fetchone()

    if row is None:
        return None

    return ActorLocationBelief(
        observer_id=row[0],
        subject_actor_id=row[1],

        believed_location=row[2],

        confidence=row[3],

        source=row[4],

        source_event_id=row[5],

        updated_minute=row[6],
    )


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


# ======================================================
# BELIEF AGING
# ======================================================

def decay_actor_location_beliefs(
    observer_id: str,
    current_minute: int,
):

    """
    updated_minute means:
        when the evidence about this location
        was actually produced.

    We deliberately DO NOT update it while
    confidence decays.

    Therefore we always know how old the
    underlying information really is.
    """

    initialize_actor_locations()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                subject_actor_id,
                source,
                updated_minute

            FROM actor_location_beliefs

            WHERE observer_id = ?
            """,
            (observer_id,),
        ).fetchall()

        for row in rows:

            subject_actor_id = row[0]
            source = row[1]
            evidence_minute = row[2]

            age = max(
                0,
                current_minute
                - evidence_minute,
            )

            if (
                source
                == "DIRECT_ACTOR_PERCEPTION"
            ):

                base_confidence = 0.99

            elif (
                source
                == "PROTOCOL_ACTIVITY_LOG"
            ):

                base_confidence = 0.95

            else:

                base_confidence = 0.80

            confidence = max(
                0.20,

                base_confidence
                - (age / 800.0),
            )

            conn.execute(
                """
                UPDATE actor_location_beliefs

                SET confidence = ?

                WHERE observer_id = ?
                  AND subject_actor_id = ?
                """,
                (
                    confidence,
                    observer_id,
                    subject_actor_id,
                ),
            )

        conn.commit()


# ======================================================
# DIRECT PHYSICAL PERCEPTION
# ======================================================

def perceive_colocated_actors(
    observer: Agent,
    current_minute: int,
):

    """
    World Core may use objective positions
    to decide what is physically perceptible.

    The agent receives only the resulting
    perception.
    """

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                location

            FROM agents

            WHERE location = ?
              AND id != ?
            """,
            (
                observer.location,
                observer.id,
            ),
        ).fetchall()

    for row in rows:

        subject_actor_id = row[0]
        location = row[1]

        belief = ActorLocationBelief(
            observer_id=observer.id,

            subject_actor_id=(
                subject_actor_id
            ),

            believed_location=location,

            confidence=0.99,

            source=(
                "DIRECT_ACTOR_PERCEPTION"
            ),

            source_event_id=-1,

            updated_minute=(
                current_minute
            ),
        )

        save_actor_location_belief(
            belief
        )


# ======================================================
# PROTOCOL HISTORICAL INTELLIGENCE
# ======================================================

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


def build_historical_location_belief(
    observer: Agent,
    subject_actor_id: str,
    current_minute: int,
) -> ActorLocationBelief | None:

    movement = find_latest_actor_movement(
        actor_id=subject_actor_id,
        current_minute=current_minute,
    )

    if movement is None:
        return None

    source_event_id = movement[0]
    event_minute = movement[1]
    location = movement[2]

    age = max(
        0,
        current_minute
        - event_minute,
    )

    confidence = max(
        0.20,

        0.95
        - (age / 800.0),
    )

    return ActorLocationBelief(
        observer_id=observer.id,

        subject_actor_id=(
            subject_actor_id
        ),

        believed_location=location,

        confidence=clamp(
            confidence
        ),

        source=(
            "PROTOCOL_ACTIVITY_LOG"
        ),

        source_event_id=(
            source_event_id
        ),

        # Important:
        # this is the time of the movement,
        # not the time Protocol queried it.
        updated_minute=(
            event_minute
        ),
    )


def historical_information_is_newer(
    historical: ActorLocationBelief,
    existing: ActorLocationBelief | None,
) -> bool:

    if existing is None:
        return True

    return (
        historical.updated_minute
        > existing.updated_minute
    )


# ======================================================
# COMPLETE ACTOR PERCEPTION / INTELLIGENCE PHASE
# ======================================================

def update_actor_location_intelligence(
    observer: Agent,
    actor_beliefs: list[ActorBelief],
    current_minute: int,
):

    # ----------------------------------------------
    # 1. OLD INFORMATION AGES
    # ----------------------------------------------

    decay_actor_location_beliefs(
        observer_id=observer.id,
        current_minute=current_minute,
    )

    # ----------------------------------------------
    # 2. DIRECT PHYSICAL PERCEPTION
    # ----------------------------------------------

    perceive_colocated_actors(
        observer=observer,
        current_minute=current_minute,
    )

    # ----------------------------------------------
    # 3. SPECIAL PROTOCOL INTELLIGENCE
    # ----------------------------------------------

    if observer.faction != "PROTOCOL":
        return

    for actor_belief in actor_beliefs:

        if (
            actor_belief.belief_type
            != "LIKELY_UNAUTHORIZED_MANIPULATOR"
        ):
            continue

        if (
            actor_belief.confidence
            < 0.65
        ):
            continue

        subject_actor_id = (
            actor_belief.subject_actor_id
        )

        existing = (
            load_actor_location_belief(
                observer_id=observer.id,
                subject_actor_id=(
                    subject_actor_id
                ),
            )
        )

        historical = (
            build_historical_location_belief(
                observer=observer,

                subject_actor_id=(
                    subject_actor_id
                ),

                current_minute=(
                    current_minute
                ),
            )
        )

        if historical is None:
            continue

        # Never replace a more recent direct
        # sighting with an older system log.

        if not historical_information_is_newer(
            historical=historical,
            existing=existing,
        ):
            continue

        save_actor_location_belief(
            historical
        )
