from .database import (
    get_connection,
    initialize_database,
)

from .models import (
    ActionIntent,
)


VALID_ACTIONS = {
    "MOVE",
    "INVESTIGATE",
    "STABILIZE",
    "AMPLIFY",
    "OBSERVE",
    "OBSERVE_AREA",
    "CONTACT",
    "REST",
}


def queue_action(
    actor_id: str,
    action: str,
    target: str,
    source: str = "HUMAN",
) -> int:

    initialize_database()

    action = action.upper()

    if action not in VALID_ACTIONS:

        raise ValueError(
            f"Unknown action: {action}"
        )

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO pending_actions (
                actor_id,
                action,
                target,
                source,
                processed
            )

            VALUES (?, ?, ?, ?, 0)
            """,
            (
                actor_id,
                action,
                target,
                source,
            ),
        )

        conn.commit()

        return cursor.lastrowid


def load_pending_actions():

    initialize_database()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                actor_id,
                action,
                target,
                source

            FROM pending_actions

            WHERE processed = 0

            ORDER BY id
            """
        ).fetchall()

    result = []

    for row in rows:

        action_id = row[0]

        intent = ActionIntent(
            actor_id=row[1],
            action=row[2],
            target=row[3],
            source=row[4],
        )

        result.append(
            (
                action_id,
                intent,
            )
        )

    return result


def mark_action_processed(
    action_id: int,
):

    initialize_database()

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE pending_actions

            SET processed = 1

            WHERE id = ?
            """,
            (action_id,),
        )

        conn.commit()