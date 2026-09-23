"""Optional, persistent new-game prologue.

Enabled only with LAIN_PROLOGUE_ENABLED=1 on an UNUSED save. No existing world
is reset or reconfigured. All progression is server-authoritative; neither
terminal text nor NPC conversation grants free-form state mutation.
"""
import os

from .database import get_connection
from .messages import INITIAL_MESSAGE_ID

PLAYER = "PLAYER_1"
STAGES = ("FIND_TEACHER", "FIND_RYOKO", "FIND_TERMINAL", "CONNECTED")
PROTOCOL = "telnet"
HOST = "wired"
PORT = "23"


def initialize_prologue() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_prologue (
                player_id TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                updated_minute INTEGER NOT NULL
            )
        """)
        if os.getenv("LAIN_PROLOGUE_ENABLED", "0") != "1":
            return
        if conn.execute(
            "SELECT 1 FROM player_prologue WHERE player_id=?", (PLAYER,)
        ).fetchone():
            return
        # Only a genuinely unused save may begin this origin story. In
        # particular, a seven-entity world or acknowledged Wired link is
        # ALWAYS treated as a continuation even if the flag was set.
        if conn.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone() != (0,):
            return
        if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]:
            return
        if conn.execute("SELECT COUNT(*) FROM generated_entities").fetchone()[0]:
            return
        if conn.execute(
            "SELECT location FROM agents WHERE id=?", (PLAYER,)
        ).fetchone() != ("APARTMENT",):
            return
        message = conn.execute(
            "SELECT acknowledged FROM world_messages WHERE id=?",
            (INITIAL_MESSAGE_ID,),
        ).fetchone()
        if message is None or bool(message[0]):
            return
        conn.execute(
            """INSERT INTO player_prologue (player_id, stage, updated_minute)
               VALUES (?, 'FIND_TEACHER', 0)""",
            (PLAYER,),
        )


def stage_for(player_id: str = PLAYER) -> str | None:
    initialize_prologue()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT stage FROM player_prologue WHERE player_id=?", (player_id,)
        ).fetchone()
    return row[0] if row else None


def gate_move(player_id: str, target_location: str) -> tuple[bool, str]:
    stage = stage_for(player_id)
    if stage in STAGES[:-1] and target_location in {"STATION", "OLD_DISTRICT"}:
        return False, "WIRED_NOT_CONNECTED"
    return True, ""


def talk_to_prologue_npc(player_id: str, npc_id: str, minute: int) -> dict:
    stage = stage_for(player_id)
    if stage is None:
        raise ValueError("NO_ACTIVE_PROLOGUE")
    if stage == "CONNECTED":
        raise ValueError("PROLOGUE_ALREADY_COMPLETE")
    if npc_id == "PROFESSOR":
        required_location = "SCHOOL_LAB"
        if stage == "FIND_TEACHER":
            next_stage = "FIND_RYOKO"
            line = (
                "No puedo enseñarte a entrar en la Wired. Solo tuve un alumno "
                "que parecia conocerla: Ryoko. No sé dónde está ahora. "
                "Si la encuentras, quizá recuerde cómo se conectaba."
            )
        else:
            next_stage = stage
            line = "El alumno se llamaba Ryoko. No he sabido nada más."
    elif npc_id == "RYOKO":
        required_location = "NIGHTCLUB"
        if stage == "FIND_TEACHER":
            next_stage = stage
            line = (
                "No hablamos de la Wired con desconocidos. "
                "Pregunta primero por el aula de informática de la escuela."
            )
        elif stage == "FIND_RYOKO":
            next_stage = "FIND_TERMINAL"
            line = (
                "La conexión se abre con una orden REAL de consola: TELNET. "
                "En tu terminal, el servidor se llama WIRED y usa el puerto 23. "
                "Busca por tu cuenta en Internet la sintaxis del comando "
                "Telnet para conectarte a un servidor y un puerto. "
                "No voy a escribirte la orden completa."
            )
        else:
            next_stage = stage
            line = (
                "Ya conoces el protocolo, el nombre del servidor y su puerto. "
                "Busca la sintaxis de Telnet y prueba en tu ordenador."
            )
    else:
        raise ValueError("UNKNOWN_PROLOGUE_CHARACTER")
    with get_connection() as conn:
        player = conn.execute(
            "SELECT location FROM agents WHERE id=?", (player_id,)
        ).fetchone()
        if player != (required_location,):
            raise ValueError("CHARACTER_NOT_PRESENT")
        if next_stage != stage:
            updated = conn.execute(
                """UPDATE player_prologue SET stage=?, updated_minute=?
                   WHERE player_id=? AND stage=?""",
                (next_stage, minute, player_id, stage),
            )
            if updated.rowcount != 1:
                raise ValueError("STALE_PROLOGUE_STAGE")
            conn.execute(
                """INSERT INTO events(minute, actor_id, action, target, details)
                   VALUES(?, ?, 'PROLOGUE_TALK', ?, ?)""",
                (minute, player_id, npc_id, next_stage),
            )
    return {"speaker": "Profesor" if npc_id == "PROFESSOR" else "Ryoko",
            "text": line, "stage": next_stage}


def submit_terminal_command(player_id: str, line: str, minute: int) -> dict:
    """Validate grammar, NEVER execute OS commands or access network."""
    if not isinstance(line, str) or len(line) > 80 or any(
        ord(character) < 32 or ord(character) == 127 for character in line
    ):
        raise ValueError("INVALID_TERMINAL_INPUT")
    stage = stage_for(player_id)
    if stage is None:
        raise ValueError("NO_ACTIVE_PROLOGUE")
    if stage == "CONNECTED":
        return {"accepted": False, "reason": "ALREADY_CONNECTED"}
    with get_connection() as conn:
        loc = conn.execute(
            "SELECT location FROM agents WHERE id=?", (player_id,)
        ).fetchone()
    if loc != ("APARTMENT",):
        raise ValueError("TERMINAL_NOT_PRESENT")
    if stage != "FIND_TERMINAL":
        return {"accepted": False, "reason": "MISSING_CONNECTION_KNOWLEDGE"}
    words = line.strip().casefold().split()
    if words != [PROTOCOL, HOST, PORT]:
        return {"accepted": False, "reason": "COMMAND_NOT_RECOGNIZED"}
    with get_connection() as conn:
        changed = conn.execute(
            """UPDATE player_prologue SET stage='CONNECTED', updated_minute=?
               WHERE player_id=? AND stage='FIND_TERMINAL'""",
            (minute, player_id),
        )
        if changed.rowcount != 1:
            raise ValueError("STALE_PROLOGUE_STAGE")
        conn.execute(
            """INSERT INTO events(minute, actor_id, action, target, details)
               VALUES(?, ?, 'PROLOGUE_CONNECTED', 'WIRED', 'TELNET_GRAMMAR')""",
            (minute, player_id),
        )
    return {"accepted": True, "reason": "LINK_ESTABLISHED"}


def prologue_projection(player_id: str = PLAYER) -> dict:
    stage = stage_for(player_id)
    if stage is None:
        return {"enabled": False, "stage": "LEGACY", "hint": ""}
    hints = {
        "FIND_TEACHER": (
            "Encuentra la escuela en el barrio, entra en su aula de "
            "informatica y habla con el profesor."
        ),
        "FIND_RYOKO": (
            "Busca a Ryoko, el antiguo alumno del profesor. "
            "Hay una discoteca en el barrio."
        ),
        "FIND_TERMINAL": (
            "Vuelve al ordenador de tu apartamento. Investiga fuera "
            "del juego la sintaxis real de TELNET para abrir una "
            "conexión a WIRED por el puerto 23."
        ),
        "CONNECTED": "Has aprendido a conectar. La historia de la Wired comienza.",
    }
    return {"enabled": True, "stage": stage, "hint": hints.get(stage, "")}
