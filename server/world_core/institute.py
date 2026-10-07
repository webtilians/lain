"""The Instituto de Física del Puerto's own call, QB-01: the qubit and BB84.

The centres, the registry and the threshold are in research.py; this module
holds what only QB-01 has: its articles, a one-qubit simulator (`qubit`), a
key shared with Hideo over two channels, one of them tapped (`bb84`), and what
three researchers bring to every terminal (`qkd`).
"""
import datetime
import hashlib
import random

from .database import get_connection
from . import i18n

HIDEO = "RESIDENT_019"
COMMANDS = {"qubit", "bb84", "qkd"}
RAW_COMMANDS = COMMANDS
PHOTONS = 24
CHANNELS = ("a", "b")
QUBIT_SUB = {"new": "nuevo", "measure": "medir", "state": "estado"}
BB84_SUB = {"measure": "medir", "compare": "comparar"}

CALLS = {
    "QB-01": {
        "centre": "instituto",
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
    "qkd": {"title": "QKD", "text": "Indara reparte claves con fotones: si alguien escucha, se nota.",
            "line": "Desde hoy, cualquiera puede usar qkd en el terminal.",
            "memory": "QKD ya está en Indara: los armarios reparten sus claves con fotones y, si alguien "
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

MAIL = ("De: hideo <hideo@instituto.indara>\nAsunto: convocatoria QB-01\n\n"
        "Doy ciencias en el colegio y, en mis ratos libres, llevo el Instituto de Física del Puerto, en Indara.\n"
        "Tenemos una convocatoria abierta: el qubit y la clave que delata al espía.\n"
        "Si tres personas la terminan, Indara aprenderá a repartir claves con fotones.\n"
        "Empieza por la orden instituto. Y no te creas nada que no puedas medir.")


def enabled() -> bool:
    from . import layer_three
    return layer_three.enabled()


def initialize_institute() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS institute_qubit (player_id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS institute_bb84 (
                player_id TEXT NOT NULL, channel TEXT NOT NULL, round INTEGER NOT NULL,
                alice_bits TEXT NOT NULL, alice_bases TEXT NOT NULL, bob_bases TEXT NOT NULL,
                bob_bits TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0, compared INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(player_id, channel));
        """)


def run_for(c, player):
    """Open with the research centres: to every player already connected to Indara."""
    from . import research
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='institute_qubit'").fetchone() is None:
        return None
    return research.run_for(c, player)


def files(c, player: str, relay, story3) -> dict:
    if relay is not None or run_for(c, player) is None:
        return {}
    return {f"{story3.home}/correo/instituto.eml": i18n.t(MAIL)}


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
    from . import research
    if research.progress(c, player, "QB-01")["experiment"]:
        return []
    research.mark(c, player, "QB-01", "experiment", 1)
    return ["", i18n.t("Parte 2 de QB-01 (experimentar) conseguida: un 1 seguro en la base X. Hideo lo apunta.")] \
        + research.complete(c, player, "QB-01", minute, result)


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


def submit(c, player, args, minute, result) -> str:
    """QB-01's demonstration: the key of the clean channel (research.py hands it over)."""
    from . import research
    if len(args) < 2 or args[0].lower() not in CHANNELS:
        return i18n.t("Uso: instituto entregar <canal> <clave>   (por ejemplo: instituto entregar a 0110...)")
    if research.progress(c, player, "QB-01")["demo"]:
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
    research.mark(c, player, "QB-01", "demo", 1)
    lines = [i18n.t(f"Clave aceptada: {key} ({len(key)} bits). Hideo tiene la misma sin que nadie la haya dicho, "
                    "y sabéis que nadie escuchaba."),
             i18n.t("Parte 3 de QB-01 (demostrar) conseguida.")]
    state = research.progress(c, player, "QB-01")
    missing = [i18n.t("estudiar (instituto leer)")] if not research.studied(research.calls(c)["QB-01"], state) else []
    missing += [i18n.t("experimentar (qubit)")] if not state["experiment"] else []
    if missing:
        lines.append(i18n.t("Para terminar la convocatoria te falta:") + " " + ", ".join(missing))
    return "\n".join(lines + research.complete(c, player, "QB-01", minute, result))


# --- qkd: what Indara learnt -----------------------------------------------

def _qkd(c, player, story3) -> str:
    from . import research
    call = CALLS["QB-01"]
    if "qkd" not in research.unlocked(c):
        done = len(research.finished(c, "QB-01"))
        return "\n".join([i18n.t("qkd: Indara todavía no sabe repartir claves con fotones."),
                          i18n.t(f"Llegará cuando {call['threshold']} personas terminen la convocatoria QB-01 del "
                                 f"Instituto (instituto ver QB-01). Van {done}.")])
    from .layer_three import RELAYS
    hops = [story3.navi, RELAYS["RELAY_SCHOOL"][0], RELAYS["RELAY_STATION"][0], RELAYS["RELAY_VIDEO"][0]]
    # The links are quiet but for one, a different one every day: KAGAMI copies everything.
    rng = random.Random(f"qkd:{datetime.date.today().isoformat()}")
    tapped = rng.randrange(len(hops) - 1)
    lines = [i18n.t("qkd · enlaces cuánticos de Indara (BB84 entre armarios)")]
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
    return _qkd(c, player, story3)


HELP = """Instituto de Física del Puerto · QB-01:
  qubit [nuevo|x|z|h|medir z|medir x]    el simulador de un qubit
  bb84 [medir|bases|comparar] <canal>    una clave con Hideo · instituto entregar <canal> <clave>"""
QUBIT_HELP = "Uso: qubit [estado|nuevo|x|z|h|medir z|medir x]"

MAN = {
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
    "qkd": """qkd · claves cuánticas entre los armarios de Indara

Cuando QKD entra en Indara, los armarios reparten sus claves con BB84.
qkd enseña cada enlace con su tasa de error (QBER). Por debajo del 11 % es
ruido del cable; por encima, alguien está midiendo los fotones.""",
}
MAN_ALIASES = {"qbit": "qubit", "bb-84": "bb84"}
