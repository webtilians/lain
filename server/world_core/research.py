"""The Malla's research centres and their calls (convocatorias).

Three centres, each a site of the Malla visited from the terminal: the
Instituto de Física del Puerto (instituto), the Laboratorio de Inteligencias
(laboratorio) and the Archivo de Protocolos (archivo). A call has three parts:
study its articles, do its experiment and demonstrate a result the server
checks. Whoever finishes goes into the centre's registry, and when enough
people have finished, the call's technology enters the Malla for everyone.

Calls come from two places. Some are written by hand (QB-01, the qubit and
BB84, in institute.py). The rest are brought by the watcher (watch.py) from
real headlines: their words are the AI's, in Spanish and English, but their
exercise is always one of the GENERATORS below, filled with each player's own
numbers, so it can always be solved and checked. The owner can delete a
watcher call from the server panel; it then disappears from the game.
"""
from functools import lru_cache
import json
import random
import time

from .database import get_connection
from . import i18n

CENTRES = {
    "instituto": {"title": "Instituto de Física del Puerto", "host": "instituto.malla", "director": "RESIDENT_019",
                  "who": "Dirige: Hideo Sakamoto, profesor de ciencias del colegio.", "prefix": "QB",
                  "commands": ("instituto", "institute"), "en": "institute", "mail": "hideo <hideo@instituto.malla>",
                  "focus": "física: cuántica, fotones, medida, materiales, energía, ordenadores cuánticos"},
    "laboratorio": {"title": "Laboratorio de Inteligencias", "host": "laboratorio.malla", "director": "RESIDENT_025",
                    "who": "Dirige: Takeshi Uno, ayudante del aula de informática.", "prefix": "IA",
                    "commands": ("laboratorio", "laboratory", "lab"), "en": "lab",
                    "mail": "takeshi <takeshi@laboratorio.malla>",
                    "focus": "inteligencia artificial: modelos de lenguaje, agentes, aprendizaje, datos, robótica"},
    "archivo": {"title": "Archivo de Protocolos", "host": "archivo.malla", "director": "RESIDENT_049",
                "who": "Dirige: Yasuo Ueda, coleccionista, desde la librería.", "prefix": "PR",
                "commands": ("archivo", "archive"), "en": "archive", "mail": "yasuo <yasuo@archivo.malla>",
                "focus": "redes y protocolos: internet, cifrado, seguridad, estándares, criptografía poscuántica"},
}
COMMAND_CENTRE = {command: key for key, centre in CENTRES.items() for command in centre["commands"]}
COMMANDS = set(COMMAND_CENTRE)
RAW_COMMANDS = COMMANDS
SUB = {"show": "ver", "read": "leer", "submit": "entregar", "registry": "registro", "register": "registro"}
NORA = "AGENT_NORA"
THRESHOLD = 3
LISTED = 6  # newest calls a centre's front page lists; older ones stay open with «ver»


def enabled() -> bool:
    from . import layer_three
    return layer_three.enabled()


def _exists(c, table="research_progress") -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone() is not None


def initialize_research() -> None:
    if not enabled():
        return
    _tables()
    from .institute import initialize_institute
    initialize_institute()


