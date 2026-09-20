"""D8 private episodic-memory provenance, retrieval and explicit AI relay.

The existing agent_memory table remains canonical. This companion table
adds source metadata without rewriting existing saves or World Core beliefs.
"""
import re
import unicodedata

from .database import get_connection

STOPWORDS = frozenset(
    "a al algo ante con como cuando cual cuales de del donde el ella en "
    "era eran es esta estaba este esto fue ha he la las le lo los me mi "
    "mis no nos o para por que quien se ser si sobre su sus te tu tus "
    "un una uno y ya yo recuerdas recuerde recordar dime saber"
    .split()
)

CANDIDATE_LIMIT = 1000


def initialize_memory_provenance() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_memory_provenance (
                memory_id INTEGER PRIMARY KEY,
                source_kind TEXT NOT NULL,
                source_actor_id TEXT,
                origin_turn_id INTEGER,
                parent_memory_id INTEGER,
                received_minute INTEGER NOT NULL,
                shareable INTEGER NOT NULL DEFAULT 0
                    CHECK (shareable IN (0, 1))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_memory_relays (
                original_memory_id INTEGER NOT NULL,
                recipient_id TEXT NOT NULL,
                recipient_memory_id INTEGER NOT NULL UNIQUE,
                PRIMARY KEY (original_memory_id, recipient_id)
            )
            """
        )


def save_episodic_memory(
    conn,
    owner_id: str,
    text: str,
    *,
    source_kind: str,
    source_actor_id: str | None,
    minute: int,
    origin_turn_id: int | None = None,
    parent_memory_id: int | None = None,
    shareable: bool = False,
) -> int:
    """Caller owns the transaction. Use for private testimony and AI reports."""
    if not owner_id or not text.strip():
        raise ValueError("INVALID_EPISODIC_MEMORY")
    cursor = conn.execute(
        "INSERT INTO agent_memory (agent_id, memory) VALUES (?, ?)",
        (owner_id, text),
    )
    memory_id = cursor.lastrowid
    conn.execute(
        """
        INSERT INTO agent_memory_provenance
        (memory_id, source_kind, source_actor_id, origin_turn_id,
         parent_memory_id, received_minute, shareable)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            memory_id, source_kind, source_actor_id, origin_turn_id,
            parent_memory_id, minute, int(shareable),
        ),
    )
    return memory_id


def remember_agent_report(
    agent_id: str, report: str, minute: int, *, shareable: bool = False,
) -> int:
    """Internal World Core primitive, not a player/API permission to share."""
    if not isinstance(report, str) or not report.strip() or len(report) > 500:
        raise ValueError("INVALID_EPISODIC_MEMORY")
    initialize_memory_provenance()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT controller_type FROM agents WHERE id = ?",
            (agent_id,),
        ).fetchone()
        if row is None or row[0] == "HUMAN":
            raise ValueError("INVALID_REPORT_OWNER")
        return save_episodic_memory(
            conn, agent_id, report, source_kind="SELF_REPORTED",
            source_actor_id=agent_id, minute=minute, shareable=shareable,
        )


def _terms(text: str) -> set[str]:
    normalized = "".join(
        ch for ch in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(ch)
    )
    return {
        term for term in re.findall(r"[a-z0-9_]+", normalized)
        if len(term) > 2 and term not in STOPWORDS
    }


