from contextlib import closing

from .beliefs import initialize_beliefs
from .database import get_connection
from .knowledge import initialize_knowledge
from .messages import initial_message_id, acknowledge_message
from .prologue import stage_for


INITIAL_WIRED_NODE = "NODE_07"


def grant_initial_wired_lead(player_id: str, minute: int) -> bool:
    """Commit knowledge, belief and provenance together; repair older partial saves.

    INSERT OR IGNORE preserves any newer direct observation on reconnect. The
    old acknowledgement timestamp keeps a repaired lead in its original chronology.
    """
    initialize_knowledge()
    initialize_beliefs()
    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        acknowledgement = conn.execute(
            "SELECT acknowledged_minute FROM world_messages WHERE id=? AND recipient_id=? AND acknowledged=1",
            (initial_message_id(player_id), player_id),
        ).fetchone()
        acquired = (
            acknowledgement[0]
            if acknowledgement and acknowledgement[0] is not None
            else minute
        )
        knowledge = conn.execute(
            """INSERT OR IGNORE INTO agent_knowledge (agent_id,node_id,confidence,source)
               VALUES(?,?,0.35,'WIRED_MESSAGE')""",
            (player_id, INITIAL_WIRED_NODE),
        ).rowcount
        belief = conn.execute(
            """INSERT OR IGNORE INTO node_beliefs
               (agent_id,node_id,believed_location,believed_strength,confidence,source,updated_minute)
               VALUES(?,?,'STATION',0.50,0.35,'WIRED_MESSAGE',?)""",
            (player_id, INITIAL_WIRED_NODE, acquired),
        ).rowcount
        # Also repairs the historic gap after knowledge was saved but before
        # its acquisition event was written. Stronger beliefs are untouched.
        conn.execute(
            """INSERT INTO events(minute,actor_id,action,target,details)
               SELECT ?,?,'WIRED_LEAD_RECEIVED',?,?
               WHERE NOT EXISTS (SELECT 1 FROM events WHERE actor_id=?
                   AND action='WIRED_LEAD_RECEIVED' AND target=?)
               AND EXISTS (SELECT 1 FROM agent_knowledge WHERE agent_id=? AND node_id=? AND source='WIRED_MESSAGE')""",
            (
                acquired,
                player_id,
                INITIAL_WIRED_NODE,
                "Anonymous Wired connection revealed a low-confidence signal lead",
                player_id,
                INITIAL_WIRED_NODE,
                player_id,
                INITIAL_WIRED_NODE,
            ),
        )
        return bool(knowledge or belief)


def process_wired_message_acknowledgement(
    message_id: str, player_id: str, minute: int
) -> dict:
    # Neither legacy CONNECT nor direct API calls can bypass a new prologue.
    initial = message_id == initial_message_id(player_id)
    if initial and stage_for(player_id) not in (None, "CONNECTED"):
        raise ValueError("PROLOGUE_TERMINAL_REQUIRED")

    newly_acknowledged = acknowledge_message(
        message_id=message_id, player_id=player_id, minute=minute
    )
    # Acknowledgement may already have committed before a crash. Reconcile
    # the idempotent effect on every retry, not only on the first receipt.
    lead_granted = grant_initial_wired_lead(player_id, minute) if initial else False

    from .chapter_one import activate_chapter
    activate_chapter(player_id)
    from .network_conflict import enroll_connected_players
    enroll_connected_players()
    from .workshop import enroll_workshop
    enroll_workshop()
    return {"newly_acknowledged": newly_acknowledged, "lead_granted": lead_granted}