def _tables() -> None:
    """The tables, also for the watcher and the panel, which work even where the game has no layers."""
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS research_calls (
                id TEXT PRIMARY KEY, centre TEXT NOT NULL, data TEXT NOT NULL, created_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'open', deleted_at REAL);
            CREATE TABLE IF NOT EXISTS research_progress (
                player_id TEXT NOT NULL, call_id TEXT NOT NULL, read TEXT NOT NULL DEFAULT '',
                experiment INTEGER NOT NULL DEFAULT 0, demo INTEGER NOT NULL DEFAULT 0,
                completed_minute INTEGER, completed_at REAL, PRIMARY KEY(player_id, call_id));
            CREATE TABLE IF NOT EXISTS research_unlocks (
                tech TEXT PRIMARY KEY, call_id TEXT NOT NULL, minute INTEGER NOT NULL, unlocked_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS research_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, call_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id, call_id));
        """)


def run_for(c, player):
    """Open to every player already connected to the Malla (Capa 03 started)."""
    if not enabled() or not _exists(c):
        return None
    if c.execute("SELECT 1 FROM layer_three WHERE player_id=?", (player,)).fetchone() is None:
        return None
    done = c.execute("SELECT COUNT(*) FROM research_progress WHERE player_id=? AND completed_minute IS NOT NULL",
                     (player,)).fetchone()[0]
    return {"completed": done > 0, "decision": "RESEARCHED" if done else None}


# --- calls ------------------------------------------------------------------------

def say(value) -> str:
    """A text in the player's language: watcher texts carry both, hand-written ones go through the catalogue."""
    if isinstance(value, dict):
        return value.get(i18n.language()) or value.get("es", "")
    return i18n.t(value)


def command(centre: str) -> str:
    """The centre's command as the player would type it in their language."""
    return CENTRES[centre]["en"] if i18n.language() == "en" else CENTRES[centre]["commands"][0]


def calls(c, every=False) -> dict:
    """Every open call, hand-written first, then the watcher's, oldest first (every=True adds deleted ones)."""
    from .institute import CALLS
    found = {call_id: dict(call, id=call_id, generated=False) for call_id, call in CALLS.items()}
    if _exists(c, "research_calls"):
        for call_id, data, created, status in c.execute(
                "SELECT id, data, created_at, status FROM research_calls ORDER BY created_at, id").fetchall():
            if status == "open" or every:
                found[call_id] = dict(json.loads(data), id=call_id, created=created, status=status, generated=True)
    return found


def articles(call) -> list:
    return list(call["articles"]) if not call["generated"] else [call["id"].lower()]


def tech(call) -> dict:
    """What the call brings to the Malla: title, two lines for everyone and what the residents remember."""
    if not call["generated"]:
        from .institute import TECHS
        return dict(TECHS[call["unlock"]], id=call["unlock"])
    return {"id": call["id"].lower(), "title": call["tech"], "text": call["tech_text"], "line": call["tech_line"],
            "memory": f"{call['tech']} ya está en la Malla, gracias a la convocatoria {call['id']} del "
                      f"{CENTRES[call['centre']]['title']}: {call['tech_text']['es']}"}


def _name(c, player):
    row = c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()
    return row[0] if row else player


def progress(c, player, call_id) -> dict:
    row = c.execute("SELECT read, experiment, demo, completed_minute FROM research_progress "
                    "WHERE player_id=? AND call_id=?", (player, call_id)).fetchone()
    if row is None:
        return {"read": set(), "experiment": False, "demo": False, "completed": None}
    return {"read": set(filter(None, row[0].split(","))), "experiment": bool(row[1]), "demo": bool(row[2]),
            "completed": row[3]}


def mark(c, player, call_id, field, value) -> None:
    c.execute("INSERT OR IGNORE INTO research_progress(player_id, call_id) VALUES(?,?)", (player, call_id))
    c.execute(f"UPDATE research_progress SET {field}=? WHERE player_id=? AND call_id=?", (value, player, call_id))


def studied(call, state) -> bool:
    return set(articles(call)) <= state["read"]


def finished(c, call_id) -> list:
    return c.execute("SELECT player_id, completed_minute FROM research_progress WHERE call_id=? "
                     "AND completed_minute IS NOT NULL ORDER BY completed_at, completed_minute", (call_id,)).fetchall()


def unlocked(c) -> dict:
    """Technologies already in the Malla: {tech id: (call id, minute)}, only from calls that still exist."""
    if not _exists(c, "research_unlocks"):
        return {}
    known = calls(c)
    return {tech_id: (call_id, minute) for tech_id, call_id, minute in c.execute(
        "SELECT tech, call_id, minute FROM research_unlocks ORDER BY unlocked_at").fetchall() if call_id in known}


