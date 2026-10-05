"""The Instituto de Física del Puerto: the Malla's first research centre.

A call (convocatoria) is a small study unit with three parts: read its articles,
do its experiment and demonstrate a result the server can check. Whoever
finishes goes into the institute's registry, and when enough people have
finished a call its technology enters the Malla for everyone.

The first call, QB-01, is the qubit and BB84: a one-qubit simulator (`qubit`)
and a key shared with Hideo over two channels, one of them tapped (`bb84`).
Three researchers bring `qkd` to every terminal.
"""
import datetime
import hashlib
import random
import time

from .database import get_connection
from . import i18n

TITLE = "Instituto de Física del Puerto"
HOST = "instituto.malla"
HIDEO = "RESIDENT_019"
NORA = "AGENT_NORA"
COMMANDS = {"instituto", "institute", "qubit", "bb84", "qkd"}
RAW_COMMANDS = COMMANDS
PHOTONS = 24
CHANNELS = ("a", "b")
SUB = {"show": "ver", "read": "leer", "submit": "entregar", "registry": "registro", "register": "registro"}
QUBIT_SUB = {"new": "nuevo", "measure": "medir", "state": "estado"}
BB84_SUB = {"measure": "medir", "compare": "comparar"}

CALLS = {
    "QB-01": {
        "title": "El qubit y la clave que delata al espía",
        "summary": "Un qubit no se puede leer sin cambiarlo. Con eso, dos personas pueden repartirse una clave\n"
                   "y saber si alguien la ha escuchado. Hideo busca a quien lo entienda midiendo.",
        "articles": ("qubit", "bb84"),
        "experiment": "Prepara un qubit que, medido en la base X, dé 1 con total certeza, y mídelo (qubit).",
        "demo": "Saca una clave con Hideo por BB84 y entrégala con instituto entregar <canal> <clave>. "
                "Uno de los dos canales está pinchado (bb84).",
        "threshold": 3,
        "unlock": "qkd",
        "memory": "Terminó la convocatoria QB-01 del Instituto: sacó una clave con BB84 y descubrió qué canal "
                  "estaba pinchado. Entiende que medir un qubit lo cambia.",
    },
}
TECHS = {
    "qkd": {"title": "QKD", "text": "La Malla reparte claves con fotones: si alguien escucha, se nota.",
            "line": "Desde hoy, cualquiera puede usar qkd en el terminal.",
            "memory": "QKD ya está en la Malla: los armarios reparten sus claves con fotones y, si alguien "
                      "escucha, la tasa de error lo delata. Salió de la convocatoria QB-01 del Instituto."},
}

ARTICLES = {
    "qubit": """El qubit · Instituto de Física del Puerto · H. Sakamoto

Un bit vale 0 o 1. Un qubit puede estar en una mezcla de los dos, una
superposición, hasta que lo mides. Al medirlo da 0 o 1, y se queda así:
medir lo cambia.

Siempre se mide en una base. En la base Z (la recta, +) los estados seguros
son |0> y |1>. En la base X (la diagonal, x) son |+> y |->, que vistos desde
la base Z son mitad y mitad:
  |+> = (|0> + |1>)/√2        |-> = (|0> - |1>)/√2
Si mides |+> en la base X, sale + siempre. Si lo mides en la base Z, sale
0 o 1 al 50 %, y el |+> se pierde. En la base X, + cuenta como 0 y - como 1.

Las puertas cambian el estado sin medirlo:
  X   cambia |0> por |1> y |1> por |0> (un NOT)
  Z   cambia el signo de |1>: convierte |+> en |-> y |-> en |+>
  H   (Hadamard) pasa de una base a la otra: |0> a |+>, |1> a |->

El simulador del Instituto es la orden qubit (man qubit).""",
    "bb84": """BB84 · repartir una clave con fotones · H. Sakamoto

Bennett y Brassard, 1984. Alicia manda fotones, uno a uno. Cada fotón lleva
un bit en una base elegida al azar: recta (+) o diagonal (x). Bob mide cada
uno en una base que también elige al azar.
- Si las bases coinciden, Bob lee el bit de Alicia.
- Si no, le sale 0 o 1 al azar.
Luego hablan en público, pero solo de las bases, nunca de los bits, y se
quedan con las posiciones donde coincidieron.

El espía: quien quiera leer los fotones por el camino tiene que medirlos, y
no sabe la base. La mitad de las veces se equivoca, y el fotón que reenvía ya
va en su base, no en la de Alicia. En las posiciones que Alicia y Bob se
quedan aparecen errores: en torno a uno de cada cuatro bits.

Por eso sacrifican una parte: comparan en público una muestra de sus bits.
Si no coinciden, alguien escuchaba y esa clave se tira. Si coinciden, lo que
no han dicho en voz alta es su clave. Un cable real tiene algo de ruido; por
encima del 11 % de errores, ya no es ruido.

En el Instituto, Hideo hace de Alicia y tú de Bob: bb84 (man bb84).""",
}
ARTICLE_ALIASES = {"bb-84": "bb84", "qbit": "qubit", "cubit": "qubit"}

