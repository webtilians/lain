from dataclasses import dataclass

from server.world_core.database import (
    get_connection,
    record_event,
)

from server.world_core.models import (
    WorldNode,
    WorldState,
)


@dataclass
class Situation:
    id: str
    situation_type: str

    location: str
    subject_id: str

    status: str
    severity: float

    created_minute: int
    updated_minute: int

    reason: str


def clamp(value: float) -> float:
    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def initialize_situations():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS situations (
                id TEXT PRIMARY KEY,

                situation_type TEXT NOT NULL,

                location TEXT NOT NULL,
                subject_id TEXT NOT NULL,

                status TEXT NOT NULL,
                severity REAL NOT NULL,

                created_minute INTEGER NOT NULL,
                updated_minute INTEGER NOT NULL,

                reason TEXT NOT NULL
            )
            """
        )

        conn.commit()


def row_to_situation(row) -> Situation:

    return Situation(
        id=row[0],
        situation_type=row[1],

        location=row[2],
        subject_id=row[3],

        status=row[4],
        severity=row[5],

        created_minute=row[6],
        updated_minute=row[7],

        reason=row[8],
    )


def load_situation(
    situation_id: str,
) -> Situation | None:

    initialize_situations()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                situation_type,
                location,
                subject_id,
                status,
                severity,
                created_minute,
                updated_minute,
                reason

            FROM situations

            WHERE id = ?
            """,
            (situation_id,),
        ).fetchone()

    if row is None:
        return None

    return row_to_situation(row)


def list_situations() -> list[Situation]:

    initialize_situations()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                situation_type,
                location,
                subject_id,
                status,
                severity,
                created_minute,
                updated_minute,
                reason

            FROM situations

            ORDER BY created_minute
            """
        ).fetchall()

    return [
        row_to_situation(row)
        for row in rows
    ]


def list_open_situations() -> list[Situation]:

    return [
        situation
        for situation in list_situations()
        if situation.status == "OPEN"
    ]


def save_situation(
    situation: Situation,
):

    initialize_situations()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT OR REPLACE INTO situations (
                id,
                situation_type,
                location,
                subject_id,
                status,
                severity,
                created_minute,
                updated_minute,
                reason
            )

            VALUES (
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?
            )
            """,
            (
                situation.id,
                situation.situation_type,

                situation.location,
                situation.subject_id,

                situation.status,
                situation.severity,

                situation.created_minute,
                situation.updated_minute,

                situation.reason,
            ),
        )

        conn.commit()


# ======================================================
# SIGNAL SURGE
# ======================================================

def evaluate_signal_surge(
    world: WorldState,
    node: WorldNode,
    minute: int,
):

    situation_id = (
        f"SIGNAL_SURGE_{node.id}"
    )

    existing = load_situation(
        situation_id
    )

    should_exist = (
        world.signal >= 0.50
        or
        node.anomaly_strength >= 0.45
    )

    should_resolve = (
        world.signal <= 0.35
        and
        node.anomaly_strength <= 0.25
    )

    severity = max(
        world.signal,
        node.anomaly_strength,
    )

    if should_exist:

        reason = (
            f"Signal={world.signal:.2f}, "
            f"anomaly={node.anomaly_strength:.2f}"
        )

        if existing is None:

            situation = Situation(
                id=situation_id,

                situation_type=(
                    "SIGNAL_SURGE"
                ),

                location=node.location,
                subject_id=node.id,

                status="OPEN",
                severity=severity,

                created_minute=minute,
                updated_minute=minute,

                reason=reason,
            )

            save_situation(situation)

            record_event(
                minute=minute,
                actor_id="WORLD_CORE",
                action="CREATE_SITUATION",
                target=situation_id,
                details=reason,
            )

            print()
            print(
                "*** SITUATION CREATED: "
                f"{situation_id} ***"
            )

            return

        was_closed = (
            existing.status != "OPEN"
        )

        existing.status = "OPEN"
        existing.severity = severity
        existing.updated_minute = minute
        existing.reason = reason

        save_situation(existing)

        if was_closed:

            record_event(
                minute=minute,
                actor_id="WORLD_CORE",
                action="REOPEN_SITUATION",
                target=situation_id,
                details=reason,
            )

            print()
            print(
                "*** SITUATION REOPENED: "
                f"{situation_id} ***"
            )

        return

    if (
        existing is not None
        and existing.status == "OPEN"
        and should_resolve
    ):

        existing.status = "RESOLVED"
        existing.updated_minute = minute

        existing.reason = (
            f"Signal stabilized at "
            f"{world.signal:.2f}; "
            f"anomaly at "
            f"{node.anomaly_strength:.2f}"
        )

        save_situation(existing)

        record_event(
            minute=minute,
            actor_id="WORLD_CORE",
            action="RESOLVE_SITUATION",
            target=situation_id,
            details=existing.reason,
        )

        print()
        print(
            "*** SITUATION RESOLVED: "
            f"{situation_id} ***"
        )