def retrieve_memories(
    agent_id: str, query: str | None = None, limit: int = 12,
) -> list[dict]:
    """Search ONLY this agent's memories; rank matches before recency.

    Uses a bounded scan of 1000 recent candidates (not semantic search).
    The latest four entries are retained to preserve immediate continuity.
    """
    if not 1 <= limit <= 100:
        raise ValueError("INVALID_CONTEXT_LIMIT")
    initialize_memory_provenance()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.memory, p.source_kind, p.source_actor_id,
                   p.origin_turn_id, p.parent_memory_id, p.received_minute
            FROM agent_memory a
            LEFT JOIN agent_memory_provenance p ON p.memory_id = a.id
            WHERE a.agent_id = ?
            ORDER BY a.id DESC LIMIT ?
            """,
            (agent_id, CANDIDATE_LIMIT),
        ).fetchall()

    def format_record(row):
        text = row[1]
        source_kind = row[2] or (
            "LEGACY_PLAYER_TESTIMONY"
            if "PLAYER_1 said:" in text
            else "LEGACY_UNCLASSIFIED"
        )
        return {
            "id": row[0],
            "text": text,
            "source_kind": source_kind,
            "source_actor_id": row[3],
            "origin_turn_id": row[4],
            "parent_memory_id": row[5],
            "received_minute": row[6],
        }

    if not rows:
        return []
    terms = _terms(query or "")
    # Score is lexical and local, never based on other agents' memories.
    recent_count = min(4, limit)
    selected = {row[0]: row for row in rows[:recent_count]}
    if terms:
        scored = []
        for row in rows[recent_count:]:
            score = len(terms.intersection(_terms(row[1])))
            if score:
                scored.append((score, row[0], row))
        for _, _, row in sorted(scored, reverse=True)[: limit - len(selected)]:
            selected[row[0]] = row
    # Without lexical matches, fill using recent memories.
    for row in rows:
        if len(selected) >= limit:
            break
        selected[row[0]] = row
    return [
        format_record(row)
        for row in sorted(selected.values(), key=lambda item: item[0])
    ]


def relay_shareable_memory(
    sender_id: str, recipient_id: str, memory_id: int, minute: int,
) -> int:
    """A validated internal AI-to-AI relay, NEVER automatic proximity gossip.

    Sender and recipient must be co-located AI actors. The source memory
    must explicitly be marked shareable by World Core. Player testimony is
    private by default; received reports cannot be relayed a second time.
    """
    initialize_memory_provenance()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        agents = {
            row[0]: (row[1], row[2])
            for row in conn.execute(
                """
                SELECT id, location, controller_type
                FROM agents WHERE id IN (?, ?)
                """,
                (sender_id, recipient_id),
            ).fetchall()
        }
        if (
            sender_id == recipient_id
            or sender_id not in agents or recipient_id not in agents
            or agents[sender_id][1] == "HUMAN"
            or agents[recipient_id][1] == "HUMAN"
            or agents[sender_id][0] != agents[recipient_id][0]
        ):
            raise ValueError("RELAY_ACTORS_NOT_COLOCATED")
        original = conn.execute(
            """
            SELECT a.memory, p.source_kind, p.shareable
            FROM agent_memory a
            JOIN agent_memory_provenance p ON p.memory_id = a.id
            WHERE a.id = ? AND a.agent_id = ?
            """,
            (memory_id, sender_id),
        ).fetchone()
        if original is None or not original[2]:
            raise ValueError("PRIVATE_OR_UNKNOWN_MEMORY")
        existing = conn.execute(
            """
            SELECT recipient_memory_id FROM agent_memory_relays
            WHERE original_memory_id = ? AND recipient_id = ?
            """,
            (memory_id, recipient_id),
        ).fetchone()
        if existing is not None:
            return existing[0]

        # A report is a claim attributed to its source, never a factual update.
        received_id = save_episodic_memory(
            conn,
            recipient_id,
            f"{sender_id} told me: {original[0]}",
            source_kind="RELAYED_TESTIMONY",
            source_actor_id=sender_id,
            parent_memory_id=memory_id,
            minute=minute,
            shareable=False,
        )
        conn.execute(
            """
            INSERT INTO agent_memory_relays
            (original_memory_id, recipient_id, recipient_memory_id)
            VALUES (?, ?, ?)
            """,
            (memory_id, recipient_id, received_id),
        )
        conn.execute(
            """
            INSERT INTO events (minute, actor_id, action, target, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (minute, sender_id, "RELAY_TESTIMONY", recipient_id, "HEARSAY"),
        )
        return received_id
