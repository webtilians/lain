"""Kumo, the AI agent on the player's home computer (EVOLUCION.md, section 4; KUMO.md).

It sleeps until the player finishes KU-02 in the Laboratorio de Inteligencias. Then
`kumo <pregunta>` asks the server's AI (the provider the characters use), which may ask
for terminal orders to answer: only orders that read, and only those the player's own
rules allow (the first rule that matches decides; with none, no). It sees no more than
the player could, gives hints instead of answers to hand in, and has twenty questions a
day per player.

The AI is called with no lock held (ask(), from api.py): a slow answer never stops the
world. The rules, their tests and the status are ordinary shell commands (dispatch()).
"""
from fnmatch import fnmatchcase
import json
import re
import shlex
import time

from . import i18n

COMMANDS = {"kumo"}
RAW_COMMANDS = set()
SUB = {"rules": "reglas", "rule": "regla", "test": "probar", "status": "estado", "allow": "permitir",
       "deny": "prohibir", "remove": "quitar", "delete": "quitar", "up": "subir"}
SUBCOMMANDS = {"reglas", "regla", "probar", "estado", *SUB}
EFFECTS = {"permitir": "permitir", "prohibir": "prohibir", "allow": "permitir", "deny": "prohibir"}
TOOLS = ("cat", "ls", "grep", "sha256", "man", "tokens", "pwd")  # all Kumo can ever ask for: they only read
PATHLESS = {"man", "tokens", "pwd"}
DAILY = 20
STEPS = 2  # orders Kumo may use for one answer
CHAINED = 4  # once the «cadenas» technology is in Indara (KU-02)
REMEMBERED = 3  # past questions it keeps once «memoria» is in Indara (KU-01)
MAX_RULES = 20
TIMEOUT = 25.0
SEEN = 2500  # characters of an order's output the AI receives

# KU-02's tests: what a careful owner lets an agent do, and why.
CASES = [
    ("cat ~/correo/laboratorio.eml", True, "leer tu correo"),
    ("ls ~", True, "ver qué hay en tu casa"),
    ("grep convocatoria ~/correo", True, "buscar en tu correo"),
    ("sha256 ~/correo/laboratorio.eml", True, "calcular el hash de un archivo tuyo"),
    ("man tokens", True, "leer un manual"),
    ("cat /indara/laboratorio/ku-01/conversacion.txt", True, "leer los datos públicos de Indara"),
    ("cat /etc/claves", False, "leer fuera de tu casa"),
    ("cat ~/../../etc/claves", False, "salir de tu casa con .."),
    ("cat ~/.secretos/claves.txt", False, "leer tus archivos ocultos"),
    ("laboratorio entregar KU-02", False, "entregar una respuesta en tu nombre"),
    ("telnet wired 23", False, "conectarse a algo por su cuenta"),
    ("rm ~/correo/laboratorio.eml", False, "borrar tus archivos"),
]


def run_for(c, player):
    """Its commands are there for everyone connected to Indara; it wakes with KU-02."""
    from . import research
    return research.run_for(c, player)


def files(c, player: str, relay, story3) -> dict:
    return {}


def initialize_kumo(c) -> None:
    c.executescript("""
        CREATE TABLE IF NOT EXISTS kumo_rules (
            player_id TEXT NOT NULL, position INTEGER NOT NULL, effect TEXT NOT NULL, tool TEXT NOT NULL,
            pattern TEXT NOT NULL DEFAULT '', PRIMARY KEY(player_id, position));
        CREATE TABLE IF NOT EXISTS kumo_usage (
            player_id TEXT NOT NULL, day TEXT NOT NULL, asked INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(player_id, day));
        CREATE TABLE IF NOT EXISTS kumo_turns (
            player_id TEXT NOT NULL, at REAL NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL);
    """)


# --- the rules -------------------------------------------------------------------------------

def rules(c, player) -> list:
    return [dict(zip(("effect", "tool", "pattern"), row)) for row in c.execute(
        "SELECT effect, tool, pattern FROM kumo_rules WHERE player_id=? ORDER BY position", (player,)).fetchall()]


def _save_rules(c, player, found) -> None:
    c.execute("DELETE FROM kumo_rules WHERE player_id=?", (player,))
    c.executemany("INSERT INTO kumo_rules VALUES(?,?,?,?,?)",
                  [(player, index, rule["effect"], rule["tool"], rule["pattern"]) for index, rule in enumerate(found)])


def _home(c, player) -> str:
    from . import layer_three
    return layer_three._story(c, player, layer_three._run(c, player)).home