def complete(c, player, call_id, minute, result) -> list:
    """Close the call for this player once its three parts are done; the last one in may change the Malla."""
    call, state = calls(c)[call_id], progress(c, player, call_id)
    if state["completed"] is not None or not (studied(call, state) and state["experiment"] and state["demo"]):
        return []
    centre = CENTRES[call["centre"]]
    c.execute("UPDATE research_progress SET completed_minute=?, completed_at=? WHERE player_id=? AND call_id=?",
              (minute, time.time(), player, call_id))
    memory = call["memory"] if not call["generated"] else \
        f"Terminó la convocatoria {call_id} del {centre['title']}: {call['title']['es']}. {call['memory']}"
    c.execute("INSERT OR REPLACE INTO research_knowledge VALUES(?,?,?,?,?)",
              (player, centre["director"], call_id, memory, minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'RESEARCH_COMPLETED',?,?)",
              (minute, player, call_id, centre["host"]))
    result["changed"] = True
    lines = ["", i18n.t(f"CONVOCATORIA {call_id} COMPLETADA · {centre['title']}"),
             i18n.t(f"Tu nombre entra en el registro del centro: {command(call['centre'])} registro.")]
    brought, done = tech(call), len(finished(c, call_id))
    if brought["id"] in unlocked(c):
        return lines
    title = say(brought["title"])
    if done < call["threshold"]:
        return lines + [i18n.t(f"Van {done} de {call['threshold']}. Cuando lleguen a {call['threshold']}, "
                               f"{title} entrará en la Malla para todos.")]
    c.execute("INSERT OR REPLACE INTO research_unlocks VALUES(?,?,?,?)", (brought["id"], call_id, minute, time.time()))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'MALLA_EVOLVES',?,?)",
              (minute, player, brought["id"], call_id))
    return lines + ["", i18n.t(f"LA MALLA APRENDE · {title} entra en la Malla para todos."),
                    say(brought["text"]), say(brought["line"])]


# --- what a centre shows ------------------------------------------------------------

def _checks(call, state) -> list:
    return ["[x]" if done else "[ ]" for done in (studied(call, state), state["experiment"], state["demo"])]


def _count(c, call) -> str:
    done, brought = len(finished(c, call["id"])), tech(call)
    if brought["id"] in unlocked(c):
        return i18n.t(f"han terminado {done} · {say(brought['title'])} ya está en la Malla")
    return i18n.t(f"han terminado {done}/{call['threshold']}")


def _mine(c, centre) -> list:
    return [call for call in calls(c).values() if call["centre"] == centre]


def _portal(c, player, centre) -> str:
    info, cmd = CENTRES[centre], command(centre)
    lines = [f"{i18n.t(info['title']).upper()} · {info['host']}", i18n.t(info["who"]), ""]
    listed = _mine(c, centre)[::-1][:LISTED][::-1]
    if not listed:
        lines.append(i18n.t("Sin convocatorias abiertas. El vigía del centro busca la próxima en la actualidad."))
    else:
        lines.append(i18n.t("Convocatorias abiertas:"))
    for call in listed:
        state = progress(c, player, call["id"])
        study, experiment, demo = _checks(call, state)
        status = i18n.t("terminada") if state["completed"] is not None else \
            i18n.t(f"estudiar {study} · experimentar {experiment} · demostrar {demo}")
        lines.append(f"  {call['id']}  {say(call['title'])}")
        lines.append(f"         {status} · {_count(c, call)}")
    known = _known(c)
    lines.append("")
    if known:
        lines.append(i18n.t("Lo que ya sabe la Malla:") + " " +
                     ", ".join(i18n.t(f"{say(brought['title'])} (desde el minuto {minute})") for brought, minute in known))
    else:
        lines.append(i18n.t("Lo que ya sabe la Malla: nada nuevo todavía."))
    lines.append(i18n.t(f"{cmd} ver <código> · {cmd} leer <artículo> · {cmd} registro · man {cmd}"))
    return "\n".join(lines)


