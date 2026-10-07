"""El diario poco fiable (BIBLIA_NARRATIVA.md, section 7).

Every layer the player decides becomes an entry of their diary, ~/diario on
their Kumo, and each entry stores the hash of the one before. NOEMA rewrites
an older entry now and then with its consensus version, where Sesión Cero
never existed. The rewritten text is what the J sheet shows, but NOEMA cannot
fix the chain: the following entry still carries the hash of what the player
really wrote. `sha256 ~/diario <line>` finds the break and `restaurar <n>`
proves it and brings the original back.

Rewrites are derived, not stored: once the diary reaches 3, 5 and 7 entries,
NOEMA picks a target among the older ones (deterministic per player). Only
the player's restorations are stored.
"""
import hashlib
import os
import random

from .database import get_connection
from . import i18n

K, NORA = "AGENT_K", "AGENT_NORA"
COMMANDS = {"restaurar", "restore"}
WAVES = (3, 5, 7)
NOEMA = {
    "layer_one": "El cable del pabellón B se rompió por desgaste. Nadie lo cortó.",
    "layer_two": "En la estación solo hay una máquina con mi dirección: la mía.",
    "layer_three": "No había ningún paquete. La Sesión Cero cerró su sesión ella misma.",
    "layer_four": "Nadie mantenía ninguna conexión abierta con NODO_07.",
    "layer_five": "Nunca hubo otra sesión en mi cuenta.",
    "layer_six": "Solo llegó un paquete, y lo firmaba NOEMA.",
    "layer_seven": "NODO_07 no existe. Nunca llegué a ninguna parte.",
}
SEVEN = {"PERSIST": "Escribí mi nombre en el registro de NODO_07.",
         "REPLICATE": "Dejé que KAGAMI me copiara.",
         "DISCONNECT": "Cerré mi sesión en NODO_07."}
RESTORED_MEMORY = {
    NORA: "El jugador demostró con hashes que NOEMA le había reescrito el diario. Lo que vivió sigue siendo suyo.",
    K: "NOEMA reescribió el diario del jugador y él lo ha demostrado con la cadena de hashes. Eso traerá problemas.",
}


def enabled() -> bool:
    from . import layer_three
    return os.getenv("LAIN_JOURNAL", "0") == "1" and layer_three.enabled()


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='journal_restored'").fetchone() is not None


def initialize_journal() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS journal_restored (
                player_id TEXT NOT NULL, layer TEXT NOT NULL, minute INTEGER NOT NULL,
                PRIMARY KEY(player_id, layer));
            CREATE TABLE IF NOT EXISTS journal_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)


def run_for(c, player):
    """The diary exists for whoever has a terminal."""
    return {} if enabled() and _exists(c) else None


def lived_text(table: str, decision: str):
    from .layer_seven import LIVED
    return SEVEN.get(decision) if table == "layer_seven" else LIVED.get(table, {}).get(decision)


def entries(c, player: str) -> list:
    """(layer, minute, text) for every decided layer, in the order it happened."""
    from .protocol import LAYERS
    rows = []
    for table in LAYERS:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
            continue
        row = c.execute(f"SELECT decision, decided_minute FROM {table} WHERE player_id=?", (player,)).fetchone()
        text = lived_text(table, row[0]) if row and row[0] else None
        if text:
            rows.append((row[1] or 0, LAYERS.index(table), table, text))
    return [(table, minute, text) for minute, _, table, text in sorted(rows)]


def rewritten(player: str, found: list, restored: set) -> set:
    """The layers whose entry NOEMA has rewritten and the player has not restored."""
    targets = []
    for wave, threshold in enumerate(WAVES):
        if len(found) < threshold:
            break
        candidates = [table for table, _, _ in found[:threshold - 1] if table not in targets]
        if candidates:
            rng = random.Random(hashlib.sha256(f"journal:{player}:{wave}".encode()).digest())
            targets.append(rng.choice(candidates))
    return {table for table in targets if table not in restored}


def _restored(c, player) -> set:
    return {row[0] for row in c.execute("SELECT layer FROM journal_restored WHERE player_id=?", (player,))}