# ======================================================
# UNAUTHORIZED SIGNAL MANIPULATION
# ======================================================

def find_recent_player_manipulation(
    node_id: str,
    minute: int,
    window_minutes: int = 120,
):

    minimum_minute = (
        minute - window_minutes
    )

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                minute,
                actor_id,
                action,
                target,
                details

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
                minute,
            ),
        ).fetchone()

    return row


def evaluate_unauthorized_manipulation(
    world: WorldState,
    node: WorldNode,
    minute: int,
):

    situation_id = (
        f"UNAUTHORIZED_MANIPULATION_"
        f"{node.id}"
    )

    existing = load_situation(
        situation_id
    )

    event = (
        find_recent_player_manipulation(
            node_id=node.id,
            minute=minute,
            window_minutes=120,
        )
    )

    # --------------------------------------------
    # No recent manipulation
    # --------------------------------------------

    if event is None:

        if (
            existing is not None
            and existing.status == "OPEN"
        ):

            existing.status = "RESOLVED"
            existing.updated_minute = minute

            existing.reason = (
                "No recent unauthorized "
                "signal manipulation detected"
            )

            save_situation(existing)

            record_event(
                minute=minute,
                actor_id="WORLD_CORE",
                action="RESOLVE_SITUATION",
                target=situation_id,
                details=existing.reason,
            )

            print()
            print(
                "*** SITUATION RESOLVED: "
                f"{situation_id} ***"
            )

        return

    event_minute = event[0]
    actor_id = event[1]
    action = event[2]

    # La gravedad depende parcialmente
    # del estado actual del Signal.

    severity = clamp(
        max(
            0.60,
            world.signal + 0.15,
        )
    )

    reason = (
        f"{actor_id} performed "
        f"{action} on {node.id} "
        f"at minute {event_minute}"
    )

    # --------------------------------------------
    # New situation
    # --------------------------------------------

    if existing is None:

        situation = Situation(
            id=situation_id,

            situation_type=(
                "UNAUTHORIZED_SIGNAL_MANIPULATION"
            ),

            location=node.location,

            # El objeto investigable sigue
            # siendo el nodo.
            subject_id=node.id,

            status="OPEN",

            severity=severity,

            created_minute=minute,
            updated_minute=minute,

            reason=reason,
        )

        save_situation(
            situation
        )

        record_event(
            minute=minute,
            actor_id="WORLD_CORE",
            action="CREATE_SITUATION",
            target=situation_id,
            details=reason,
        )

        print()
        print(
            "*** SITUATION CREATED: "
            f"{situation_id} ***"
        )

        return

    # --------------------------------------------
    # Existing situation
    # --------------------------------------------

    was_closed = (
        existing.status != "OPEN"
    )

    existing.status = "OPEN"
    existing.severity = severity
    existing.updated_minute = minute
    existing.reason = reason

    save_situation(
        existing
    )

    if was_closed:

        record_event(
            minute=minute,
            actor_id="WORLD_CORE",
            action="REOPEN_SITUATION",
            target=situation_id,
            details=reason,
        )

        print()
        print(
            "*** SITUATION REOPENED: "
            f"{situation_id} ***"
        )


# ======================================================
# WORLD EVALUATION
# ======================================================

def evaluate_node(
    world: WorldState,
    node: WorldNode,
    minute: int,
):

    if not node.active:
        return

    evaluate_signal_surge(
        world=world,
        node=node,
        minute=minute,
    )

    evaluate_unauthorized_manipulation(
        world=world,
        node=node,
        minute=minute,
    )


def evaluate_nodes(
    world: WorldState,
    nodes: list[WorldNode],
    minute: int,
):

    for node in nodes:

        evaluate_node(
            world=world,
            node=node,
            minute=minute,
        )


def evaluate_world(
    world: WorldState,
    node: WorldNode,
    minute: int,
):

    """
    Backwards-compatible adapter for
    World Core 0.9.

    World Core 1.0 will gradually migrate
    callers to evaluate_nodes().
    """

    evaluate_node(
        world=world,
        node=node,
        minute=minute,
    )