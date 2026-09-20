from dataclasses import dataclass

from .database import get_connection


VALID_RESPONSES = {
    "ADMIT",
    "DENY",
    "SILENCE",
    "ACCUSE",
}


@dataclass
class Interaction:
    id: str
    interaction_type: str

    initiator_id: str
    recipient_id: str

    topic: str
    status: str

    source_goal: str

    created_minute: int
    updated_minute: int


@dataclass
class InteractionResponse:
    id: int

    interaction_id: str

    actor_id: str
    response_type: str

    subject_actor_id: str | None

    processed: bool


def initialize_interactions():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,

                interaction_type TEXT NOT NULL,

                initiator_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,

                topic TEXT NOT NULL,

                status TEXT NOT NULL,

                source_goal TEXT NOT NULL,

                created_minute INTEGER NOT NULL,
                updated_minute INTEGER NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interaction_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                interaction_id TEXT NOT NULL,

                actor_id TEXT NOT NULL,
                response_type TEXT NOT NULL,

                subject_actor_id TEXT,

                processed INTEGER NOT NULL DEFAULT 0,

                processed_minute INTEGER
            )
            """
        )

        conn.commit()


def row_to_interaction(
    row,
) -> Interaction:

    return Interaction(
        id=row[0],
        interaction_type=row[1],

        initiator_id=row[2],
        recipient_id=row[3],

        topic=row[4],
        status=row[5],

        source_goal=row[6],

        created_minute=row[7],
        updated_minute=row[8],
    )


def get_interaction(
    interaction_id: str,
) -> Interaction | None:

    initialize_interactions()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                interaction_type,

                initiator_id,
                recipient_id,

                topic,
                status,

                source_goal,

                created_minute,
                updated_minute

            FROM interactions

            WHERE id = ?
            """,
            (interaction_id,),
        ).fetchone()

    if row is None:
        return None

    return row_to_interaction(
        row
    )


def find_open_interaction(
    initiator_id: str,
    recipient_id: str,
    topic: str,
) -> Interaction | None:

    initialize_interactions()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                interaction_type,

                initiator_id,
                recipient_id,

                topic,
                status,

                source_goal,

                created_minute,
                updated_minute

            FROM interactions

            WHERE initiator_id = ?
              AND recipient_id = ?
              AND topic = ?
              AND status IN ('OPEN', 'PAUSED', 'RESUMING')

            ORDER BY created_minute DESC

            LIMIT 1
            """,
            (
                initiator_id,
                recipient_id,
                topic,
            ),
        ).fetchone()

    if row is None:
        return None

    return row_to_interaction(
        row
    )


def find_latest_open_for_recipient(
    recipient_id: str,
) -> Interaction | None:

    initialize_interactions()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                interaction_type,

                initiator_id,
                recipient_id,

                topic,
                status,

                source_goal,

                created_minute,
                updated_minute

            FROM interactions

            WHERE recipient_id = ?
              AND status = 'OPEN'

            ORDER BY created_minute DESC

            LIMIT 1
            """,
            (recipient_id,),
        ).fetchone()

    if row is None:
        return None

    return row_to_interaction(
        row
    )


def find_latest_open_for_initiator(
    initiator_id: str,
) -> Interaction | None:

    initialize_interactions()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                interaction_type,

                initiator_id,
                recipient_id,

                topic,
                status,

                source_goal,

                created_minute,
                updated_minute

            FROM interactions

            WHERE initiator_id = ?
              AND status = 'OPEN'

            ORDER BY
                created_minute DESC,
                id DESC

            LIMIT 1
            """,
            (initiator_id,),
        ).fetchone()

    if row is None:
        return None

    return row_to_interaction(
        row
    )


def create_or_get_interaction(
    initiator_id: str,
    recipient_id: str,

    topic: str,

    source_goal: str,

    minute: int,
) -> tuple[Interaction, bool]:

    existing = find_open_interaction(
        initiator_id=initiator_id,
        recipient_id=recipient_id,
        topic=topic,
    )

    if existing is not None:
        if existing.status == "PAUSED":
            # CONTACT is accepted, but the new greeting has not been
            # delivered yet. START must append it once before returning
            # the conversation to OPEN. Repeated CONTACT remains idempotent.
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE interactions
                    SET status = 'RESUMING', updated_minute = ?
                    WHERE id = ? AND status = 'PAUSED'
                    """,
                    (minute, existing.id),
                )
                conn.commit()
            existing = get_interaction(existing.id)
        return existing, False

    interaction = Interaction(
        id=(
            f"CONTACT_"
            f"{initiator_id}_"
            f"{recipient_id}_"
            f"{minute}"
        ),

        interaction_type="CONTACT",

        initiator_id=initiator_id,
        recipient_id=recipient_id,

        topic=topic,

        status="OPEN",

        source_goal=source_goal,

        created_minute=minute,
        updated_minute=minute,
    )

    initialize_interactions()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT INTO interactions (
                id,
                interaction_type,

                initiator_id,
                recipient_id,

                topic,
                status,

                source_goal,

                created_minute,
                updated_minute
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interaction.id,
                interaction.interaction_type,

                interaction.initiator_id,
                interaction.recipient_id,

                interaction.topic,
                interaction.status,

                interaction.source_goal,

                interaction.created_minute,
                interaction.updated_minute,
            ),
        )

        conn.commit()

    return (
        interaction,
        True,
    )


