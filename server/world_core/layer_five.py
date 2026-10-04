"""Capa 05 · Sesión (BIBLIA_NARRATIVA.md, section 6).

NODO_07 found an expired session with the player's name (Sesión Cero) and the
account admits a single active session. At the station cabinet's console the
player reads three JSON states (common ancestor, Sesión Cero, their own),
performs a three-way merge field by field, commits it with optimistic
concurrency (the next version) under the current lease's fencing token, and
then decides which session holds the account.

Concepts: session expiry, leases, fencing tokens, compare-and-swap versions
and three-way merge. Values are generated per player and frozen in the
language the layer started in; explanations go through the catalogue.
"""
import hashlib
import json
import os
import random

from .database import get_connection
from . import i18n

TITLE = "Capa 05 · Sesión"
ARCHIVE = "RELAY_STATION"
K, NORA = "AGENT_K", "AGENT_NORA"
COMMANDS = {"sessions", "sesiones", "merge", "fusionar", "commit", "confirmar", "lease", "expire", "caducar"}
FIELDS = ("name", "last_place", "trusts", "fears", "remembers_node07", "open_connections", "fragments", "kept_word")
WORDS = ["lluvia", "faro", "eco", "umbral", "marea", "ceniza", "vigilia", "deriva"]
VALUES = {
    "es": {"lab": "aula de informática", "node": "NODO_07", "platform": "andén", "nobody": "nadie",
           "forget": "olvidar", "vanish": "desaparecer", "silence": "el silencio"},
    "en": {"lab": "computer room", "node": "NODO_07", "platform": "platform", "nobody": "nobody",
           "forget": "forgetting", "vanish": "vanishing", "silence": "silence"},
}
WORDS_EN = {"lluvia": "rain", "faro": "lighthouse", "eco": "echo", "umbral": "threshold", "marea": "tide",
            "ceniza": "ash", "vigilia": "vigil", "deriva": "drift"}


def enabled() -> bool:
    return os.getenv("LAIN_LAYER_FIVE", "0") == "1"


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_five'").fetchone() is not None


def initialize_layer_five() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS layer_five (
                player_id TEXT PRIMARY KEY, started_minute INTEGER NOT NULL, language TEXT NOT NULL,
                trusts TEXT NOT NULL, open_connections INTEGER NOT NULL, fragments INTEGER NOT NULL,
                working TEXT NOT NULL DEFAULT '{}', committed TEXT, rejected INTEGER NOT NULL DEFAULT 0,
                decision TEXT, decided_minute INTEGER);
            CREATE TABLE IF NOT EXISTS layer_five_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_four'").fetchone():
            minute = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
            for player, decision in c.execute(
                    "SELECT player_id, decision FROM layer_four WHERE decision IS NOT NULL").fetchall():
                activate(c, player, minute, decision)


def activate(c, player: str, minute: int, previous: str, language: str | None = None) -> bool:
    """Starts once Capa 04 is decided; what Sesión Uno is depends on that choice."""
    if not enabled() or not _exists(c):
        return False
    lang = i18n.normalize(language or i18n.language())
    values = VALUES[lang]
    trusts = {"FIN": "K", "RST": values["nobody"], "KEEPALIVE": "Nora"}.get(previous, values["nobody"])
    created = c.execute(
        "INSERT OR IGNORE INTO layer_five(player_id, started_minute, language, trusts, open_connections, fragments)"
        " VALUES(?,?,?,?,?,?)",
        (player, minute, lang, trusts, 1 if previous == "KEEPALIVE" else 0, 2),
    ).rowcount
    if created:
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_FIVE_STARTED','NODE_07',?)",
                  (minute, player, previous))
    return bool(created)


def run_for(c, player):
    if not enabled() or not _exists(c):
        return None
    row = c.execute(
        """SELECT started_minute, language, trusts, open_connections, fragments, working, committed,
        rejected, decision FROM layer_five WHERE player_id=?""", (player,)).fetchone()
    if row is None:
        return None
    keys = ("started", "language", "trusts", "open_connections", "fragments", "working", "committed",
            "rejected", "decision")
    run = dict(zip(keys, row))
    run["working"] = json.loads(run["working"])
    run["committed"] = json.loads(run["committed"]) if run["committed"] else None
    return run


