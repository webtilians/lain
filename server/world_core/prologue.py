"""Optional, persistent new-game prologue.

Enabled only with LAIN_PROLOGUE_ENABLED=1 on an UNUSED save. No existing world
is reset or reconfigured. All progression is server-authoritative; neither
terminal text nor NPC conversation grants free-form state mutation.
"""
import os

from .i18n import t
from .database import get_connection
from .messages import INITIAL_MESSAGE_ID

PLAYER = "PLAYER_1"
STAGES = ("FIND_TEACHER", "FIND_RYOKO", "FIND_TERMINAL", "CONNECTED")
PROTOCOL = "telnet"
HOST = "malla"
# The English clue says MESH; players who learnt the old name may still type it.
HOSTS = {HOST, "mesh", "wired"}
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


# What the player can say to each of them. Labels are the player's own words.
PROFESSOR_CHOICES = {
    "ASK_WHO": "«¿A quién me parezco?»",
    "ASK_CLASS": "«¿Qué se hacía en esta aula?»",
    "ASK_STUDENT": "«Alguien me ha escrito. Dice que usted le enseñó a hablar con la Malla.»",
    "ASK_WHERE": "«¿Dónde encuentro a Ryoko?»",
    "GOODBYE": "Dejarle con su registro.",
}
RYOKO_CHOICES = {
    "ASK_WIRED": "«Me escribieron desde mi ordenador. Firmaban Sesión Cero.»",
    "ASK_SCHOOL": "«¿Fuiste alumna del profesor?»",
    "ASK_ADDRESS": "«Necesito entrar en la Malla.»",
    "ASK_METHOD": "«¿Y qué hay que escribir delante?»",
    "GOODBYE": "Dejarla con su música.",
}

# The teacher believes in registers; his own says something he does not remember.
PROFESSOR_LINES = {
    "INTRO": (
        "El profesor no levanta la vista del registro de préstamos. «El aula cierra a las nueve. "
        "Si buscas un libro, la biblioteca está…» Entonces te mira, y el bolígrafo se le queda quieto. "
        "«Perdona. Te pareces mucho a alguien.»"
    ),
    "INTRO_AGAIN": (
        "El profesor cierra el registro en cuanto te ve entrar. «Otra vez tú. "
        "¿La has encontrado ya? A Ryoko, digo.»"
    ),
    "ASK_WHO": (
        "«A alguien que estudió aquí hace años. Se sentaba en el último puesto y se quedaba cuando ya "
        "no quedaba nadie.» Pasa páginas del registro hasta dar con una línea. «Aquí pone que se dio de "
        "baja. Con su firma. Qué raro… yo no recuerdo que se despidiera.»"
    ),
    "ASK_CLASS": (
        "«Oficialmente, a escribir cartas en un procesador de textos.» Mira los ordenadores apagados. "
        "«Había una red en el barrio, antes de que las empresas compraran los cables. Algunos se "
        "conectaban a ella desde aquí. Yo firmaba los partes y no hacía preguntas.»"
    ),
    "ASK_STUDENT": (
        "Se queda muy quieto. «Yo enseñaba a escribir cartas. Quien entendía lo que había al otro "
        "lado de esas pantallas era Ryoko.» Baja la voz. «No la busques de día. La última vez que oí "
        "su nombre fue en el Pasaje Azul, abajo, donde la música no deja oír los ventiladores.»"
    ),
    "ASK_STUDENT_AGAIN": (
        "«Ryoko. Ya te lo he dicho.» Se quita las gafas. «Y no le digas quién te manda. "
        "No firmo cosas que no puedo explicar.»"
    ),
    "ASK_WHERE_EARLY": (
        "«¿A quién buscas? Por esta aula han pasado muchos. A algunos ya no los reconocería ni "
        "mirándolos a la cara.»"
    ),
    "ASK_WHERE": (
        "«En el Pasaje Azul, de noche. Bajando las escaleras, donde suena la música.» Vuelve al "
        "registro. «Si alguien te pregunta, no has hablado conmigo.»"
    ),
    "GOODBYE": "«Cierra la puerta al salir. Con la corriente, las pantallas se apagan solas.»",
}

# Ryoko builds networks nobody owns; she trusts nobody who comes asking.
RYOKO_LINES = {
    "INTRO_STRANGER": (
        "Alguien se te pone delante entre las luces y no te deja pasar. «No te conozco. "
        "Y aquí abajo eso es un problema.»"
    ),
    "INTRO": (
        "Una chica con los auriculares al cuello te mira de arriba abajo. «Te manda el profesor. "
        "Se nota: miras las pantallas como él, como si fueran a morder.»"
    ),
    "INTRO_AGAIN": (
        "Ryoko ni se quita los auriculares. «Todavía aquí. Ese ordenador no se va a encender solo… "
        "aunque contigo, por lo visto, sí.»"
    ),
    "ASK_SCHOOL": (
        "«Me pasaba las tardes en el último puesto. Él fingía no ver lo que hacía.» Sonríe sin ganas. "
        "«Cree en los registros. Yo aprendí pronto que los registros se reescriben.»"
    ),
    "ASK_WIRED": (
        "Deja de sonreír. «La Sesión Cero.» Mira alrededor antes de seguir. «Ese nombre no debería "
        "seguir existiendo. Las sesiones que caducan… alguien se encarga de que nadie las recuerde.» "
        "Te mira otra vez, más despacio. «Si de verdad te escribió, no fue por casualidad.»"
    ),
    "ASK_ADDRESS_STRANGER": "«¿Entrar? No hablo de eso con desconocidos. ¿Quién te ha dicho que me busques?»",
    "ASK_ADDRESS": (
        "Saca una hoja doblada mil veces y te la enseña sin soltarla. A lápiz, dos cosas: MALLA y 23. "
        "«El nombre de la red y el puerto por el que escucha.» Vuelve a guardarla. «Desde tu "
        "ordenador, no desde aquí. Y lo que hay que escribir delante no te lo voy a dar: si eres "
        "quien creo, lo sabrás.»"
    ),
    "ASK_METHOD": (
        "«Una orden muy vieja, de cuando las máquinas se hablaban por turnos.» Se encoge de hombros. "
        "«Si no te acuerdas, pídele ayuda al ordenador. Los sistemas viejos siempre la tienen.»"
    ),
    "GOODBYE": "Ryoko vuelve a ponerse los auriculares. «Si te borran, no vengas a buscarme.»",
}