def _known(c) -> list:
    every = calls(c)
    return [(tech(every[call_id]), minute) for _tech, (call_id, minute) in unlocked(c).items()]


def call_id(text: str) -> str:
    """A call's code as written: «qb01», «ia-1» and «PR-01» are all fine."""
    code = text.upper()
    for prefix in [info["prefix"] for info in CENTRES.values()]:
        if code.startswith(prefix):
            number = code[len(prefix):].lstrip("-")
            return f"{prefix}-{int(number):02d}" if number.isdigit() else code
    return code


def _find(c, text, centre):
    found = calls(c).get(call_id(text))
    return found if found is not None and found["centre"] == centre else None


def _show(c, player, centre, args) -> str:
    mine = _mine(c, centre)
    call = _find(c, args[0], centre) if args else (mine[-1] if mine else None)
    if call is None:
        return i18n.t(f"No hay ninguna convocatoria con ese código en este centro. {command(centre)} enseña las abiertas.")
    state, info, cmd = progress(c, player, call["id"]), CENTRES[centre], command(centre)
    study, experiment, demo = _checks(call, state)
    reading = " · ".join(i18n.t(f"{cmd} leer {slug}") for slug in articles(call))
    lines = [f"{call['id']} · {say(call['title'])}",
             i18n.t(f"{info['title']} · umbral: {call['threshold']} personas · trae a la Malla: "
                    f"{say(tech(call)['title'])}"), "", say(call["summary"])]
    if call["generated"]:
        lines.append(i18n.t(f"Fuente: {call['source']['name']} · {call['source']['title']}"))
        statements = [say(call["framing"]) + " " + exercise(c, player, call, "practica")["statement"],
                      exercise(c, player, call, "prueba")["statement"]]
        submit = i18n.t(f"Se entrega con {cmd} entregar {call['id']} <respuesta>.")
    else:
        statements, submit = [i18n.t(call["experiment"]), i18n.t(call["demo"])], ""
    lines += ["", f"1. {i18n.t('Estudiar')} {study}  {reading}",
              f"2. {i18n.t('Experimentar')} {experiment}  {statements[0]}",
              f"3. {i18n.t('Demostrar')} {demo}  {statements[1]}"]
    lines += [submit] if submit else []
    lines.append("")
    if state["completed"] is not None:
        lines.append(i18n.t(f"La terminaste en el minuto {state['completed']}. Estás en el registro."))
    count = _count(c, call)
    lines.append(count[:1].upper() + count[1:] + ".")
    return "\n".join(lines)


def article(c, slug):
    """(call, text) of an article by its name, or (None, None)."""
    from .institute import ARTICLES
    slug = _slug(slug)
    every = calls(c)
    if call_id(slug) in every:
        slug = call_id(slug).lower()
    for call in every.values():
        if slug in articles(call):
            if not call["generated"]:
                return call, i18n.t(ARTICLES[slug])
            source = call["source"]
            return call, "\n".join([say(call["article"]), "", i18n.t(f"Fuente: {source['name']} · {source['title']}"),
                                    source["url"]])
    return None, None


def _read(c, player, centre, args, minute, result) -> str:
    call, text = article(c, args[0].lower()) if args else (None, None)
    if call is None or call["centre"] != centre:
        names = [slug for call in _mine(c, centre) for slug in articles(call)]
        return "\n".join([i18n.t("Artículos de este centro:") + " " + (", ".join(names) or "-"),
                          i18n.t(f"Para leer uno: {command(centre)} leer <artículo>")])
    slug = _slug(args[0].lower())
    if slug not in articles(call):
        slug = call_id(slug).lower()
    extra = []
    state = progress(c, player, call["id"])
    if slug not in state["read"]:
        mark(c, player, call["id"], "read", ",".join(sorted(state["read"] | {slug})))
        if studied(call, progress(c, player, call["id"])):
            extra.append(i18n.t(f"Parte 1 de {call['id']} (estudiar) conseguida."))
        extra += complete(c, player, call["id"], minute, result)
    return "\n".join([text] + ([""] + extra if extra else []))