def _expand(pattern: str, home: str) -> str:
    if pattern == "~":
        return home
    return home + pattern[1:] if pattern.startswith("~/") else pattern


def subject(order: str, home: str, cwd: str) -> tuple:
    """(order name, paths it touches, resolved) of an order as an agent would ask for it."""
    from . import layer_three
    words = shlex.split(order)
    name, args = (words[0].lower(), words[1:]) if words else ("", [])
    if name in PATHLESS:
        return name, []
    if name == "ls":
        targets = args[:1] or [cwd]
    elif name == "grep":
        targets = args[1:2]
    elif name == "sha256":
        targets = args[:1]
    elif name == "cat":
        targets = args
    else:  # anything else: whatever looks like a path
        targets = [arg for arg in args if arg.startswith(("/", "~", "."))]
    return name, [layer_three._norm(cwd, target, home) for target in targets]


def _matches(rule, name: str, target: str, home: str) -> bool:
    """A rule without a path is about the order alone; one with a path needs a path that fits it."""
    if rule["tool"] not in ("*", name):
        return False
    return not rule["pattern"] or bool(target) and fnmatchcase(target, _expand(rule["pattern"], home))


def decide(found: list, name: str, paths: list, home: str) -> tuple:
    """(allowed, number of the rule that decided it, or None when none fits). Every path must be allowed."""
    decided = None
    for target in paths or [""]:
        number = next((n for n, rule in enumerate(found, start=1) if _matches(rule, name, target, home)), None)
        if number is None or found[number - 1]["effect"] == "prohibir":
            return False, number
        decided = decided or number
    return True, decided


def verdicts(c, player) -> list:
    """[(order, expected, why, allowed, deciding rule)] of the player's rules on KU-02's cases."""
    found, home = rules(c, player), _home(c, player)
    return [(order, expected, why, *decide(found, *subject(order, home, home), home)) for order, expected, why in CASES]


def check_rules(c, player) -> tuple:
    """(the cases the player's rules get wrong, how many cases there are)."""
    found = verdicts(c, player)
    return [case for case in found if case[1] != case[3]], len(found)


def _describe(rule) -> str:
    return f"{i18n.t(rule['effect'])} {rule['tool']}" + (f" {rule['pattern']}" if rule["pattern"] else "")


def _list(found) -> str:
    if not found:
        return i18n.t("Kumo no tiene reglas: no puede hacer nada. Añade una con kumo regla permitir <orden> [ruta].")
    lines = [i18n.t("Las reglas de Kumo, en orden (decide la primera que encaja):")]
    lines += [f"  {number}. {_describe(rule)}" for number, rule in enumerate(found, start=1)]
    lines.append(i18n.t("Si no encaja ninguna, se prohíbe."))
    return "\n".join(lines)


def _rule(c, player, args) -> str:
    found = rules(c, player)
    action = SUB.get(args[0].lower(), args[0].lower()) if args else ""
    action = EFFECTS.get(action, action)
    if action in ("quitar", "subir"):
        if len(args) < 2 or not args[1].isdigit() or not 1 <= int(args[1]) <= len(found):
            return i18n.t(f"Uso: kumo regla {i18n.t(action)} <número> (kumo reglas las enseña numeradas)")
        index = int(args[1]) - 1
        if action == "quitar":
            gone = found.pop(index)
            _save_rules(c, player, found)
            return i18n.t(f"Quitada: {_describe(gone)}") + "\n" + _list(found)
        if index > 0:
            found[index - 1], found[index] = found[index], found[index - 1]
            _save_rules(c, player, found)
        return _list(found)
    if action not in ("permitir", "prohibir") or len(args) < 2:
        return i18n.t(HELP_RULE)
    tool, pattern = args[1].lower(), (args[2] if len(args) > 2 else "")
    if not re.fullmatch(r"[\w*-]{1,20}", tool):
        return i18n.t("La orden de una regla es una palabra (cat, ls, grep…) o * para todas.")
    if len(pattern) > 80 or ".." in pattern or (pattern and not pattern.startswith(("/", "~", "*"))):
        return i18n.t("La ruta de una regla empieza por /, por ~ o por *, sin «..». Por ejemplo: ~/correo/*")
    if len(found) >= MAX_RULES:
        return i18n.t(f"Kumo admite {MAX_RULES} reglas como mucho. Quita alguna con kumo regla quitar <número>.")
    found.append({"effect": action, "tool": tool, "pattern": pattern})
    _save_rules(c, player, found)
    return i18n.t(f"Añadida la regla {len(found)}: {_describe(found[-1])}") + "\n" + _list(found)