MAIL = ("De: hideo <hideo@instituto.malla>\nAsunto: convocatoria QB-01\n\n"
        "Doy ciencias en el colegio y, en mis ratos libres, llevo el Instituto de Física del Puerto, en la Malla.\n"
        "Tenemos una convocatoria abierta: el qubit y la clave que delata al espía.\n"
        "Si tres personas la terminan, la Malla aprenderá a repartir claves con fotones.\n"
        "Empieza por la orden instituto. Y no te creas nada que no puedas medir.")


def enabled() -> bool:
    from . import layer_three
    return layer_three.enabled()


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='institute_progress'").fetchone() is not None


def initialize_institute() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS institute_progress (
                player_id TEXT NOT NULL, call_id TEXT NOT NULL, read TEXT NOT NULL DEFAULT '',
                experiment INTEGER NOT NULL DEFAULT 0, demo INTEGER NOT NULL DEFAULT 0,
                completed_minute INTEGER, completed_at INTEGER, PRIMARY KEY(player_id, call_id));
            CREATE TABLE IF NOT EXISTS institute_qubit (player_id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS institute_bb84 (
                player_id TEXT NOT NULL, channel TEXT NOT NULL, round INTEGER NOT NULL,
                alice_bits TEXT NOT NULL, alice_bases TEXT NOT NULL, bob_bases TEXT NOT NULL,
                bob_bits TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0, compared INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(player_id, channel));
            CREATE TABLE IF NOT EXISTS institute_unlocks (
                tech TEXT PRIMARY KEY, call_id TEXT NOT NULL, minute INTEGER NOT NULL, unlocked_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS institute_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)


def run_for(c, player):
    """Open to every player already connected to the Malla (Capa 03 started)."""
    if not enabled() or not _exists(c):
        return None
    if c.execute("SELECT 1 FROM layer_three WHERE player_id=?", (player,)).fetchone() is None:
        return None
    done = c.execute("SELECT COUNT(*) FROM institute_progress WHERE player_id=? AND completed_minute IS NOT NULL",
                     (player,)).fetchone()[0]
    return {"completed": done > 0, "decision": "RESEARCHED" if done else None}


def files(c, player: str, relay, story3) -> dict:
    if relay is not None or run_for(c, player) is None:
        return {}
    return {f"{story3.home}/correo/instituto.eml": i18n.t(MAIL)}


# --- calls, progress and the registry -------------------------------------

def _name(c, player):
    row = c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()
    return row[0] if row else player


def _progress(c, player, call_id) -> dict:
    row = c.execute("SELECT read, experiment, demo, completed_minute FROM institute_progress "
                    "WHERE player_id=? AND call_id=?", (player, call_id)).fetchone()
    if row is None:
        return {"read": set(), "experiment": False, "demo": False, "completed": None}
    return {"read": set(filter(None, row[0].split(","))), "experiment": bool(row[1]), "demo": bool(row[2]),
            "completed": row[3]}


def _mark(c, player, call_id, field, value) -> None:
    c.execute("INSERT OR IGNORE INTO institute_progress(player_id, call_id) VALUES(?,?)", (player, call_id))
    c.execute(f"UPDATE institute_progress SET {field}=? WHERE player_id=? AND call_id=?", (value, player, call_id))


def _studied(call, progress) -> bool:
    return set(call["articles"]) <= progress["read"]


def _finished(c, call_id) -> list:
    return c.execute("SELECT player_id, completed_minute FROM institute_progress WHERE call_id=? "
                     "AND completed_minute IS NOT NULL ORDER BY completed_at, completed_minute", (call_id,)).fetchall()


def _unlocked(c) -> dict:
    return {tech: minute for tech, minute in c.execute("SELECT tech, minute FROM institute_unlocks ORDER BY unlocked_at")}


def _complete(c, player, call_id, minute, result) -> list:
    """Close the call for this player once its three parts are done; the last one in may change the Malla."""
    call, progress = CALLS[call_id], _progress(c, player, call_id)
    if progress["completed"] is not None or not (_studied(call, progress) and progress["experiment"]
                                                 and progress["demo"]):
        return []
    c.execute("UPDATE institute_progress SET completed_minute=?, completed_at=? WHERE player_id=? AND call_id=?",
              (minute, time.time(), player, call_id))
    c.execute("INSERT OR REPLACE INTO institute_knowledge VALUES(?,?,?,?)", (player, HIDEO, call["memory"], minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'RESEARCH_COMPLETED',?,?)",
              (minute, player, call_id, HOST))
    result["changed"] = True
    lines = ["", i18n.t(f"CONVOCATORIA {call_id} COMPLETADA · {TITLE}"),
             i18n.t("Tu nombre entra en el registro del Instituto: instituto registro.")]
    tech, done = call["unlock"], len(_finished(c, call_id))
    if tech in _unlocked(c):
        return lines
    title = TECHS[tech]["title"]
    if done < call["threshold"]:
        return lines + [i18n.t(f"Van {done} de {call['threshold']}. Cuando lleguen a {call['threshold']}, "
                               f"{title} entrará en la Malla para todos.")]
    c.execute("INSERT INTO institute_unlocks VALUES(?,?,?,?)", (tech, call_id, minute, int(time.time())))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'MALLA_EVOLVES',?,?)",
              (minute, player, tech, call_id))
    return lines + ["", i18n.t(f"LA MALLA APRENDE · {title} entra en la Malla para todos."),
                    i18n.t(TECHS[tech]["text"]), i18n.t(TECHS[tech]["line"])]