def _slug(slug: str) -> str:
    from .institute import ARTICLE_ALIASES
    return ARTICLE_ALIASES.get(slug, slug)


def _registry(c, centre) -> str:
    lines = [i18n.t(f"Registro del {CENTRES[centre]['title']}")]
    mine = _mine(c, centre)
    if not mine:
        lines.append("  " + i18n.t("(nadie la ha terminado todavía)"))
    for call in mine:
        rows = finished(c, call["id"])
        lines.append(f"{call['id']} · {say(call['title'])}")
        if not rows:
            lines.append("  " + i18n.t("(nadie la ha terminado todavía)"))
        for number, (player, minute) in enumerate(rows, start=1):
            lines.append(f"  {number}. {_name(c, player)} · {i18n.t('minuto')} {minute}")
    every = calls(c)
    for _tech, (call_key, minute) in unlocked(c).items():
        if every[call_key]["centre"] == centre:
            lines.append(i18n.t(f"{say(tech(every[call_key])['title'])} entró en la Malla en el minuto {minute}."))
    return "\n".join(lines)


def _submit(c, player, centre, args, minute, result) -> str:
    mine = _mine(c, centre)
    call = _find(c, args[0], centre) if args else None
    if call is not None:
        args = args[1:]
    elif centre == "instituto" and args and args[0].lower() in ("a", "b"):
        call = calls(c)["QB-01"]  # «instituto entregar a 0110…»: a BB84 channel and its key
    else:
        pending = [item for item in mine if progress(c, player, item["id"])["completed"] is None]
        call = (pending or mine or [None])[-1]
    if call is None:
        return i18n.t("Este centro no tiene convocatorias abiertas.")
    if not call["generated"]:
        from .institute import submit
        return submit(c, player, args, minute, result)
    cmd, state = command(centre), progress(c, player, call["id"])
    if not args:
        return i18n.t(f"Uso: {cmd} entregar {call['id']} <respuesta>")
    if state["demo"]:
        return i18n.t(f"Ya entregaste {call['id']}. Está en tu registro.")
    part = "prueba" if state["experiment"] else "practica"
    answer = "".join(args).strip().lower()
    if answer != exercise(c, player, call, part)["answer"]:
        return i18n.t("No es eso. Vuelve a leer el enunciado con calma:") + " " + exercise(c, player, call, part)["statement"]
    if part == "practica":
        mark(c, player, call["id"], "experiment", 1)
        return "\n".join([i18n.t(f"Parte 2 de {call['id']} (experimentar) conseguida."),
                          i18n.t("Ahora con tus propios datos:") + " " + exercise(c, player, call, "prueba")["statement"]]
                         + complete(c, player, call["id"], minute, result))
    mark(c, player, call["id"], "demo", 1)
    lines = [i18n.t(f"Parte 3 de {call['id']} (demostrar) conseguida.")]
    if not studied(call, progress(c, player, call["id"])):
        lines.append(i18n.t(f"Para terminar la convocatoria te falta estudiar: {cmd} leer {articles(call)[0]}"))
    return "\n".join(lines + complete(c, player, call["id"], minute, result))


def dispatch(c, player, story3, relay, result, name, args, minute):
    centre = COMMAND_CENTRE[name]
    sub = SUB.get(args[0].lower(), args[0].lower()) if args else ""
    rest = args[1:]
    if not sub:
        return _portal(c, player, centre)
    if sub == "ver":
        return _show(c, player, centre, rest)
    if sub == "leer":
        return _read(c, player, centre, rest, minute, result)
    if sub == "registro":
        return _registry(c, centre)
    if sub == "entregar":
        return _submit(c, player, centre, rest, minute, result)
    return i18n.t(HELP)


