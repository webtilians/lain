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
                energy REAL NOT NULL
            )
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

        existing = conn.execute(
            "SELECT id FROM world_state WHERE id = 1"
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO world_state
                (id, signal, stability, connection)
                VALUES (1, 0.10, 0.90, 0.35)
                """
            )

        existing_sim = conn.execute(
            "SELECT id FROM simulation_state WHERE id = 1"
        ).fetchone()

        if existing_sim is None:
            conn.execute(
                """
                INSERT INTO simulation_state (id, minute)
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

    return WorldState(*row)


def save_world_state(state: WorldState):
    state.clamp()

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE world_state
            SET signal = ?,
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
            SELECT id, name, faction, location, goal, energy
            FROM agents
            WHERE id = ?
            """,
            (default.id,),
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO agents
                (id, name, faction, location, goal, energy)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    default.id,
                    default.name,
                    default.faction,
                    default.location,
                    default.goal,
                    default.energy,
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

        agent.memory = [row[0] for row in memories]

    return agent


def save_agent(agent: Agent):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE agents
            SET location = ?,
                goal = ?,
                energy = ?
            WHERE id = ?
            """,
            (
                agent.location,
                agent.goal,
                agent.energy,
                agent.id,
            ),
        )
        conn.commit()


def add_memory(agent_id: str, memory: str):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_memory (agent_id, memory)
            VALUES (?, ?)
            """,
            (agent_id, memory),
        )
        conn.commit()


def load_or_create_node(default: WorldNode) -> WorldNode:
    initialize_database()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, location, node_type,
                   discovered, active, anomaly_strength
            FROM nodes
            WHERE id = ?
            """,
            (default.id,),
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO nodes
                (id, location, node_type,
                 discovered, active, anomaly_strength)
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
            SET discovered = ?,
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


def save_simulation_minute(minute: int):
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
):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO events
            (minute, actor_id, action, target, details)
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
        conn.commit()