def _checks(call, progress) -> list:
    def box(done):
        return "[x]" if done else "[ ]"
    return [box(_studied(call, progress)), box(progress["experiment"]), box(progress["demo"])]


def _count(c, call_id) -> str:
    call, done = CALLS[call_id], len(_finished(c, call_id))
    if call["unlock"] in _unlocked(c):
        return i18n.t(f"han terminado {done} · {TECHS[call['unlock']]['title']} ya está en la Malla")
    return i18n.t(f"han terminado {done}/{call['threshold']}")


def _portal(c, player) -> str:
    lines = [f"{i18n.t(TITLE).upper()} · {HOST}",
             i18n.t("Dirige: Hideo Sakamoto, profesor de ciencias del colegio."), "",
             i18n.t("Convocatorias abiertas:")]
    for call_id, call in CALLS.items():
        progress = _progress(c, player, call_id)
        study, experiment, demo = _checks(call, progress)
        state = i18n.t("terminada") if progress["completed"] is not None else \
            i18n.t(f"estudiar {study} · experimentar {experiment} · demostrar {demo}")
        done = _count(c, call_id)
        lines.append(f"  {call_id}  {i18n.t(call['title'])}")
        lines.append(f"         {state} · {done}")
    unlocked = _unlocked(c)
    lines.append("")
    if unlocked:
        known = ", ".join(i18n.t(f"{TECHS[tech]['title']} (desde el minuto {minute})") for tech, minute in unlocked.items())
        lines.append(i18n.t("Lo que ya sabe la Malla:") + " " + known)
    else:
        lines.append(i18n.t("Lo que ya sabe la Malla: nada nuevo todavía."))
    lines.append(i18n.t("instituto ver QB-01 · instituto leer qubit · instituto registro · man instituto"))
    return "\n".join(lines)


def _call_id(text: str):
    code = text.upper()
    if not code.startswith("QB-") and code.startswith("QB"):
        code = "QB-" + code[2:]
    return code if code in CALLS else None