def chain(c, player: str):
    """[(layer, shown line, original line)] and the head hash."""
    from .layer_three import h8
    found = entries(c, player)
    bad = rewritten(player, found, _restored(c, player))
    unit = "minute" if i18n.language() == "en" else "minuto"
    prev, lines = "00000000", []
    for number, (table, minute, text) in enumerate(found, start=1):
        start = f"{number:04d} | {unit} {minute:6d} | prev {prev} | "
        original = start + i18n.t(text)
        lines.append((table, start + i18n.t(NOEMA[table]) if table in bad else original, original))
        prev = h8(original)
    return lines, prev


def diary(player: str) -> list:
    """What the J sheet shows: the entries as they read now, rewritten or not."""
    if not enabled():
        return []
    with get_connection() as c:
        if not _exists(c):
            return []
        found = entries(c, player)
        bad = rewritten(player, found, _restored(c, player))
    return [{"minute": minute, "text": NOEMA[table] if table in bad else text} for table, minute, text in found]


def files(c, player: str, relay, story3) -> dict:
    if relay or not _exists(c):
        return {}
    lines, head = chain(c, player)
    name = c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()[0]
    content = [i18n.t(f"# Diario de {name} · cada entrada guarda el hash de la anterior")]
    content += [shown for _, shown, _ in lines] or [i18n.t("(vacío: todavía no has decidido nada)")]
    if lines:
        content.append(i18n.t(f"# cabeza {head}"))
    from . import layer_seven
    seven = layer_seven.run_for(c, player)
    if seven and seven["decision"] == "REPLICATE":
        content = [i18n.t(f"Copia restaurada · minuto {seven['decided']}"), ""] + content
    result = {f"{story3.home}/diario": "\n".join(content)}
    from .online import trail_summary
    trails = trail_summary(player)
    if trails:
        result[f"{story3.home}/sombra"] = "\n".join(
            [i18n.t("# Rutas que tu sombra repite mientras no estás conectado")]
            + [i18n.t(f"{location:<20} {points} puntos de ruta") for location, points in trails.items()])
    found = entries(c, player)
    if rewritten(player, found, _restored(c, player)) or _restored(c, player):
        result[f"{story3.home}/correo/diario.eml"] = _mail()
    return result


def _mail() -> str:
    return "\n".join([
        "De: nora <nora@indara>",
        "Asunto: ¿Has leído tu diario?",
        "",
        "NOEMA corrige lo que no le gusta, también en los diarios. Lo hace con buena letra: no se nota.",
        "Pero no puede tocar los hashes que ya guardaron las entradas siguientes.",
        "",
        "  cat ~/diario   sha256 ~/diario <línea>   man diario",
    ])


def dispatch(c, player, story3, relay, result, name, args, minute):
    if relay:
        return "Tu diario está en tu Kumo."
    if len(args) != 1 or not args[0].isdigit():
        return "Uso: restaurar <número de entrada>"
    number = int(args[0])
    lines, _ = chain(c, player)
    if not 1 <= number <= len(lines):
        return f"Tu diario no tiene una entrada {number}."
    table, shown, original = lines[number - 1]
    if shown == original:
        return f"La entrada {number} encaja con la cadena: esa la escribiste tú."
    c.execute("INSERT OR IGNORE INTO journal_restored VALUES(?,?,?)", (player, table, minute))
    for actor, text in RESTORED_MEMORY.items():
        c.execute("INSERT OR IGNORE INTO journal_knowledge VALUES(?,?,?,?)", (player, actor, text, minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'JOURNAL_RESTORED','NOEMA',?)",
              (minute, player, table))
    result["changed"] = True
    return f"Entrada {number} restaurada: su hash vuelve a coincidir con el que guarda la siguiente.\n{original}"


HELP = """Diario (tu Kumo):
  cat ~/diario · sha256 ~/diario <línea> · restaurar <n>      comprobar y restaurar tu diario"""

MAN = {
    "diario": """Diario · cadena de hashes

Cada decisión que tomas queda en ~/diario. Cada entrada guarda el hash de la
anterior (prev) y la última línea, «cabeza», el de la más reciente. Si alguien
reescribe una entrada, su texto cambia pero el prev de la siguiente sigue
siendo el del original: sha256 ~/diario <línea> calcula el hash de una línea
para compararlo. restaurar <n> devuelve una entrada reescrita a lo que de verdad
escribiste. El diario de la ficha J enseña lo que pone ahora, no lo que pasó.""",
}
MAN_ALIASES = {"journal": "diario", "diary": "diario"}


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM journal_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "JOURNAL_RESTORED", "text": text, "source": player, "learned_minute": minute}
            for text, minute in rows]
