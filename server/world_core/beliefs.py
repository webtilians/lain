from .database import get_connection
from .models import NodeBelief


def initialize_beliefs():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS node_beliefs (
                agent_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                believed_location TEXT NOT NULL,
                believed_strength REAL NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,
                updated_minute INTEGER NOT NULL,

                PRIMARY KEY (
                    agent_id,
                    node_id
                )
            )
            """
        )

        conn.commit()


def save_belief(
    belief: NodeBelief,
):
    initialize_beliefs()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO node_beliefs (
                agent_id,
                node_id,
                believed_location,
                believed_strength,
                confidence,
                source,
                updated_minute
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                belief.agent_id,
                belief.node_id,
                belief.believed_location,
                belief.believed_strength,
                belief.confidence,
                belief.source,
                belief.updated_minute,
            ),
        )

        conn.commit()


def load_belief(
    agent_id: str,
    node_id: str,
) -> NodeBelief | None:

    initialize_beliefs()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                agent_id,
                node_id,
                believed_location,
                believed_strength,
                confidence,
                source,
                updated_minute
            FROM node_beliefs
            WHERE agent_id = ?
              AND node_id = ?
            """,
            (
                agent_id,
                node_id,
            ),
        ).fetchone()

    if row is None:
        return None

    return NodeBelief(
        agent_id=row[0],
        node_id=row[1],
        believed_location=row[2],
        believed_strength=row[3],
        confidence=row[4],
        source=row[5],
        updated_minute=row[6],
    )