def _show(c, player, args) -> str:
    call_id = _call_id(args[0]) if args else next(iter(CALLS))
    if call_id is None:
        return i18n.t("No hay ninguna convocatoria con ese código. instituto enseña las abiertas.")
    call, progress = CALLS[call_id], _progress(c, player, call_id)
    study, experiment, demo = _checks(call, progress)
    articles = " · ".join(i18n.t(f"instituto leer {slug}") for slug in call["articles"])
    lines = [f"{call_id} · {i18n.t(call['title'])}",
             i18n.t(f"{TITLE} · umbral: {call['threshold']} personas · "
                    f"trae a la Malla: {TECHS[call['unlock']]['title']}"), "",
             i18n.t(call["summary"]), "",
             f"1. {i18n.t('Estudiar')} {study}  {articles}",
             f"2. {i18n.t('Experimentar')} {experiment}  {i18n.t(call['experiment'])}",
             f"3. {i18n.t('Demostrar')} {demo}  {i18n.t(call['demo'])}", ""]
    if progress["completed"] is not None:
        lines.append(i18n.t(f"La terminaste en el minuto {progress['completed']}. Estás en el registro."))
    lines.append(_count(c, call_id).capitalize() + ".")
    return "\n".join(lines)


def _read(c, player, args, minute, result) -> str:
    slug = ARTICLE_ALIASES.get(args[0].lower(), args[0].lower()) if args else ""
    if slug not in ARTICLES:
        return i18n.t("Artículos del Instituto:") + " " + ", ".join(sorted(ARTICLES)) + \
            "\n" + i18n.t("instituto leer <artículo>")
    text = i18n.t(ARTICLES[slug])
    extra = []
    for call_id, call in CALLS.items():
        if slug not in call["articles"]:
            continue
        progress = _progress(c, player, call_id)
        if slug not in progress["read"]:
            _mark(c, player, call_id, "read", ",".join(sorted(progress["read"] | {slug})))
            if _studied(call, _progress(c, player, call_id)):
                extra.append(i18n.t(f"Parte 1 de {call_id} (estudiar) conseguida."))
            extra += _complete(c, player, call_id, minute, result)
    return "\n".join([text] + ([""] + extra if extra else []))


def _registry(c) -> str:
    lines = [i18n.t(f"Registro del {TITLE}")]
    for call_id, call in CALLS.items():
        rows = _finished(c, call_id)
        lines.append(f"{call_id} · {i18n.t(call['title'])}")
        if not rows:
            lines.append("  " + i18n.t("(nadie la ha terminado todavía)"))
        for number, (player, minute) in enumerate(rows, start=1):
            lines.append(f"  {number}. {_name(c, player)} · {i18n.t('minuto')} {minute}")
    for tech, minute in _unlocked(c).items():
        lines.append(i18n.t(f"{TECHS[tech]['title']} entró en la Malla en el minuto {minute}."))
    return "\n".join(lines)


# --- qubit: the one-qubit simulator ----------------------------------------
# With only X, Z and H from |0>, a qubit is always one of four states (up to a
# global sign that no measurement can see): |0>, |1>, |+> and |->.

GATES = {"x": {"0": "1", "1": "0", "+": "+", "-": "-"},
         "z": {"0": "0", "1": "1", "+": "-", "-": "+"},
         "h": {"0": "+", "1": "-", "+": "0", "-": "1"}}
FORMS = {"0": "|0>", "1": "|1>", "+": "|+> = (|0> + |1>)/√2", "-": "|-> = (|0> - |1>)/√2"}


def _qubit_state(c, player) -> str:
    row = c.execute("SELECT state FROM institute_qubit WHERE player_id=?", (player,)).fetchone()
    return row[0] if row else "0"


def _set_qubit(c, player, state) -> None:
    c.execute("INSERT OR REPLACE INTO institute_qubit VALUES(?,?)", (player, state))


def _describe(state) -> str:
    z = i18n.t(f"Medido en la base Z: {state} seguro.") if state in "01" else \
        i18n.t("Medido en la base Z: 0 o 1, al 50 %.")
    x = i18n.t(f"Medido en la base X: {state} seguro (cuenta como {'0' if state == '+' else '1'}).") \
        if state in "+-" else i18n.t("Medido en la base X: + o -, al 50 %.")
    return "\n".join([i18n.t("Tu qubit:") + " " + FORMS[state], z, x])


def _measure(state, basis):
    """(bit, sign shown, state after). The outcome is certain only when the state belongs to the basis."""
    if basis == "z":
        bit = state if state in "01" else random.choice("01")
        return bit, bit, bit
    after = state if state in "+-" else random.choice("+-")
    return ("0" if after == "+" else "1"), after, after