def files(c, player: str, relay, story3) -> dict:
    """Each watcher call's data files, under /malla/<centre>/<code>/, at home and at every cabinet;
    at home, also the director's mail announcing it."""
    if run_for(c, player) is None:
        return {}
    found = {}
    for call in calls(c).values():
        if not call["generated"]:
            continue
        for part in ("practica", "prueba"):
            found.update(exercise(c, player, call, part)["files"])
        if relay is None:
            centre = CENTRES[call["centre"]]
            found[f"{story3.home}/correo/{call['id'].lower()}.eml"] = "\n".join([
                i18n.t(f"De: {centre['mail']}"), i18n.t(f"Asunto: convocatoria {call['id']}"), "",
                say(call["title"]), say(call["summary"]), "",
                i18n.t(f"Empieza con {command(call['centre'])} ver {call['id']}.")])
    return found


# --- exercises: the AI chooses one, the code fills and checks it -----------------------

PRIMES = [101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193, 197, 199]


class Xor:
    ABOUT = "XOR bit a bit de dos bytes: cifrados de flujo, códigos, paridad, mezclas de claves"

    @staticmethod
    def make(rng, path):
        a, b = rng.randrange(256), rng.randrange(256)
        return (i18n.t(f"Calcula a XOR b bit a bit (1 donde son distintos, 0 donde son iguales): a = {a:08b}, "
                       f"b = {b:08b}. Entrega los 8 bits."), f"{a ^ b:08b}", {})


class Powmod:
    ABOUT = "potencia modular g^x mod p: criptografía de clave pública, Diffie-Hellman, firmas digitales"

    @staticmethod
    def make(rng, path):
        p, g, x = rng.choice(PRIMES), rng.randrange(2, 10), rng.randrange(20, 300)
        return (i18n.t(f"Calcula {g}^{x} mod {p}: el resto de dividir {g} elevado a {x} entre {p} (man powmod). "
                       "Entrega el número."), str(pow(g, x, p)), {})


class Hamming:
    ABOUT = ("encontrar el bit erróneo de un bloque Hamming(7,4): corrección de errores en redes, memorias, "
             "discos y ordenadores cuánticos")

    @staticmethod
    def make(rng, path):
        d = [rng.randrange(2) for _ in range(4)]
        word = [d[0] ^ d[1] ^ d[3], d[0] ^ d[2] ^ d[3], d[0], d[1] ^ d[2] ^ d[3], d[1], d[2], d[3]]
        wrong = rng.randrange(1, 8)
        word[wrong - 1] ^= 1
        bits = "".join(map(str, word))
        return (i18n.t(f"Este bloque Hamming(7,4) llegó con un bit cambiado: {bits}. Comprueba las tres paridades: "
                       "la 1 cubre las posiciones 1, 3, 5 y 7; la 2, las 2, 3, 6 y 7; la 4, las 4, 5, 6 y 7. Cada "
                       "grupo debería tener un número par de unos. Suma los números de las que fallan: es la posición "
                       "del bit erróneo. Entrega esa posición."), str(wrong), {})


WORDS = ["torre-norte", "puente-sur", "nodo-rio", "cable-viejo", "galeria-7", "tunel-este", "azotea-3", "faro-oeste"]


class Fingerprint:
    ABOUT = "huella sha256 de un dato: integridad, firmas, cadenas de bloques, verificación de descargas"

    @staticmethod
    def make(rng, path):
        lines = [f"lote {index:02d} · {rng.choice(WORDS)} · {rng.randrange(16 ** 4):04x} · {rng.randrange(1000)} ms"
                 for index in range(1, 13)]
        number = rng.randrange(1, len(lines) + 1)
        from .layer_three import h8
        return (i18n.t(f"En {path} hay {len(lines)} líneas. Saca la huella de la línea {number} con "
                       f"sha256 {path} {number} y entrega sus 8 caracteres."),
                h8(lines[number - 1]), {path: "\n".join(lines)})