class Story:
    """Three versions of the same account, derived from the player's id and choices."""

    def __init__(self, player: str, name: str, run: dict):
        rng = random.Random(hashlib.sha256(("layer5:" + player).encode()).digest())
        values = VALUES[run["language"]]
        word = rng.choice(WORDS)
        self.word = word if run["language"] == "es" else WORDS_EN[word]
        self.base = {"name": name, "last_place": values["lab"], "trusts": "Ryoko", "fears": values["forget"],
                     "remembers_node07": False, "open_connections": 0, "fragments": 0, "kept_word": None}
        self.s0 = dict(self.base, last_place=values["node"], trusts="Nora", remembers_node07=True,
                       open_connections=1, kept_word=self.word)
        self.s1 = dict(self.base, last_place=values["platform"], trusts=run["trusts"], fears=values["vanish"],
                       open_connections=run["open_connections"], fragments=run["fragments"])
        # Some players' Sesión Cero also changed what it feared: one more conflict.
        if rng.random() < 0.5:
            self.s0["fears"] = values["silence"]
        self.version = rng.randrange(20, 60)
        self.s0_version = rng.randrange(3, 12)
        self.token = rng.randrange(40, 99)
        self.s0_token = self.token - rng.randrange(6, 30)
        self.started = run["started"]

    def resolution(self, field):
        """('auto', value) when only one side changed (or both alike); ('conflict', None) otherwise."""
        base, left, right = self.base[field], self.s0[field], self.s1[field]
        if left == right:
            return "auto", left
        if left == base:
            return "auto", right
        if right == base:
            return "auto", left
        return "conflict", None


def _story(c, player, run):
    name = c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()[0]
    return Story(player, name, run)


def _json(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False, indent=2)


def files(c, player: str, relay, story3) -> dict:
    run = run_for(c, player)
    if run is None:
        return {}
    story = _story(c, player, run)
    if relay != ARCHIVE:
        if relay:
            return {}
        return {f"{story3.home}/correo/sesion.eml": _mail()}
    result = {
        "/var/lib/sesiones/base.json": _json(story.base),
        "/var/lib/sesiones/s0.json": _json(story.s0),
        "/var/lib/sesiones/s1.json": _json(story.s1),
        "/var/lib/sesiones/LEEME": ("Archivo de sesiones de NODO_07.\n"
                                    "base.json es el último estado común; s0.json y s1.json, lo que cambió cada sesión después.\n"
                                    "La cuenta admite una sola sesión activa: quien tiene el arrendamiento (lease)."),
    }
    if run["committed"]:
        result["/var/lib/sesiones/fusion.json"] = _json(run["committed"])
    return result


def _mail() -> str:
    return "\n".join([
        "De: nodo07 <sesiones@wired>",
        "Asunto: Dos sesiones, una cuenta",
        "",
        "NODO_07 ha encontrado una sesión caducada con tu nombre: la Sesión Cero.",
        "Tu cuenta solo admite una sesión activa.",
        "Antes de decidir cuál sigue, hay que fusionar lo que recuerda cada una.",
        "",
        "El archivo de sesiones está en NODO_07. Se monta en la consola del armario del andén.",
        "",
        "  man sesion   man lease   man fencing   man version   man merge",
    ])


def _sessions(story, relay):
    if relay != ARCHIVE:
        return "El archivo de sesiones está en NODO_07: se monta en la consola del armario del andén."
    return "\n".join([
        "id   state     version  last_seen         lease_token",
        f"s0   EXPIRED   v{story.s0_version:<6} minute {max(0, story.started - 900):<9} {story.s0_token}",
        f"s1   ACTIVE    v{story.version:<6} minute {story.started:<9} {story.token}",
        f"lease account:{story.base['name']}  holder=s1  fencing_token={story.token}",
    ])


def _merge(c, player, story, run, result, args):
    if run["committed"]:
        return "La fusión ya está confirmada: /var/lib/sesiones/fusion.json"
    if not args:
        lines = ["Fusión en curso (campo: valor elegido):"]
        for field in FIELDS:
            value = run["working"].get(field, "<sin elegir>")
            lines.append(f"  {field}: {json.dumps(value, ensure_ascii=False) if field in run['working'] else value}")
        return "\n".join(lines)
    if len(args) != 2 or args[0] not in FIELDS or args[1] not in {"base", "s0", "s1"}:
        return "Uso: merge <campo> <base|s0|s1>   ·   merge  (ver la fusión en curso)"
    field, side = args
    value = {"base": story.base, "s0": story.s0, "s1": story.s1}[side][field]
    working = dict(run["working"], **{field: value})
    c.execute("UPDATE layer_five SET working=? WHERE player_id=?", (json.dumps(working, ensure_ascii=False), player))
    result["changed"] = True
    return f"{field} = {json.dumps(value, ensure_ascii=False)} (de {side})"


