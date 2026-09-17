from dataclasses import dataclass

from .database import get_connection


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
              AND status = 'OPEN'

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

        return (
            existing,
            False,
        )

    interaction = Interaction(
        id=(
            f"CONTACT_"
            f"{initiator_id}_"
            f"{recipient_id}_"
            f"{minute}"
        ),

        interaction_type=(
            "CONTACT"
        ),

        initiator_id=(
            initiator_id
        ),

        recipient_id=(
            recipient_id
        ),

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


def list_open_interactions() -> list[Interaction]:

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