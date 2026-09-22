import sqlite3
from pathlib import Path

from .models import Agent, WorldNode, WorldState


DB_PATH = Path("world.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS world_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                signal REAL NOT NULL,
                stability REAL NOT NULL,
                connection REAL NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                faction TEXT NOT NULL,
                location TEXT NOT NULL,
                goal TEXT NOT NULL,
                energy REAL NOT NULL,
                controller_type TEXT NOT NULL DEFAULT 'AI'
            )
            """
        )

        # Migración para bases creadas en versiones anteriores.
        agent_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(agents)"
            ).fetchall()
        }

        if "controller_type" not in agent_columns:
            conn.execute(
                """
                ALTER TABLE agents
                ADD COLUMN controller_type TEXT
                NOT NULL DEFAULT 'AI'
                """
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                memory TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                location TEXT NOT NULL,
                node_type TEXT NOT NULL,
                discovered INTEGER NOT NULL,
                active INTEGER NOT NULL,
                anomaly_strength REAL NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                minute INTEGER NOT NULL,
                actor_id TEXT,
                action TEXT NOT NULL,
                target TEXT,
                details TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS simulation_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                minute INTEGER NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                actor_id TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                source TEXT NOT NULL,
                processed INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        existing_world = conn.execute(
            "SELECT id FROM world_state WHERE id = 1"
        ).fetchone()

        if existing_world is None:
            conn.execute(
                """
                INSERT INTO world_state (
                    id,
                    signal,
                    stability,
                    connection
                )
                VALUES (1, 0.10, 0.90, 0.35)
                """
            )

        existing_simulation = conn.execute(
            "SELECT id FROM simulation_state WHERE id = 1"
        ).fetchone()

        if existing_simulation is None:
            conn.execute(
                """
                INSERT INTO simulation_state (
                    id,
                    minute
                )
                VALUES (1, 0)
                """
            )

        conn.commit()


def load_world_state() -> WorldState:
    initialize_database()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT signal, stability, connection
            FROM world_state
            WHERE id = 1
            """
        ).fetchone()

    return WorldState(
        signal=row[0],
        stability=row[1],
        connection=row[2],
    )


def save_world_state(state: WorldState):
    state.clamp()

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE world_state
            SET
                signal = ?,
                stability = ?,
                connection = ?
            WHERE id = 1
            """,
            (
                state.signal,
                state.stability,
                state.connection,
            ),
        )

        conn.commit()


def load_or_create_agent(default: Agent) -> Agent:
    initialize_database()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                name,
                faction,
                location,
                goal,
                energy,
                controller_type
            FROM agents
            WHERE id = ?
            """,
            (default.id,),
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO agents (
                    id,
                    name,
                    faction,
                    location,
                    goal,
                    energy,
                    controller_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    default.id,
                    default.name,
                    default.faction,
                    default.location,
                    default.goal,
                    default.energy,
                    default.controller_type,
                ),
            )

            conn.commit()

            agent = default

        else:
            agent = Agent(
                id=row[0],
                name=row[1],
                faction=row[2],
                location=row[3],
                goal=row[4],
                energy=row[5],
                controller_type=row[6],
            )

        memories = conn.execute(
            """
            SELECT memory
            FROM agent_memory
            WHERE agent_id = ?
            ORDER BY id
            """,
            (default.id,),
        ).fetchall()

        agent.memory = [
            memory_row[0]
            for memory_row in memories
        ]

    return agent


def save_agent(agent: Agent):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE agents
            SET
                location = ?,
                goal = ?,
                energy = ?,
                controller_type = ?
            WHERE id = ?
            """,
            (
                agent.location,
                agent.goal,
                agent.energy,
                agent.controller_type,
                agent.id,
            ),
        )

        conn.commit()


def add_memory(
    agent_id: str,
    memory: str,
):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_memory (
                agent_id,
                memory
            )
            VALUES (?, ?)
            """,
            (
                agent_id,
                memory,
            ),
        )

        conn.commit()


def load_or_create_node(
    default: WorldNode,
) -> WorldNode:

    initialize_database()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                location,
                node_type,
                discovered,
                active,
                anomaly_strength
            FROM nodes
            WHERE id = ?
            """,
            (default.id,),
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO nodes (
                    id,
                    location,
                    node_type,
                    discovered,
                    active,
                    anomaly_strength
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    default.id,
                    default.location,
                    default.node_type,
                    int(default.discovered),
                    int(default.active),
                    default.anomaly_strength,
                ),
            )

            conn.commit()

            return default

    return WorldNode(
        id=row[0],
        location=row[1],
        node_type=row[2],
        discovered=bool(row[3]),
        active=bool(row[4]),
        anomaly_strength=row[5],
    )


def save_node(node: WorldNode):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE nodes
            SET
                discovered = ?,
                active = ?,
                anomaly_strength = ?
            WHERE id = ?
            """,
            (
                int(node.discovered),
                int(node.active),
                node.anomaly_strength,
                node.id,
            ),
        )

        conn.commit()


def load_simulation_minute() -> int:
    initialize_database()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT minute
            FROM simulation_state
            WHERE id = 1
            """
        ).fetchone()

    return row[0]


def save_simulation_minute(
    minute: int,
):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE simulation_state
            SET minute = ?
            WHERE id = 1
            """,
            (minute,),
        )

        conn.commit()


def record_event(
    minute: int,
    actor_id: str,
    action: str,
    target: str,
    details: str = "",
    location: str | None = None,
):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO events (
                minute,
                actor_id,
                action,
                target,
                details
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                minute,
                actor_id,
                action,
                target,
                details,
            ),
        )

        if location is not None:
            from .shared_experiences import record_action_experience
            record_action_experience(conn, cursor.lastrowid, actor_id, action,
                                     target, minute, location)
        conn.commit()
        return cursor.lastrowid


def list_nodes() -> list[WorldNode]:

    initialize_database()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                location,
                node_type,
                discovered,
                active,
                anomaly_strength

            FROM nodes

            ORDER BY id
            """
        ).fetchall()

    return [
        WorldNode(
            id=row[0],
            location=row[1],
            node_type=row[2],
            discovered=bool(row[3]),
            active=bool(row[4]),
            anomaly_strength=row[5],
        )
        for row in rows
    ]


def load_node(
    node_id: str,
) -> WorldNode | None:

    initialize_database()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                location,
                node_type,
                discovered,
                active,
                anomaly_strength

            FROM nodes

            WHERE id = ?
            """,
            (node_id,),
        ).fetchone()

    if row is None:
        return None

    return WorldNode(
        id=row[0],
        location=row[1],
        node_type=row[2],
        discovered=bool(row[3]),
        active=bool(row[4]),
        anomaly_strength=row[5],
    )