def _qubit(c, player, args, minute, result) -> str:
    sub = QUBIT_SUB.get(args[0].lower(), args[0].lower()) if args else "estado"
    state = _qubit_state(c, player)
    if sub == "estado":
        return _describe(state)
    if sub in ("nuevo", "reset"):
        _set_qubit(c, player, "0")
        return i18n.t("Qubit nuevo: empieza en |0>.")
    if sub in GATES:
        after = GATES[sub][state]
        _set_qubit(c, player, after)
        return i18n.t(f"Aplicas {sub.upper()}: el qubit pasa de {FORMS[state][:3]} a {FORMS[after][:3]}.")
    if sub == "medir":
        basis = (args[1].lower() if len(args) > 1 else "z").replace("+", "z").replace("×", "x")
        if basis not in ("z", "x"):
            return i18n.t("Uso: qubit medir [z|x]")
        bit, shown, after = _measure(state, basis)
        _set_qubit(c, player, after)
        sure = (state in "01") == (basis == "z")
        lines = [i18n.t(f"Mides en la base Z: sale {bit}.") if basis == "z" else
                 i18n.t(f"Mides en la base X: sale {shown} (cuenta como {bit}).")]
        lines.append(i18n.t(f"Era seguro: el qubit ya estaba en {FORMS[state][:3]}.") if sure else
                     i18n.t(f"Era al azar: el qubit estaba en {FORMS[state][:3]} y la medida lo ha dejado en "
                            f"{FORMS[after][:3]}."))
        if basis == "x" and state == "-":
            lines += _experiment_done(c, player, minute, result)
        return "\n".join(lines)
    return i18n.t(QUBIT_HELP)


def _experiment_done(c, player, minute, result) -> list:
    progress = _progress(c, player, "QB-01")
    if progress["experiment"]:
        return []
    _mark(c, player, "QB-01", "experiment", 1)
    return ["", i18n.t("Parte 2 de QB-01 (experimentar) conseguida: un 1 seguro en la base X. Hideo lo apunta.")] \
        + _complete(c, player, "QB-01", minute, result)


# --- bb84: a key with Hideo, over two channels, one of them tapped -----------

def _spied(player) -> str:
    return CHANNELS[hashlib.sha256(f"bb84-espia:{player}".encode()).digest()[0] % 2]


def _split(alice_bases, bob_bases):
    """Matching positions, halved: the odd ones are compared in public, the even ones are the key."""
    matches = [i for i in range(len(alice_bases)) if alice_bases[i] == bob_bases[i]]
    return matches[0::2], matches[1::2]


def _photons(player, channel, number, bob_bases):
    """Hideo's photons for one round, as Bob measures them. On the tapped channel someone measures
    every photon first, in a base of their own, and resends what they got (intercept and resend).
    Rounds are drawn until the key has at least four bits and the tap shows in the sample."""
    spied = channel == _spied(player)
    for attempt in range(1000):
        rng = random.Random(f"bb84:{player}:{channel}:{number}:{attempt}")
        alice_bits = "".join(rng.choice("01") for _ in range(PHOTONS))
        alice_bases = "".join(rng.choice("+x") for _ in range(PHOTONS))
        bob_bits = []
        for i in range(PHOTONS):
            bit, basis = alice_bits[i], alice_bases[i]
            if spied:
                eve = rng.choice("+x")
                bit, basis = (bit if eve == basis else rng.choice("01")), eve
            bob_bits.append(bit if bob_bases[i] == basis else rng.choice("01"))
        bob_bits = "".join(bob_bits)
        sample, key = _split(alice_bases, bob_bases)
        errors = sum(alice_bits[i] != bob_bits[i] for i in sample)
        if len(key) >= 4 and (not spied or errors >= 2):
            break
    return alice_bits, alice_bases, bob_bits


def _round(c, player, channel):
    row = c.execute("SELECT round, alice_bits, alice_bases, bob_bases, bob_bits, published, compared "
                    "FROM institute_bb84 WHERE player_id=? AND channel=?", (player, channel)).fetchone()
    if row is None:
        return None
    return dict(zip(("round", "alice_bits", "alice_bases", "bob_bases", "bob_bits", "published", "compared"), row))


def _groups(text) -> str:
    return " ".join(text[i:i + 4] for i in range(0, len(text), 4))


def _row(label, value) -> str:
    return f"{i18n.t(label):<16}{value}"


def _ruler() -> str:
    return _row("posición", "".join(f"{i + 1:<5}" for i in range(0, PHOTONS, 4)).rstrip())


def _channel(args):
    return args[0].lower() if args and args[0].lower() in CHANNELS else None


