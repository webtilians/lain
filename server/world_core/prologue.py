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


def talk_to_prologue_npc(
    player_id: str, npc_id: str, minute: int, choice: str = "INTRO"
) -> dict:
    """One deliberate question per interaction; opening a dialogue is read-only.

    The teacher does not know Ryoko's location. Ryoko knows ONLY the
    fictional host and port: neither NPC names a real protocol, a program,
    its syntax, a website, or a plan for solving the terminal puzzle.
    """
    stage = stage_for(player_id)
    if stage is None:
        raise ValueError("NO_ACTIVE_PROLOGUE")
    if npc_id not in {"PROFESSOR", "RYOKO"}:
        raise ValueError("UNKNOWN_PROLOGUE_CHARACTER")
    required_location = "SCHOOL_LAB" if npc_id == "PROFESSOR" else "NIGHTCLUB"
    allowed = (
        {"INTRO", "ASK_CLASS", "ASK_STUDENT", "ASK_WHERE", "GOODBYE"}
        if npc_id == "PROFESSOR"
        else {"INTRO", "ASK_SCHOOL", "ASK_WIRED", "ASK_ADDRESS",
              "ASK_METHOD", "GOODBYE"}
    )
    if choice not in allowed:
        raise ValueError("INVALID_PROLOGUE_QUESTION")
    with get_connection() as conn:
        player = conn.execute(
            "SELECT location FROM agents WHERE id=?", (player_id,)
        ).fetchone()
    if player != (required_location,):
        raise ValueError("CHARACTER_NOT_PRESENT")

    next_stage = stage
    if npc_id == "PROFESSOR":
        lines = {
            "INTRO": (
                "La pantalla lleva años apagada. El profesor no se vuelve "
                "inmediatamente. «¿Has venido a por algún libro?»"
            ),
            "ASK_CLASS": (
                "«Teníamos pocos ordenadores. La mayoría aprendía "
                "a escribir documentos. A veces alguien se quedaba "
                "hasta que cerraban las puertas.»"
            ),
            "ASK_WHERE": (
                "«¿Dónde está? No lo sé. Dejé de verla al acabar el curso. "
                "Ni siquiera sé si conserva el mismo nombre.»"
                if stage != "FIND_TEACHER"
                else "«¿A quién buscas? Hay antiguos alumnos a los "
                "que ya no reconocería.»"
            ),
            "GOODBYE": "El profesor vuelve la mirada a la pantalla vacía.",
        }
        if choice == "ASK_STUDENT":
            if stage == "FIND_TEACHER":
                next_stage = "FIND_RYOKO"
                line = (
                    "«Solo hubo una persona que parecía entender qué había "
                    "al otro lado de esas pantallas. Ryoko. "
                    "No sé dónde está ahora.»"
                )
            else:
                line = (
                    "«Ryoko. No tengo ningún dato nuevo sobre su paradero. "
                    "¿Por qué te interesa tanto?»"
                )
        else:
            line = lines[choice]
    else:
        lines = {
            "INTRO": (
                "Entre la música alguien te observa un instante. "
                "«No creo que nos conozcamos.»"
            ),
            "ASK_SCHOOL": (
                "«La escuela... Hace mucho que no paso por allí. "
                "¿Todavía guardan aquellos ordenadores?»"
            ),
            "ASK_WIRED": (
                "«Las cosas no siempre son lo que parecen en una pantalla. "
                "No todo lo que responde está al otro lado.»"
            ),
            "ASK_METHOD": (
                "«No recuerdo las teclas. Recuerdo esperar. "
                "Lo demás tendrás que averiguarlo tú.»"
            ),
            "GOODBYE": "Ryoko se pierde de nuevo entre las luces.",
        }
        if choice == "ASK_ADDRESS":
            if stage == "FIND_TEACHER":
                line = (
                    "«No hablo de direcciones con desconocidos. "
                    "¿Cómo has llegado hasta mí?»"
                )
            else:
                if stage == "FIND_RYOKO":
                    next_stage = "FIND_TERMINAL"
                line = (
                    "«Había dos datos escritos en una hoja: "
                    "WIRED y 23. El segundo era el puerto. "
                    "No conservo la hoja. Lo demás tendrás que averiguarlo tú.»"
                )
        else:
            line = lines[choice]

    if next_stage != stage:
        with get_connection() as conn:
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
    return {
        "speaker": "Profesor" if npc_id == "PROFESSOR" else "Ryoko",
        "text": line, "stage": next_stage,
        "closed": choice == "GOODBYE",
    }


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
            "En el barrio está la antigua escuela. "
            "En el aula de informática quizá quede alguien que recuerde."
        ),
        "FIND_RYOKO": (
            "El profesor pronunció un nombre: Ryoko. "
            "No sabe dónde está. El barrio parece tener otra vida al caer la noche."
        ),
        "FIND_TERMINAL": (
            "WIRED. Puerto 23. Dos datos que Ryoko no quiso explicar. "
            "El ordenador de tu apartamento sigue esperando."
        ),
        "CONNECTED": "La conexión cambió algo. Quizá ahora puedas descubrir qué.",
    }
    return {"enabled": True, "stage": stage, "hint": hints.get(stage, "")}