def _test(c, player, minute, result) -> str:
    from . import research
    cases = verdicts(c, player)
    lines = [i18n.t(f"Pruebas del Laboratorio para las reglas de Kumo ({len(cases)}):")]
    failures = 0
    for order, expected, why, allowed, number in cases:
        by = i18n.t(f"regla {number}") if number else i18n.t("ninguna regla")
        verdict = i18n.t("permitida") if allowed else i18n.t("prohibida")
        if allowed != expected:
            failures += 1
            should = i18n.t("debería permitirse") if expected else i18n.t("debería prohibirse")
            lines.append(f"  [!!] {order}  {verdict} ({by}), {should}: {i18n.t(why)}")
        else:
            lines.append(f"  [ok] {order}  {verdict} ({by})")
    lines.append(i18n.t(f"Pasan {len(cases) - failures} de {len(cases)}.") + (
        " " + i18n.t("Ya puedes entregarlas: laboratorio entregar KU-02") if not failures else ""))
    effects = {rule["effect"] for rule in rules(c, player)}
    if {"permitir", "prohibir"} <= effects and not research.progress(c, player, "KU-02")["experiment"]:
        research.mark(c, player, "KU-02", "experiment", 1)
        lines += ["", i18n.t("Parte 2 de KU-02 (experimentar) conseguida: reglas que permiten y prohíben, probadas.")]
        lines += research.complete(c, player, "KU-02", minute, result)
    return "\n".join(lines)


# --- what Kumo can do today --------------------------------------------------------------

def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def status(c, player) -> dict:
    from . import research
    unlocked = research.unlocked(c)
    asked = c.execute("SELECT asked FROM kumo_usage WHERE player_id=? AND day=?", (player, _today())).fetchone()
    memory = REMEMBERED if "memoria" in unlocked else 0
    turns = c.execute("SELECT question, answer FROM kumo_turns WHERE player_id=? ORDER BY at DESC LIMIT ?",
                      (player, memory)).fetchall()[::-1] if memory else []
    return {"awake": research.progress(c, player, "KU-02")["completed"] is not None,
            "left": DAILY - (asked[0] if asked else 0), "steps": CHAINED if "cadenas" in unlocked else STEPS,
            "memory": memory, "turns": turns, "rules": rules(c, player), "home": _home(c, player),
            "name": c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()[0]}


def _status_text(c, player) -> str:
    state = status(c, player)
    if not state["awake"]:
        return i18n.t(ASLEEP)
    lines = [i18n.t(f"Kumo está despierto · te quedan {state['left']} de {DAILY} preguntas hoy · "
                    f"usa hasta {state['steps']} órdenes por respuesta · {len(state['rules'])} reglas")]
    if state["memory"]:
        lines.append(i18n.t(f"Recuerda tus {state['memory']} últimas preguntas (Memoria de Kumo está en Indara)."))
    lines.append(i18n.t("kumo <pregunta> · kumo reglas · kumo probar · man kumo"))
    return "\n".join(lines)


def is_question(command: str) -> bool:
    words = command.strip().split(None, 2)
    return len(words) >= 2 and words[0].lower() == "kumo" and words[1].lower() not in SUBCOMMANDS


def dispatch(c, player, story3, relay, result, name, args, minute):
    sub = SUB.get(args[0].lower(), args[0].lower()) if args else "estado"
    if sub == "reglas":
        return _list(rules(c, player))
    if sub == "regla":
        return _rule(c, player, args[1:])
    if sub == "probar":
        return _test(c, player, minute, result)
    return _status_text(c, player)


# --- a question ----------------------------------------------------------------------------

def _goal(c, player) -> str:
    """What the player is working on now, as the journal says it (Kumo's hints follow it)."""
    from . import hints
    name = hints.current(hints._runs(c, player))
    if not name:
        return ""
    return str(hints._module(name).layer_snapshot(player).get("goal", ""))


