from dataclasses import dataclass

from .database import (
    get_connection,
    record_event,
)


INITIAL_MESSAGE_ID = "MSG_BOOTSTRAP_001"


@dataclass
class WorldMessage:
    id: str

    recipient_id: str

    sender_id: str | None
    sender_label: str

    subject: str
    body: str

    created_minute: int
    visible_from_minute: int

    read: bool
    acknowledged: bool

    acknowledged_minute: int | None


def initialize_messages():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            world_messages (

                id TEXT PRIMARY KEY,

                recipient_id TEXT NOT NULL,

                sender_id TEXT,
                sender_label TEXT NOT NULL,

                subject TEXT NOT NULL,
                body TEXT NOT NULL,

                created_minute INTEGER NOT NULL,
                visible_from_minute INTEGER NOT NULL,

                read INTEGER NOT NULL DEFAULT 0,
                acknowledged INTEGER NOT NULL DEFAULT 0,

                acknowledged_minute INTEGER
            )
            """
        )

        conn.commit()


def ensure_initial_player_message():

    initialize_messages()

    with get_connection() as conn:

        conn.execute(
            """
            INSERT OR IGNORE INTO world_messages (
                id,
                recipient_id,
                sender_id,
                sender_label,
                subject,
                body,
                created_minute,
                visible_from_minute,
                read,
                acknowledged
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                INITIAL_MESSAGE_ID,
                "PLAYER_1",
                None,
                "unknown@wired",
                "NO SUBJECT",
                (
                    "NO ESTOY MUERTA.\n\n"
                    "SOLO DEJÉ DE ESTAR AHÍ."
                ),
                0,
                0,
            ),
        )

        conn.commit()


def _row_to_message(row) -> WorldMessage:

    return WorldMessage(
        id=row[0],
        recipient_id=row[1],
        sender_id=row[2],
        sender_label=row[3],
        subject=row[4],
        body=row[5],
        created_minute=row[6],
        visible_from_minute=row[7],
        read=bool(row[8]),
        acknowledged=bool(row[9]),
        acknowledged_minute=row[10],
    )


def list_player_messages(
    player_id: str,
    current_minute: int,
) -> list[WorldMessage]:

    initialize_messages()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                recipient_id,
                sender_id,
                sender_label,
                subject,
                body,
                created_minute,
                visible_from_minute,
                read,
                acknowledged,
                acknowledged_minute

            FROM world_messages

            WHERE recipient_id = ?
              AND visible_from_minute <= ?

            ORDER BY created_minute DESC, id DESC
            """,
            (
                player_id,
                current_minute,
            ),
        ).fetchall()

    return [
        _row_to_message(row)
        for row in rows
    ]


def acknowledge_message(
    message_id: str,
    player_id: str,
    minute: int,
) -> bool:

    initialize_messages()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT acknowledged

            FROM world_messages

            WHERE id = ?
              AND recipient_id = ?
            """,
            (
                message_id,
                player_id,
            ),
        ).fetchone()

        if row is None:
            raise ValueError(
                "Unknown player message"
            )

        if bool(row[0]):
            return False

        conn.execute(
            """
            UPDATE world_messages

            SET
                read = 1,
                acknowledged = 1,
                acknowledged_minute = ?

            WHERE id = ?
              AND recipient_id = ?
            """,
            (
                minute,
                message_id,
                player_id,
            ),
        )

        conn.commit()

    record_event(
        minute=minute,
        actor_id=player_id,
        action="MESSAGE_ACKNOWLEDGED",
        target=message_id,
        details="Player accepted message connection",
    )

    return True
