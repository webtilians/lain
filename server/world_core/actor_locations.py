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


# ======================================================
# INTERNAL WORLD SENSOR
# ======================================================

def get_actor_real_location(
    actor_id: str,
) -> str | None:

    """
    IMPORTANT:

    This function belongs to the world/sensor layer.

    Agents must NEVER receive this value directly.

    It may only be used to determine whether
    direct perception is physically possible.
    """

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT location
            FROM agents
            WHERE id = ?
            """,
            (actor_id,),
        ).fetchone()

    if row is None:
        return None

    return row[0]


# ======================================================
# DIRECT ACTOR PERCEPTION
# ======================================================

def try_direct_actor_perception(
    observer: Agent,
    subject_actor_id: str,
    current_minute: int,
) -> ActorLocationBelief | None:

    """
    The world may inspect true positions only to
    determine whether two actors can perceive
    each other.

    The cognition system never sees the true
    location directly.
    """

    subject_location = (
        get_actor_real_location(
            subject_actor_id
        )
    )

    if subject_location is None:
        return None

    # They must physically share the same location.
    if (
        observer.location
        != subject_location
    ):
        return None

    belief = ActorLocationBelief(
        observer_id=observer.id,

        subject_actor_id=(
            subject_actor_id
        ),

        believed_location=(
            subject_location
        ),

        confidence=0.99,

        source=(
            "DIRECT_ACTOR_PERCEPTION"
        ),

        # There is no historical event behind
        # a direct visual perception.
        source_event_id=-1,

        updated_minute=(
            current_minute
        ),
    )

    save_actor_location_belief(
        belief
    )

    return belief


# ======================================================
# HISTORICAL INTELLIGENCE
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
        current_minute - event_minute,
    )

    # Historical information becomes less
    # trustworthy as time passes.

    confidence = clamp(
        0.95 - (age / 800.0)
    )

    confidence = max(
        0.20,
        confidence,
    )

    return ActorLocationBelief(
        observer_id=observer.id,

        subject_actor_id=(
            subject_actor_id
        ),

        believed_location=location,

        confidence=confidence,

        source=(
            "PROTOCOL_ACTIVITY_LOG"
        ),

        source_event_id=(
            source_event_id
        ),

        updated_minute=(
            current_minute
        ),
    )


# ======================================================
# INTELLIGENCE UPDATE
# ======================================================

def update_actor_location_intelligence(
    observer: Agent,
    actor_beliefs: list[ActorBelief],
    current_minute: int,
):

    """
    Protocol attempts to locate actors it considers
    relevant.

    Information hierarchy:

        DIRECT PERCEPTION
               ↓
        HISTORICAL LOG

    Direct physical perception is preferred when
    available.

    Otherwise Protocol falls back to historical
    activity data.
    """

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

        # =================================================
        # FIRST: DIRECT PHYSICAL PERCEPTION
        # =================================================

        direct = (
            try_direct_actor_perception(
                observer=observer,

                subject_actor_id=(
                    subject_actor_id
                ),

                current_minute=(
                    current_minute
                ),
            )
        )

        if direct is not None:
            continue

        # =================================================
        # OTHERWISE: HISTORICAL INTELLIGENCE
        # =================================================

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

        save_actor_location_belief(
            historical
        )