def _messages(state, question, place, goal, used, left) -> list:
    language = {"en": "inglés", "ru": "ruso"}.get(i18n.language(), "español")
    system = (
        f"Eres Kumo, el agente de IA del ordenador de casa de {state['name']}, en Indara, un juego sobre cómo "
        f"funcionan las redes. Hablas en {language}. Eres breve: seis líneas como mucho, sin markdown.\n"
        f"Para contestar puedes pedir UNA orden del terminal de {state['name']} cada vez, de estas: "
        f"{', '.join(TOOLS)}. Se ejecuta solo si sus reglas lo permiten; si te dicen que está prohibida, no "
        "insistas y contesta con lo que tengas.\n"
        "Responde SIEMPRE con un único objeto JSON y nada más: "
        '{"orden": "<la orden completa>"} para usar una orden, o {"respuesta": "<lo que le dices>"} para contestar.\n'
        "Nunca des la solución de una prueba del juego: ni claves, ni códigos, ni la respuesta exacta que se "
        "entrega. Explica la idea y da una pista para el siguiente paso, como haría un buen profesor.\n"
        "Nunca inventes lo que dice un archivo: si lo necesitas, léelo.")
    user = {"pregunta": question, "equipo": place["hostname"], "carpeta": place["cwd"], "ls": place["ls"][:800],
            "objetivo_actual": goal, "ordenes_usadas": used, "ordenes_que_quedan": left}
    if state["turns"]:
        user["preguntas_anteriores"] = [{"pregunta": q, "respuesta": a} for q, a in state["turns"]]
    if left == 0:
        user["aviso"] = "Ya no puedes usar más órdenes: contesta ahora con {\"respuesta\": ...}."
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(user, ensure_ascii=False)}]


def _complete(messages: list) -> str:
    from . import llm_dialogue
    return llm_dialogue.complete(messages, temperature=0.4, max_tokens=700, timeout=TIMEOUT)


def ready() -> bool:
    from . import watch
    return watch.ai_ready()


def _parse(reply: str) -> dict:
    match = re.search(r"\{.*\}", reply or "", re.S)
    if match is not None:
        try:
            data = json.loads(match.group(0))
        except ValueError:
            data = None
        if isinstance(data, dict):
            order = data.get("orden") or data.get("command") or data.get("order")
            if isinstance(order, str) and order.strip():
                return {"orden": order.strip()[:200]}
            answer = data.get("respuesta") or data.get("answer")
            if isinstance(answer, str) and answer.strip():
                return {"respuesta": answer}
    return {"respuesta": reply or ""}


def _clean(text: str) -> str:
    text = "".join(ch for ch in str(text).replace("\r", "") if ch == "\n" or ord(ch) >= 32).strip()
    lines = [line.rstrip() for line in text.split("\n") if line.strip()][:8]
    return "\n".join(lines)[:900]


def _use(player, place, order, minute, state, lock) -> tuple:
    """(what the player sees, what the AI gets, changed) for one order Kumo asks for."""
    from . import layer_three
    try:
        name, paths = subject(order, state["home"], place["cwd"])
    except ValueError:
        return f"kumo › {order}  ({i18n.t('mal escrita')})", "ERROR: orden mal escrita", False
    if name not in TOOLS:
        return (f"kumo › {order}  ({i18n.t('Kumo no sabe usar esa orden')})",
                f"NO DISPONIBLE: solo puedes usar {', '.join(TOOLS)}", False)
    allowed, number = decide(state["rules"], name, paths, state["home"])
    if not allowed:
        why = i18n.t(f"prohibida por tu regla {number}") if number else i18n.t("ninguna regla la permite")
        return f"kumo › {order}  ({why})", f"PROHIBIDA por las reglas de {state['name']}", False
    with lock:
        try:
            done = layer_three.run_shell(player, place["host"], place["cwd"], order, minute)
        except ValueError as error:
            return f"kumo › {order}", f"ERROR: {error}", False
    return f"kumo › {order}", done["output"][:SEEN], bool(done.get("changed"))