def _commit(c, player, story, run, result, args):
    if run["committed"]:
        return "La fusión ya está confirmada."
    options = dict(arg.split("=", 1) for arg in args if "=" in arg)
    if not options.get("version", "").isdigit() or not options.get("token", "").isdigit():
        return "Uso: commit version=<n> token=<n>"
    missing = [field for field in FIELDS if field not in run["working"]]
    if missing:
        return "Faltan campos por fusionar: " + ", ".join(missing)
    if int(options["token"]) != story.token:
        c.execute("UPDATE layer_five SET rejected=rejected+1 WHERE player_id=?", (player,))
        result["changed"] = True
        return ("Escritura rechazada: ese token de exclusión no es el del arrendamiento actual. "
                "El almacén solo acepta escrituras del titular vigente.")
    if int(options["version"]) != story.version + 1:
        c.execute("UPDATE layer_five SET rejected=rejected+1 WHERE player_id=?", (player,))
        result["changed"] = True
        return f"Conflicto de versión: s1 está en v{story.version}. Una escritura debe proponer la versión siguiente."
    for field in FIELDS:
        kind, expected = story.resolution(field)
        if kind == "auto" and run["working"][field] != expected:
            c.execute("UPDATE layer_five SET rejected=rejected+1 WHERE player_id=?", (player,))
            result["changed"] = True
            return (f"La fusión pierde un cambio en «{field}»: comparado con base.json, solo una de las dos "
                    "sesiones lo modificó, y ese cambio debe conservarse.")
        if kind == "conflict" and run["working"][field] not in (story.s0[field], story.s1[field]):
            return f"«{field}» cambió en las dos sesiones: elige s0 o s1, no base."
    c.execute("UPDATE layer_five SET committed=? WHERE player_id=?",
              (json.dumps(run["working"], ensure_ascii=False), player))
    result["changed"] = True
    conflicts = [field for field in FIELDS if story.resolution(field)[0] == "conflict"]
    return (f"Fusión confirmada: s1 v{story.version + 1}, escrita con el token {story.token}.\n"
            f"Conflictos resueltos por ti: {', '.join(conflicts)}.\n"
            "Ahora decide quién conserva la cuenta: lease s1, lease s0 o expire s0.")


MEMORIES = {
    "KEEP": {
        NORA: "El jugador fusionó sus recuerdos con los de la Sesión Cero y conservó la cuenta. Ella vive en lo que él recuerda.",
        K: "La cuenta del jugador vuelve a tener un solo titular, con un estado fusionado. Estable.",
    },
    "YIELD": {
        NORA: "El jugador le devolvió la cuenta a la Sesión Cero, con los recuerdos de los dos. No sé si sigo hablando con la misma persona.",
        K: "La Sesión Cero ha vuelto a ser la titular de la cuenta. Hay que vigilar NODO_07.",
    },
    "ERASE": {
        NORA: "El jugador borró del archivo a la Sesión Cero después de quedarse con lo que recordaba. Eso no se lo perdono.",
        K: "El archivo de la Sesión Cero ha sido eliminado. Un problema menos en NODO_07.",
    },
}
ENDINGS = {
    "KEEP": "El arrendamiento sigue siendo tuyo, con los recuerdos de las dos sesiones.\n"
            "¿Eres la misma persona que empezó a jugar? Nadie puede comprobarlo. Tampoco tú.",
    "YIELD": "Entregas el arrendamiento a la Sesión Cero. Vuelve con tus recuerdos y con los suyos.\n"
             "Tú pasas a ser una versión anterior en el archivo. Sigues jugando, pero el mundo te llama sesión 0.",
    "ERASE": "Borras el archivo de la Sesión Cero. Lo que recordaba sigue en tu fusión; ella ya no.\n"
             "El recolector de basura no pregunta.",
}