def _bb84(c, player, args) -> str:
    sub = BB84_SUB.get(args[0].lower(), args[0].lower()) if args else ""
    rest = args[1:]
    if sub == "medir":
        channel = _channel(rest)
        if channel is None:
            return i18n.t("Uso: bb84 medir <a|b> [bases]")
        given = rest[1] if len(rest) > 1 else ""
        bases = given.lower().replace("×", "x")
        if given and (len(bases) != PHOTONS or set(bases) - {"+", "x"}):
            return i18n.t(f"Necesito {PHOTONS} bases, una por fotón: + (recta) o x (diagonal). "
                          "O ninguna, y las elijo al azar.")
        bases = bases or "".join(random.choice("+x") for _ in range(PHOTONS))
        previous = _round(c, player, channel)
        number = previous["round"] + 1 if previous else 1
        alice_bits, alice_bases, bob_bits = _photons(player, channel, number, bases)
        c.execute("INSERT OR REPLACE INTO institute_bb84 VALUES(?,?,?,?,?,?,?,0,0)",
                  (player, channel, number, alice_bits, alice_bases, bases, bob_bits))
        lines = [i18n.t(f"Canal {channel.upper()} · ronda {number} · Hideo te manda {PHOTONS} fotones y los mides.")]
        if not given:
            lines.append(i18n.t("Eliges las bases al azar, como haría Bob."))
        lines += [_ruler(), _row("tus bases", _groups(bases)), _row("tus bits", _groups(bob_bits)),
                  i18n.t(f"Ahora Hideo puede decir sus bases en público (nunca sus bits): bb84 bases {channel}")]
        return "\n".join(lines)
    if sub in ("bases", "comparar"):
        channel = _channel(rest)
        if channel is None:
            return i18n.t("Uso: bb84 bases <a|b>" if sub == "bases" else "Uso: bb84 comparar <a|b>")
        run = _round(c, player, channel)
        if run is None:
            return i18n.t(f"Todavía no has medido nada por ese canal: bb84 medir {channel}")
        if sub == "bases":
            c.execute("UPDATE institute_bb84 SET published=1 WHERE player_id=? AND channel=?", (player, channel))
            return "\n".join([
                i18n.t(f"Canal {channel.upper()} · Hideo publica sus bases. Sus bits no los dice."),
                _ruler(), _row("bases de Hideo", _groups(run["alice_bases"])),
                _row("tus bases", _groups(run["bob_bases"])), _row("tus bits", _groups(run["bob_bits"])),
                i18n.t(f"Quédate con las posiciones donde las bases coinciden. Luego comparad una muestra: "
                       f"bb84 comparar {channel}")])
        if not run["published"]:
            return i18n.t(f"Primero Hideo tiene que decir sus bases: bb84 bases {channel}")
        c.execute("UPDATE institute_bb84 SET compared=1 WHERE player_id=? AND channel=?", (player, channel))
        sample, _key = _split(run["alice_bases"], run["bob_bases"])
        return "\n".join([
            i18n.t(f"Canal {channel.upper()} · Hideo y tú comparáis en público la mitad de las posiciones donde "
                   "coincidís (la 1.ª, la 3.ª, la 5.ª…):"),
            _row("posición", "".join(f"{i + 1:>3}" for i in sample)),
            _row("bit de Hideo", "".join(f"{run['alice_bits'][i]:>3}" for i in sample)),
            _row("tu bit", "".join(f"{run['bob_bits'][i]:>3}" for i in sample)),
            i18n.t("Si alguien midió los fotones por el camino, no coincidirán todos (fallará uno de cada cuatro, más o menos)."),
            i18n.t(f"Esas posiciones ya son públicas. La clave son tus bits en las otras posiciones donde coincidís, "
                   f"en orden: instituto entregar {channel} <clave>")])
    lines = [i18n.t(f"BB84 con Hideo · {PHOTONS} fotones por canal · uno de los dos canales está pinchado")]
    for channel in CHANNELS:
        run = _round(c, player, channel)
        if run is None:
            state = i18n.t("sin medir")
        else:
            steps = [i18n.t(f"ronda {run['round']}"), i18n.t("medido")]
            steps += [i18n.t("bases publicadas")] if run["published"] else []
            steps += [i18n.t("muestra comparada")] if run["compared"] else []
            state = " · ".join(steps)
        lines.append(f"  {i18n.t('canal')} {channel}: {state}")
    lines.append(i18n.t("bb84 medir a · bb84 bases a · bb84 comparar a · man bb84"))
    return "\n".join(lines)