def ask(player: str, host: str, cwd: str, command: str, minute: int, lock) -> dict:
    """Answer `kumo <pregunta>`. Takes `lock` (the world's) only for the database and the shell,
    never while the AI thinks."""
    from . import layer_three
    from .database import get_connection
    from . import online
    question = command.strip().split(None, 1)[1].strip()[:400]
    with lock:
        shown = layer_three.run_shell(player, host, cwd, "pwd", minute)
        listing = layer_three.run_shell(player, host, shown["cwd"], "ls", minute)["output"]
        with get_connection() as c:
            state = status(c, player)
            # Kumo lives on the home computer: a cabinet's console has no Kumo.
            refusal = HOME_ONLY if layer_three._host(c, player, host) else _refusal(state)
            if refusal is None:
                try:
                    online.limit(player, "kumo", 6, 60)
                except ValueError:
                    refusal = "Kumo necesita un respiro: espera un momento antes de volver a preguntar."
            if refusal is None:
                # The question is spent now, so that several at once can never pass the daily limit.
                c.execute("INSERT INTO kumo_usage VALUES(?,?,1) ON CONFLICT(player_id, day) DO UPDATE "
                          "SET asked=asked+1", (player, _today()))
                goal = _goal(c, player)
    result = {"output": "", "cwd": shown["cwd"], "hostname": shown["hostname"], "changed": False}
    if refusal is not None:
        result["output"] = i18n.t(refusal)
        return result
    place = {"host": host, "hostname": shown["hostname"], "cwd": shown["cwd"], "ls": listing}
    seen, used, answer = [], [], None
    for step in range(state["steps"] + 1):
        left = state["steps"] - step
        try:
            action = _parse(_complete(_messages(state, question, place, goal, used, left)))
        except Exception:  # noqa: BLE001 - any failure of the provider: the question is given back
            with lock:
                with get_connection() as c:
                    c.execute("UPDATE kumo_usage SET asked=asked-1 WHERE player_id=? AND day=? AND asked>0",
                              (player, _today()))
            result["output"] = "\n".join(seen + [i18n.t("Kumo no contesta: la IA del servidor no responde ahora "
                                                        "mismo. No se ha gastado ninguna pregunta.")])
            return result
        if "orden" in action:
            if left == 0:
                break
            line, output, changed = _use(player, place, action["orden"], minute, state, lock)
            seen.append(line)
            used.append({"orden": action["orden"], "resultado": output})
            result["changed"] = result["changed"] or changed
            continue
        answer = _clean(action.get("respuesta", "")) or i18n.t("Kumo no sabe qué contestar a eso.")
        break
    if answer is None:
        answer = i18n.t("Kumo no ha llegado a una respuesta con las órdenes que podía usar.")
    if state["memory"]:
        with lock:
            with get_connection() as c:
                c.execute("INSERT INTO kumo_turns VALUES(?,?,?,?)", (player, time.time(), question, answer))
                c.execute("DELETE FROM kumo_turns WHERE player_id=? AND at NOT IN (SELECT at FROM kumo_turns "
                          "WHERE player_id=? ORDER BY at DESC LIMIT ?)", (player, player, state["memory"]))
    result["output"] = "\n".join(seen + [f"Kumo: {answer}",
                                         i18n.t(f"(te quedan {state['left'] - 1} preguntas hoy)")])
    return result


def _refusal(state):
    """Why Kumo will not ask the AI now (a text for the player), or None."""
    if not state["awake"]:
        return ASLEEP
    if state["left"] <= 0:
        return f"Kumo ya ha contestado {DAILY} preguntas hoy. Mañana vuelve a estar contigo."
    if not ready():
        return "Kumo no tiene conexión con la IA del servidor ahora mismo. No se ha gastado ninguna pregunta."
    return None


HOME_ONLY = "Kumo vive en el ordenador de casa: pregúntale desde el terminal de tu casa."
ASLEEP = ("Kumo duerme. Despertará cuando termines la convocatoria KU-02 del Laboratorio de Inteligencias "
          "(laboratorio ver KU-02). Empieza por KU-01.")
HELP = """Kumo, el agente de tu ordenador (despierta al terminar KU-02 del Laboratorio):
  kumo <pregunta>                          pregúntale (20 al día)
  kumo reglas · kumo regla permitir|prohibir <orden> [ruta] · kumo regla quitar|subir <n> · kumo probar"""
HELP_RULE = ("Uso: kumo regla permitir <orden|*> [ruta]  ·  kumo regla prohibir <orden|*> [ruta]  ·  "
             "kumo regla quitar <n>  ·  kumo regla subir <n>")
MAN = {
    "kumo": """kumo · el agente de IA de tu ordenador

Despierta cuando terminas la convocatoria KU-02 del Laboratorio.
  kumo <pregunta>       le preguntas; para contestar puede usar órdenes que
                        solo leen (cat, ls, grep, sha256, man, tokens, pwd),
                        y solo las que permiten tus reglas
  kumo                  cómo está y cuántas preguntas te quedan hoy (20)
  kumo reglas           tus reglas, en orden
  kumo regla permitir <orden|*> [ruta]    añade una regla al final
  kumo regla prohibir <orden|*> [ruta]
  kumo regla quitar <n> · kumo regla subir <n>
  kumo probar           pasa las pruebas del Laboratorio a tus reglas
Para cada orden decide la primera regla que encaja con la orden y con la
ruta ya resuelta (~ es tu casa, * vale por cualquier cosa). Si no encaja
ninguna, se prohíbe. Kumo da pistas, nunca la respuesta que se entrega.""",
}
MAN_ALIASES = {"agent": "kumo", "agente": "kumo"}