def actor_exists(
    actor_id: str,
) -> bool:

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT 1

            FROM agents

            WHERE id = ?
            """,
            (actor_id,),
        ).fetchone()

    return row is not None


def queue_interaction_response(
    interaction_id: str,

    actor_id: str,

    response_type: str,

    subject_actor_id: str | None = None,
) -> int:

    initialize_interactions()

    interaction = get_interaction(
        interaction_id
    )

    if interaction is None:

        raise ValueError(
            "Unknown interaction"
        )

    if interaction.status != "OPEN":

        raise ValueError(
            "Interaction is not open"
        )

    if interaction.recipient_id != actor_id:

        raise ValueError(
            "Actor is not the recipient"
        )

    response_type = (
        response_type.upper()
    )

    if response_type not in VALID_RESPONSES:

        raise ValueError(
            f"Unknown response: "
            f"{response_type}"
        )

    if response_type == "ACCUSE":

        if not subject_actor_id:

            raise ValueError(
                "ACCUSE requires an actor"
            )

        if not actor_exists(
            subject_actor_id
        ):

            raise ValueError(
                f"Unknown actor: "
                f"{subject_actor_id}"
            )

        if subject_actor_id == actor_id:

            raise ValueError(
                "Cannot accuse yourself"
            )

    with get_connection() as conn:

        pending = conn.execute(
            """
            SELECT id

            FROM interaction_responses

            WHERE interaction_id = ?
              AND actor_id = ?
              AND processed = 0

            LIMIT 1
            """,
            (
                interaction_id,
                actor_id,
            ),
        ).fetchone()

        if pending is not None:

            raise ValueError(
                "A response is already pending"
            )

        cursor = conn.execute(
            """
            INSERT INTO interaction_responses (
                interaction_id,

                actor_id,
                response_type,

                subject_actor_id,

                processed
            )

            VALUES (?, ?, ?, ?, 0)
            """,
            (
                interaction_id,

                actor_id,
                response_type,

                subject_actor_id,
            ),
        )

        conn.commit()

        return cursor.lastrowid


def load_pending_interaction_responses(
) -> list[InteractionResponse]:

    initialize_interactions()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                id,

                interaction_id,

                actor_id,
                response_type,

                subject_actor_id,

                processed

            FROM interaction_responses

            WHERE processed = 0

            ORDER BY id
            """
        ).fetchall()

    return [
        InteractionResponse(
            id=row[0],

            interaction_id=row[1],

            actor_id=row[2],
            response_type=row[3],

            subject_actor_id=row[4],

            processed=bool(row[5]),
        )
        for row in rows
    ]


def mark_response_processed(
    response_id: int,
    minute: int,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE interaction_responses

            SET
                processed = 1,
                processed_minute = ?

            WHERE id = ?
            """,
            (
                minute,
                response_id,
            ),
        )

        conn.commit()


def close_interaction(
    interaction_id: str,
    status: str,
    minute: int,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE interactions

            SET
                status = ?,
                updated_minute = ?

            WHERE id = ?
            """,
            (
                status,
                minute,
                interaction_id,
            ),
        )

        conn.commit()


def list_open_interactions(
) -> list[Interaction]:

    initialize_interactions()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                interaction_type,

                initiator_id,
                recipient_id,

                topic,
                status,

                source_goal,

                created_minute,
                updated_minute

            FROM interactions

            WHERE status = 'OPEN'

            ORDER BY created_minute
            """
        ).fetchall()

    return [
        row_to_interaction(row)
        for row in rows
    ]