def _submit(c, player, args, minute, result) -> str:
    if args and _call_id(args[0]):
        args = args[1:]
    if len(args) < 2 or args[0].lower() not in CHANNELS:
        return i18n.t("Uso: instituto entregar <canal> <clave>   (por ejemplo: instituto entregar a 0110...)")
    if _progress(c, player, "QB-01")["demo"]:
        return i18n.t("Ya entregaste tu clave de QB-01. Hideo la tiene apuntada.")
    # The key may come in groups of four, as bb84 prints bits.
    channel, key = args[0].lower(), "".join(args[1:])
    run = _round(c, player, channel)
    if run is None:
        return i18n.t(f"Primero saca la clave: bb84 medir {channel}")
    if not run["published"]:
        return i18n.t(f"Todavía no sabes qué posiciones valen: bb84 bases {channel}")
    if not run["compared"]:
        return i18n.t(f"Antes de usar una clave hay que comprobar que nadie escuchaba: bb84 comparar {channel}")
    if channel == _spied(player):
        return i18n.t("Hideo no se fía de esa clave: en la muestra de ese canal hay bits que no coinciden. "
                      "Eso no es ruido: alguien medía los fotones por el camino. Prueba con el otro canal.")
    _sample, positions = _split(run["alice_bases"], run["bob_bases"])
    expected = "".join(run["alice_bits"][i] for i in positions)
    if key != expected:
        return i18n.t("Esa no es la clave. Son tus bits en las posiciones donde coinciden las bases y que no se "
                      "publicaron al comparar, en orden.")
    _mark(c, player, "QB-01", "demo", 1)
    lines = [i18n.t(f"Clave aceptada: {key} ({len(key)} bits). Hideo tiene la misma sin que nadie la haya dicho, "
                    "y sabéis que nadie escuchaba."),
             i18n.t("Parte 3 de QB-01 (demostrar) conseguida.")]
    progress = _progress(c, player, "QB-01")
    missing = [i18n.t("estudiar (instituto leer)")] if not _studied(CALLS["QB-01"], progress) else []
    missing += [i18n.t("experimentar (qubit)")] if not progress["experiment"] else []
    if missing:
        lines.append(i18n.t("Para terminar la convocatoria te falta:") + " " + ", ".join(missing))
    return "\n".join(lines + _complete(c, player, "QB-01", minute, result))


# --- qkd: what the Malla learnt -----------------------------------------------

def _qkd(c, player, story3) -> str:
    call = CALLS["QB-01"]
    if "qkd" not in _unlocked(c):
        done = len(_finished(c, "QB-01"))
        return "\n".join([i18n.t("qkd: la Malla todavía no sabe repartir claves con fotones."),
                          i18n.t(f"Llegará cuando {call['threshold']} personas terminen la convocatoria QB-01 del "
                                 f"Instituto (instituto ver QB-01). Van {done}.")])
    from .layer_three import RELAYS
    hops = [story3.navi, RELAYS["RELAY_SCHOOL"][0], RELAYS["RELAY_STATION"][0], RELAYS["RELAY_VIDEO"][0]]
    # The links are quiet but for one, a different one every day: KAGAMI copies everything.
    rng = random.Random(f"qkd:{datetime.date.today().isoformat()}")
    tapped = rng.randrange(len(hops) - 1)
    lines = [i18n.t("qkd · enlaces cuánticos de la Malla (BB84 entre armarios)")]
    for index in range(len(hops) - 1):
        rate = rng.randint(22, 27) if index == tapped else rng.randint(1, 4)
        state = i18n.t("ALGUIEN ESCUCHA") if index == tapped else i18n.t("ruido del cable")
        lines.append(f"  {hops[index]:<16} <-> {hops[index + 1]:<16} QBER {rate:>2} %  {state}")
    lines.append(i18n.t("Por debajo del 11 % es ruido. Por encima, alguien mide los fotones: KAGAMI lo copia todo."))
    return "\n".join(lines)