def _decide(c, player, story, run, result, decision, minute):
    if not run["committed"]:
        return "Primero confirma la fusión (commit). Sin ella, cualquier decisión borra la mitad de alguien."
    if run["decision"]:
        return "Ya decidiste quién conserva la cuenta."
    c.execute("UPDATE layer_five SET decision=?, decided_minute=? WHERE player_id=?", (decision, minute, player))
    for actor, text in MEMORIES[decision].items():
        c.execute("INSERT OR REPLACE INTO layer_five_knowledge VALUES(?,?,?,?)", (player, actor, text, minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_FIVE_DECISION','SESSION',?)",
              (minute, player, decision))
    from . import layer_six
    layer_six.activate(c, player, minute, decision)
    result["changed"] = True
    return (ENDINGS[decision] + "\n\nCAPA 05 COMPLETADA · fragmento 5/7 de la Sesión Cero recuperado.\n"
            f"Siguiente: Capa 06 · Presentación. La palabra que guardaba la Sesión Cero ({story.word}) abre algo.")


def dispatch(c, player, story3, relay, result, name, args, minute):
    run = run_for(c, player)
    if run is None:
        return f"{name}: orden desconocida. Escribe help."
    story = _story(c, player, run)
    name = {"sesiones": "sessions", "fusionar": "merge", "confirmar": "commit", "caducar": "expire"}.get(name, name)
    if name == "sessions":
        return _sessions(story, relay)
    if relay != ARCHIVE:
        return "El archivo de sesiones está en NODO_07: se monta en la consola del armario del andén."
    if name == "merge":
        return _merge(c, player, story, run, result, args)
    if name == "commit":
        return _commit(c, player, story, run, result, args)
    if name == "lease" and args in (["s1"], ["s0"]):
        return _decide(c, player, story, run, result, "KEEP" if args == ["s1"] else "YIELD", minute)
    if name == "expire" and args == ["s0"]:
        return _decide(c, player, story, run, result, "ERASE", minute)
    return "Uso: lease s1 · lease s0 · expire s0"


def session_label(c, player: str) -> str:
    run = run_for(c, player)
    return i18n.t("sesión 0 (restaurada)") if run and run["decision"] == "YIELD" else i18n.t("sesión 1")


HELP = """Capa 05 (consola del andén):
  sessions               sesiones de tu cuenta    merge <campo> <base|s0|s1>
  commit version=<n> token=<n>                    escribir la fusión
  lease s1 · lease s0 · expire s0                 quién conserva la cuenta"""

MAN = {
    "sesion": """Sesión

Una sesión es el estado de alguien mientras está conectado: quién es, qué ha
hecho, qué recuerda. Caduca si pasa demasiado tiempo sin actividad (idle
timeout) y queda archivada. Restaurar una sesión caducada no la hace la misma:
es su último estado guardado, vuelto a cargar.""",
    "lease": """Lease · arrendamiento

Para que solo una sesión use la cuenta a la vez, el sistema concede un
arrendamiento: un permiso exclusivo con caducidad. Quien lo tiene es el
titular; si deja de renovarlo, caduca y otro puede tomarlo. Cada concesión
lleva un número que solo crece: el token de exclusión (man fencing).""",
    "fencing": """Fencing token · token de exclusión

Un titular antiguo puede despertar tarde y creer que aún manda. Para evitarlo,
cada arrendamiento nuevo trae un número mayor que el anterior, y el almacén
rechaza cualquier escritura que lleve un número menor que el último que vio.
Solo escribe quien presenta el token vigente.""",
    "version": """Versiones · concurrencia optimista

Cada estado guardado tiene un número de versión. Para escribir, propones la
versión siguiente a la que leíste (compare-and-swap): si alguien escribió
antes, la versión ya no coincide y tu escritura se rechaza en lugar de pisar
la suya.""",
    "merge": """Fusión a tres bandas

Cuando dos versiones parten de un antepasado común (base), cada campo se
compara con él:
  - si solo cambió en una de las dos, gana ese cambio;
  - si cambió igual en las dos, no hay problema;
  - si cambió distinto en las dos, hay un conflicto y alguien tiene que elegir.
Es lo que hace git al fusionar ramas. merge <campo> <base|s0|s1> elige el
valor; merge sin argumentos enseña la fusión en curso.""",
    "json": "JSON · texto con estructura: {\"campo\": valor}. true/false, números, texto entre comillas y null (sin valor).",
}
MAN_ALIASES = {"session": "sesion", "sesión": "sesion", "fusion": "merge", "fusión": "merge", "versiones": "version"}


def layer_snapshot(player: str) -> dict:
    if not enabled():
        return {"active": False}
    from .protocol import fragments
    with get_connection() as c:
        run = run_for(c, player)
        count = fragments(c, player)
    if run is None:
        return {"active": False}
    if run["decision"]:
        goal = "Capa 05 completada. Siguiente: Capa 06 · Presentación."
    elif run["committed"]:
        goal = "Decide qué sesión conserva la cuenta: lease s1, lease s0 o expire s0."
    else:
        goal = "Tu cuenta solo admite una sesión. En la consola del andén, fusiona tu estado con el de la Sesión Cero."
    return {
        "active": True, "title": TITLE, "goal": goal, "decision": run["decision"],
        "fragments": count,
        "mail": {"subject": "Dos sesiones, una cuenta", "from": "sesiones@wired",
                 "body": "NODO_07 ha encontrado una sesión caducada con tu nombre. Lee ~/correo/sesion.eml en el Terminal."},
    }


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM layer_five_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "LAYER_FIVE_SESSION", "text": text, "source": player, "learned_minute": minute}
            for text, minute in rows]


def story_for(player: str) -> Story:
    with get_connection() as c:
        return _story(c, player, run_for(c, player))
