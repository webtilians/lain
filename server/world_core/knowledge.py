from .database import get_connection


def initialize_knowledge():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_knowledge (
                agent_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,

                PRIMARY KEY (
                    agent_id,
                    node_id
                )
            )
            """
        )

        conn.commit()


def knows_node(
    agent_id: str,
    node_id: str,
) -> bool:

    initialize_knowledge()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM agent_knowledge
            WHERE agent_id = ?
              AND node_id = ?
            """,
            (
                agent_id,
                node_id,
            ),
        ).fetchone()

    return row is not None


def learn_node(
    agent_id: str,
    node_id: str,
    confidence: float = 1.0,
    source: str = "DIRECT_OBSERVATION",
):
    initialize_knowledge()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO agent_knowledge (
                agent_id,
                node_id,
                confidence,
                source
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                agent_id,
                node_id,
                confidence,
                source,
            ),
        )

        conn.commit()