class Count:
    ABOUT = "contar en un registro con grep: análisis de tráfico, detección de intrusos, auditoría de sistemas"
    MARKS = ["KAGAMI", "NOEMA", "REINTENTO", "PERDIDO", "TIMEOUT"]

    @staticmethod
    def make(rng, path):
        mark_word = rng.choice(Count.MARKS)
        others = [word for word in Count.MARKS if word != mark_word]
        lines, hits = [], 0
        for index in range(1, 31):
            tag = mark_word if rng.random() < 0.3 else rng.choice(others + ["OK", "OK", "OK"])
            hits += tag == mark_word
            lines.append(f"{index:02d} {rng.choice(WORDS):<12} {tag:<9} {rng.randrange(1, 900)} ms")
        return (i18n.t(f"¿Cuántas líneas de {path} dicen {mark_word}? Cuéntalas con grep {mark_word} {path}. "
                       "Entrega el número."), str(hits), {path: "\n".join(lines)})


GENERATORS = {"xor": Xor, "powmod": Powmod, "hamming": Hamming, "huella": Fingerprint, "contar": Count}


def exercise(c, player, call, part) -> dict:
    """The player's own instance of a watcher call's exercise: statement, expected answer and data files."""
    return _exercise(call["id"], call["centre"], call["kind"], player, part, i18n.language())


@lru_cache(maxsize=4096)
def _exercise(code, centre, kind, player, part, _language) -> dict:
    # Every shell command lists its files, so each call's data is built once per player and language.
    rng = random.Random(f"{code}:{player}:{part}")
    path = f"/malla/{centre}/{code.lower()}/{part}.txt"
    statement, answer, data = GENERATORS[kind].make(rng, path)
    return {"statement": statement, "answer": answer, "files": data}


# --- the watcher's side ----------------------------------------------------------------

def centre_focus(key: str) -> str:
    return f"{CENTRES[key]['title']}: {CENTRES[key]['focus']}"


def studied_topics() -> list:
    with get_connection() as c:
        return [f"{call['id']}: {say_es(call['title'])}" for call in calls(c, every=True).values()]


def say_es(value) -> str:
    return value.get("es", "") if isinstance(value, dict) else str(value)


def open_counts() -> dict:
    """How many calls each centre has open (hand-written ones included)."""
    _tables()
    with get_connection() as c:
        counts = {key: 0 for key in CENTRES}
        for call in calls(c).values():
            counts[call["centre"]] += 1
    return counts


def recent_kinds(count: int = 2) -> list:
    """The exercise types of the watcher's latest calls, so the next one can be different."""
    _tables()
    with get_connection() as c:
        return [call["kind"] for call in list(calls(c, every=True).values())[::-1] if call["generated"]][:count]


def last_generated() -> float | None:
    _tables()
    with get_connection() as c:
        row = c.execute("SELECT MAX(created_at) FROM research_calls").fetchone()
    return row[0] if row and row[0] is not None else None


def publish(proposal: dict) -> dict:
    """Store a watcher call under the next free code of its centre; it is open to everyone at once."""
    _tables()
    centre = proposal["centre"]
    prefix = CENTRES[centre]["prefix"]
    with get_connection() as c:
        taken = set(calls(c, every=True))
        number = 1
        while f"{prefix}-{number:02d}" in taken:
            number += 1
        code = f"{prefix}-{number:02d}"
        data = dict(proposal, threshold=THRESHOLD)
        c.execute("INSERT INTO research_calls(id, centre, data, created_at) VALUES(?,?,?,?)",
                  (code, centre, json.dumps(data, ensure_ascii=False), time.time()))
    return dict(data, id=code)