def _professor(choice: str, stage: str) -> tuple[str, str, list]:
    """(line, next stage, what the player can say next)."""
    met_ryoko_clue = stage != "FIND_TEACHER"
    next_stage = stage
    if choice == "INTRO":
        line = PROFESSOR_LINES["INTRO_AGAIN" if met_ryoko_clue else "INTRO"]
    elif choice == "ASK_STUDENT":
        line = PROFESSOR_LINES["ASK_STUDENT_AGAIN" if met_ryoko_clue else "ASK_STUDENT"]
        if not met_ryoko_clue:
            next_stage = "FIND_RYOKO"
    elif choice == "ASK_WHERE":
        line = PROFESSOR_LINES["ASK_WHERE" if met_ryoko_clue else "ASK_WHERE_EARLY"]
    else:
        line = PROFESSOR_LINES[choice]
    if next_stage == "FIND_TEACHER":
        options = ["ASK_WHO", "ASK_CLASS", "ASK_STUDENT", "GOODBYE"]
    else:
        options = ["ASK_WHERE", "ASK_WHO", "ASK_CLASS", "GOODBYE"]
    return line, next_stage, [option for option in options if option != choice or option == "GOODBYE"]


def _ryoko(choice: str, stage: str) -> tuple[str, str, list]:
    stranger = stage == "FIND_TEACHER"  # nobody sent you: she will not talk about the Malla
    next_stage = stage
    if choice == "INTRO":
        line = RYOKO_LINES["INTRO_STRANGER" if stranger else
                           "INTRO_AGAIN" if stage != "FIND_RYOKO" else "INTRO"]
    elif choice == "ASK_ADDRESS":
        line = RYOKO_LINES["ASK_ADDRESS_STRANGER" if stranger else "ASK_ADDRESS"]
        if stage == "FIND_RYOKO":
            next_stage = "FIND_TERMINAL"
    else:
        line = RYOKO_LINES[choice]
    if stranger:
        options = ["ASK_SCHOOL", "ASK_ADDRESS", "GOODBYE"]
    elif next_stage == "FIND_RYOKO":
        options = ["ASK_WIRED", "ASK_SCHOOL", "ASK_ADDRESS", "GOODBYE"]
    else:
        options = ["ASK_METHOD", "ASK_WIRED", "ASK_SCHOOL", "GOODBYE"]
    return line, next_stage, [option for option in options if option != choice or option == "GOODBYE"]


def talk_to_prologue_npc(
    player_id: str, npc_id: str, minute: int, choice: str = "INTRO"
) -> dict:
    """One deliberate question per interaction; opening a dialogue is read-only.

    The teacher points to where Ryoko spends her nights, never to a door on
    the map. Ryoko knows ONLY the fictional host and port: neither of them
    names a real protocol, a program, its syntax, a website, or a plan for
    solving the terminal puzzle. Each answer comes with what the player can
    say next, so a conversation follows what was said.
    """
    stage = stage_for(player_id)
    if stage is None:
        raise ValueError("NO_ACTIVE_PROLOGUE")
    if npc_id not in {"PROFESSOR", "RYOKO"}:
        raise ValueError("UNKNOWN_PROLOGUE_CHARACTER")
    required_location = "SCHOOL_LAB" if npc_id == "PROFESSOR" else "NIGHTCLUB"
    labels = PROFESSOR_CHOICES if npc_id == "PROFESSOR" else RYOKO_CHOICES
    if choice != "INTRO" and choice not in labels:
        raise ValueError("INVALID_PROLOGUE_QUESTION")
    with get_connection() as conn:
        player = conn.execute(
            "SELECT location FROM agents WHERE id=?", (player_id,)
        ).fetchone()
    if player != (required_location,):
        raise ValueError("CHARACTER_NOT_PRESENT")

    line, next_stage, options = (_professor if npc_id == "PROFESSOR" else _ryoko)(choice, stage)

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
        "speaker": t("Profesor") if npc_id == "PROFESSOR" else "Ryoko",
        "text": t(line), "stage": next_stage,
        "closed": choice == "GOODBYE",
        "choices": [{"id": option, "text": t(labels[option])} for option in options],
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
    if len(words) != 3 or words[0] != PROTOCOL or words[1] not in HOSTS or words[2] != PORT:
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
            "Alguien que firma «Sesión Cero» te ha escrito desde tu propio ordenador. "
            "Busca en el colegio a quien le enseñó a hablar con la Malla: el aula de informática."
        ),
        "FIND_RYOKO": (
            "El profesor habló de Ryoko: de noche, en el Pasaje Azul, bajando las escaleras "
            "donde suena la música."
        ),
        "FIND_TERMINAL": (
            "MALLA y 23: el nombre de la red y su puerto. Ryoko no quiso decirte qué escribir "
            "delante. El ordenador de tu casa espera; si no sabes qué orden usar, pídele ayuda."
        ),
        "CONNECTED": "Estás en la Malla. La Sesión Cero sigue ahí dentro, en algún sitio.",
    }
    return {"enabled": True, "stage": stage, "hint": t(hints.get(stage, ""))}
