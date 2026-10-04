"""One playable, persistent Station case: a missing beat in NODE_07.

Discovery requires the player's accepted, direct INVESTIGATE action at the
actual node. The player chooses to archive the trace or disclose it to actors
physically co-located at that instant. Broadcasting grants PLAYER_TESTIMONY,
never fabricated direct perception or private NPC memories. Other actors
respond from their individual role during subsequent autonomous ticks.
"""
from .database import get_connection

CASE_ID = "STATION_ECHO_07"
RESPONSE_BY_ROLE = {
    "ARCHIVIST": "Conserva el testimonio y busca registros con que contrastarlo.",
    "SIGNAL_KEEPER": "Vigila si se repite la ausencia de un pulso.",
    "ORIGIN_SEEKER": "Compara la interrupcion con los indicios de su propio origen.",
    "MONITOR": "Observa como reaccionan las otras presencias a la noticia.",
    "SCOUT": "Busca indicios en los alrededores de la estacion.",
    "INQUIRER": "Prepara preguntas para contrastar las versiones del pulso.",
    "WITNESS": "Guarda constancia de quienes estaban presentes al compartirlo.",
    "OBSERVER": "Presta atencion a la nueva informacion, sin una conclusion.",
}


def initialize_station_case() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS station_echo_cases (
                player_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('TRACE_FOUND','RESOLVED')),
                discovered_minute INTEGER NOT NULL,
                resolution TEXT,
                resolved_minute INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS station_echo_witnesses (
                player_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                source TEXT NOT NULL,
                learned_minute INTEGER NOT NULL,
                reaction TEXT,
                responded_minute INTEGER,
                PRIMARY KEY(player_id, actor_id)
            )
        """)


def discover_station_echo(player_id: str, minute: int) -> bool:
    """Caller already validated an accepted direct player investigation."""
    initialize_station_case()
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO station_echo_cases
               (player_id, case_id, status, discovered_minute)
               VALUES (?, ?, 'TRACE_FOUND', ?)""",
            (player_id, CASE_ID, minute),
        )
        return cursor.rowcount == 1


def case_status(player_id: str) -> str:
    initialize_station_case()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT status FROM station_echo_cases WHERE player_id=?",
            (player_id,),
        ).fetchone()
    return row[0] if row else "UNSEEN"


def validate_case_choice(player_id: str, action: str, location: str,
                         target: str) -> tuple[bool, str]:
    if action not in {"BROADCAST_TRACE", "ARCHIVE_TRACE"}:
        return False, "UNKNOWN_CASE_ACTION"
    if location != "STATION" or target != "NODE_07":
        return False, "CASE_NOT_PRESENT"
    if case_status(player_id) != "TRACE_FOUND":
        return False, ("CASE_NOT_DISCOVERED" if case_status(player_id) == "UNSEEN"
                       else "CASE_ALREADY_RESOLVED")
    return True, ""


def resolve_station_echo(player_id: str, action: str, minute: int) -> int:
    """Exactly-once player choice; actor witnesses have actual station presence."""
    if action not in {"BROADCAST_TRACE", "ARCHIVE_TRACE"}:
        raise ValueError("INVALID_CASE_CHOICE")
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE station_echo_cases
               SET status='RESOLVED', resolution=?, resolved_minute=?
               WHERE player_id=? AND status='TRACE_FOUND'""",
            (action, minute, player_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("CASE_ALREADY_RESOLVED")
        if action == "BROADCAST_TRACE":
            witnesses = conn.execute(
                """SELECT id FROM agents
                   WHERE location='STATION' AND controller_type='GENERATED'
                   ORDER BY id"""
            ).fetchall()
            for (actor_id,) in witnesses:
                conn.execute(
                    """INSERT OR IGNORE INTO station_echo_witnesses
                       (player_id, actor_id, source, learned_minute)
                       VALUES (?, ?, 'PLAYER_TESTIMONY', ?)""",
                    (player_id, actor_id, minute),
                )
            return len(witnesses)
        return 0


def has_pending_station_response(actor_id: str, location: str) -> bool:
    if location != "STATION":
        return False
    initialize_station_case()
    with get_connection() as conn:
        return conn.execute(
            """SELECT 1 FROM station_echo_witnesses w
               JOIN station_echo_cases c ON c.player_id=w.player_id
               WHERE w.actor_id=? AND w.reaction IS NULL
                 AND c.resolution='BROADCAST_TRACE' LIMIT 1""",
            (actor_id,),
        ).fetchone() is not None


def record_station_response(actor_id: str, role: str, minute: int) -> str:
    reaction = RESPONSE_BY_ROLE.get(role, RESPONSE_BY_ROLE["OBSERVER"])
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE station_echo_witnesses
               SET reaction=?, responded_minute=?
               WHERE actor_id=? AND reaction IS NULL
                 AND EXISTS(
                   SELECT 1 FROM station_echo_cases c
                   WHERE c.player_id=station_echo_witnesses.player_id
                     AND c.resolution='BROADCAST_TRACE'
                 )""",
            (reaction, minute, actor_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("CASE_RESPONSE_NOT_PENDING")
    return reaction


def actor_received_case_report(actor_id: str) -> dict | None:
    """Only the named recipient's testimony, never the entire case/journal."""
    initialize_station_case()
    with get_connection() as conn:
        row = conn.execute(
            """SELECT source, learned_minute, reaction
               FROM station_echo_witnesses
               WHERE actor_id=? ORDER BY learned_minute DESC LIMIT 1""",
            (actor_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "source": row[0], "received_minute": row[1],
        "report": (
            "El jugador me dijo que había observado un pulso ausente "
            "al investigar NODE_07. Es su testimonio, no mi observación."
        ),
        "my_response": row[2],
    }


def station_case_snapshot(player_id: str) -> dict:
    initialize_station_case()
    with get_connection() as conn:
        case = conn.execute(
            """SELECT status, discovered_minute, resolution, resolved_minute
               FROM station_echo_cases WHERE player_id=?""",
            (player_id,),
        ).fetchone()
        if case is None:
            return {
                "id": CASE_ID, "title": "El pulso ausente",
                "status": "UNSEEN", "resolution": None,
                "summary": "Investiga NODE_07 en la estacion para buscar el rastro.",
                "witness_count": 0, "responses": [],
            }
        rows = conn.execute(
            """SELECT a.id, a.name, w.reaction
               FROM station_echo_witnesses w
               JOIN agents a ON a.id=w.actor_id
               WHERE w.player_id=? AND w.reaction IS NOT NULL
               ORDER BY w.responded_minute, a.id""",
            (player_id,),
        ).fetchall()
        count = conn.execute(
            "SELECT COUNT(*) FROM station_echo_witnesses WHERE player_id=?",
            (player_id,),
        ).fetchone()[0]
    status, discovered, resolution, resolved = case
    summary = (
        "Hay una interrupcion aislada en el ritmo de NODE_07. Decide si "
        "difundir el rastro entre quienes estan aqui o archivarlo."
        if status == "TRACE_FOUND"
        else ("Has difundido el rastro entre las presencias que estaban en la estacion."
              if resolution == "BROADCAST_TRACE"
              else "Has archivado el rastro sin comunicarlo a otras presencias.")
    )
    return {
        "id": CASE_ID, "title": "El pulso ausente", "status": status,
        "resolution": resolution, "discovered_minute": discovered,
        "resolved_minute": resolved, "summary": summary,
        "witness_count": count,
        "responses": [
            {"actor_id": actor_id, "name": name, "reaction": reaction}
            for actor_id, name, reaction in rows
        ],
    }