def delete(code: str) -> bool:
    """The owner's delete: the call leaves the game; finished players keep nothing visible of it."""
    _tables()
    with get_connection() as c:
        changed = c.execute("UPDATE research_calls SET status='deleted', deleted_at=? WHERE id=? AND status='open'",
                            (time.time(), code)).rowcount
    return bool(changed)


def panel() -> list:
    """Every watcher call for the owner's panel (also deleted ones), newest first."""
    _tables()
    with get_connection() as c:
        rows = []
        for call in list(calls(c, every=True).values())[::-1]:
            if not call["generated"]:
                continue
            rows.append({"id": call["id"], "centre": CENTRES[call["centre"]]["title"], "title": call["title"]["es"],
                         "kind": call["kind"], "tech": call["tech"], "status": call["status"],
                         "created": call["created"], "finished": len(finished(c, call["id"])),
                         "threshold": call["threshold"], "source": call["source"]})
    return rows


# --- what the world sees ------------------------------------------------------------------

def layer_actor_context(actor: str, player: str) -> list:
    directors = {info["director"] for info in CENTRES.values()}
    if actor not in directors and actor != NORA:
        return []
    with get_connection() as c:
        if not _exists(c):
            return []
        known = calls(c)
        rows = c.execute("SELECT call_id, text, minute FROM research_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
        brought = _known(c)
    memories = [{"id": f"RESEARCH_{call_id}", "text": text, "source": player, "learned_minute": minute}
                for call_id, text, minute in rows if call_id in known]
    return memories + [{"id": f"MALLA_{item['id'].upper()}", "text": item["memory"], "source": "MALLA",
                        "learned_minute": minute} for item, minute in brought]


def research_snapshot(player: str) -> dict:
    if not enabled():
        return {"active": False}
    with get_connection() as c:
        if run_for(c, player) is None:
            return {"active": False}
        every = calls(c)
        completed = [call for call in every.values() if progress(c, player, call["id"])["completed"] is not None]
        brought = _known(c)
    # Already in the player's language, under keys the response translator leaves alone.
    return {
        "active": True,
        "completed": [{"id": call["id"], "name": say(call["title"]), "centre": i18n.t(CENTRES[call["centre"]]["title"])}
                      for call in completed],
        "unlocked": [{"id": item["id"], "name": say(item["title"]), "about": say(item["text"]),
                      "next": say(item["line"])} for item, _minute in brought],
    }


HELP = """Centros de investigación de la Malla:
  instituto · laboratorio · archivo        convocatorias abiertas de cada centro
  <centro> ver <código> · <centro> leer <artículo> · <centro> entregar <código> <respuesta> · <centro> registro"""

MAN = {
    "instituto": """instituto · laboratorio · archivo · los centros de investigación de la Malla

  instituto      Instituto de Física del Puerto (instituto.malla)
  laboratorio    Laboratorio de Inteligencias (laboratorio.malla)
  archivo        Archivo de Protocolos (archivo.malla)

  <centro>                       convocatorias abiertas y lo que ya sabe la Malla
  <centro> ver <código>          una convocatoria: sus tres partes y cómo vas
  <centro> leer <artículo>       los artículos para estudiar
  <centro> entregar ...          entrega el resultado de una convocatoria
  <centro> registro              quién ha terminado cada convocatoria
Cada convocatoria tiene tres partes: estudiar, experimentar y demostrar.
Cuando la terminan bastantes personas, su tecnología entra en la Malla para
todos. El vigía de cada centro trae convocatorias nuevas cada pocos días, a
partir de noticias reales.""",
}
MAN_ALIASES = {"institute": "instituto", "instituto.malla": "instituto", "laboratorio": "instituto",
               "lab": "instituto", "laboratory": "instituto", "archivo": "instituto", "archive": "instituto",
               "centros": "instituto", "convocatoria": "instituto", "convocatorias": "instituto"}