def dispatch(c, player, story3, relay, result, name, args, minute):
    if name == "qubit":
        return _qubit(c, player, args, minute, result)
    if name == "bb84":
        return _bb84(c, player, args)
    if name == "qkd":
        return _qkd(c, player, story3)
    sub = SUB.get(args[0].lower(), args[0].lower()) if args else ""
    rest = args[1:]
    if not sub:
        return _portal(c, player)
    if sub == "ver":
        return _show(c, player, rest)
    if sub == "leer":
        return _read(c, player, rest, minute, result)
    if sub == "registro":
        return _registry(c)
    if sub == "entregar":
        return _submit(c, player, rest, minute, result)
    return i18n.t(HELP)


HELP = """Instituto de Física del Puerto (instituto.malla):
  instituto · instituto ver <código> · instituto leer <artículo> · instituto registro
  qubit [nuevo|x|z|h|medir z|medir x]    el simulador de un qubit
  bb84 [medir|bases|comparar] <canal>    una clave con Hideo · instituto entregar <canal> <clave>"""
QUBIT_HELP = "Uso: qubit [estado|nuevo|x|z|h|medir z|medir x]"

MAN = {
    "instituto": """instituto · el Instituto de Física del Puerto (instituto.malla)

  instituto                   convocatorias abiertas y lo que ya sabe la Malla
  instituto ver <código>      una convocatoria: sus tres partes y cómo vas
  instituto leer <artículo>   los artículos para estudiar
  instituto entregar ...      entrega el resultado de una convocatoria
  instituto registro          quién ha terminado cada convocatoria
Cada convocatoria tiene tres partes: estudiar, experimentar y demostrar.
Cuando la terminan bastantes personas, su tecnología entra en la Malla para
todos.""",
    "qubit": """qubit · el simulador de un qubit del Instituto

  qubit                  cómo está tu qubit y qué saldría al medirlo
  qubit nuevo            vuelve a empezar en |0>
  qubit x | z | h        aplica una puerta (instituto leer qubit)
  qubit medir [z|x]      mide en la base Z (recta, la de siempre) o en la X
                         (diagonal)
Medir cambia el qubit: después queda en el estado que salió.
En la base X, + cuenta como 0 y - como 1.""",
    "bb84": """bb84 · repartir una clave con Hideo

Hideo te manda 24 fotones por cada canal (a y b). Uno de los dos canales
está pinchado.
  bb84 medir <canal> [bases]   mides los fotones; bases: 24 signos + o x, o
                               ninguna y se eligen al azar (como haría Bob)
  bb84 bases <canal>           Hideo publica sus bases (nunca sus bits)
  bb84 comparar <canal>        sacrificáis la mitad de las posiciones donde
                               coincidís: Hideo publica sus bits en ellas
  bb84                         cómo va cada canal
La clave son tus bits en las posiciones donde coincidís y que no se han
publicado, en orden. Se entrega con instituto entregar <canal> <clave>.
Medir otra vez empieza una ronda nueva, con fotones nuevos.""",
    "qkd": """qkd · claves cuánticas entre los armarios de la Malla

Cuando QKD entra en la Malla, los armarios reparten sus claves con BB84.
qkd enseña cada enlace con su tasa de error (QBER). Por debajo del 11 % es
ruido del cable; por encima, alguien está midiendo los fotones.""",
}
MAN_ALIASES = {"institute": "instituto", "instituto.malla": "instituto", "qbit": "qubit", "bb-84": "bb84"}


# --- what the world sees ------------------------------------------------------

def layer_actor_context(actor: str, player: str) -> list:
    if actor not in (HIDEO, NORA):
        return []
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM institute_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
        unlocked = _unlocked(c)
    memories = [{"id": "RESEARCH_COMPLETED", "text": text, "source": player, "learned_minute": minute}
                for text, minute in rows]
    return memories + [{"id": f"MALLA_{tech.upper()}", "text": TECHS[tech]["memory"], "source": HOST,
                        "learned_minute": minute} for tech, minute in unlocked.items()]


def institute_snapshot(player: str) -> dict:
    if not enabled():
        return {"active": False}
    with get_connection() as c:
        if run_for(c, player) is None:
            return {"active": False}
        completed = [call_id for call_id in CALLS if _progress(c, player, call_id)["completed"] is not None]
        unlocked = list(_unlocked(c))
    return {
        "active": True,
        "completed": [{"id": call_id, "title": CALLS[call_id]["title"]} for call_id in completed],
        "unlocked": [{"id": tech, "title": TECHS[tech]["title"], "text": TECHS[tech]["text"],
                      "line": TECHS[tech]["line"]} for tech in unlocked],
    }
