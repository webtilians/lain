"""Círculo de dos: a challenge only two players can solve, each at a different link cabinet.

Ryoko's Circles are links nobody owns. To open one, two people agree on a key
that never travels: a Diffie-Hellman exchange. Each gets a secret number at
their own cabinet, publishes g^secret mod p to the circle, and raises the other
one's public value to their secret. Both arrive at the same key without ever
saying it; neither KAGAMI (who copies) nor NOEMA (who rewrites registers) can
read it. The link opens only when both confirm it from two different cabinets
within ten real minutes.
"""
import hashlib
import random
import time

from .database import get_connection
from . import i18n

TITLE = "Círculo de dos"
COMMANDS = {"circulo", "circle", "powmod"}
RAW_COMMANDS = COMMANDS
# Real seconds between the two confirmations. Not world minutes: online, ten world minutes pass
# every eight real seconds, and half an hour of the world would be gone before anyone typed.
WINDOW = 600
PRIMES = [2027, 2039, 2053, 2063, 2069, 2081, 2083, 2087, 2089, 2099, 3001, 3011, 3019, 3023, 3037, 3041]
SUB = {"open": "abrir", "join": "unirse", "publish": "publicar", "show": "ver", "link": "enlazar",
       "leave": "salir", "list": "lista"}
# Nora wants everything to propagate: she is the one who hears about every new circle.
NORA = "AGENT_NORA"
README = ("Círculos · enlaces sin dueño\n"
          "Dos personas, dos armarios distintos, una clave que nunca viaja.\n"
          "circulo abrir · circulo lista · circulo unirse <código> · man dh")


def enabled() -> bool:
    from . import layer_three
    return layer_three.enabled()


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='duo_links'").fetchone() is not None


def initialize_duo() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS duo_links (
                code TEXT PRIMARY KEY, p INTEGER NOT NULL, g INTEGER NOT NULL,
                created_minute INTEGER NOT NULL, opened_minute INTEGER);
            CREATE TABLE IF NOT EXISTS duo_members (
                code TEXT NOT NULL, player_id TEXT NOT NULL, relay TEXT NOT NULL, secret INTEGER NOT NULL,
                public INTEGER, confirmed_minute INTEGER, PRIMARY KEY(code, player_id));
            CREATE TABLE IF NOT EXISTS duo_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)


def run_for(c, player):
    """Open to every player already connected to Indara (Capa 03 started)."""
    if not enabled() or not _exists(c):
        return None
    if c.execute("SELECT 1 FROM layer_three WHERE player_id=?", (player,)).fetchone() is None:
        return None
    done = c.execute("SELECT COUNT(*) FROM duo_members m JOIN duo_links l ON l.code=m.code "
                     "WHERE m.player_id=? AND l.opened_minute IS NOT NULL", (player,)).fetchone()[0]
    return {"completed": done > 0, "decision": "OPENED" if done else None}


def _name(c, player):
    row = c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()
    return row[0] if row else player


def _relay_name(relay):
    from .layer_three import RELAYS
    return RELAYS[relay][0] if relay in RELAYS else relay


def _mine(c, player):
    """The circle this player is in and not yet opened, if any."""
    return c.execute("SELECT l.code, l.p, l.g, m.relay, m.secret, m.public, m.confirmed_minute FROM duo_members m "
                     "JOIN duo_links l ON l.code=m.code WHERE m.player_id=? AND l.opened_minute IS NULL",
                     (player,)).fetchone()


def _members(c, code):
    return c.execute("SELECT player_id, relay, public, confirmed_minute FROM duo_members WHERE code=? "
                     "ORDER BY rowid", (code,)).fetchall()


def files(c, player: str, relay, story3) -> dict:
    if run_for(c, player) is None:
        return {}
    if relay is None:
        return {f"{story3.home}/correo/circulos.eml": i18n.t(MAIL)}
    return {"/var/circulos/LEEME": i18n.t(README), "/var/circulos/registro": _registry(c)}


MAIL = ("De: ryoko\nAsunto: un círculo de dos\n\n"
        "Una red sin dueño empieza con dos personas que se fían la una de la otra sin que nadie lo apunte.\n"
        "Busca a alguien. Cada uno en un armario distinto: el de la estación, el del aula o el del videoclub.\n"
        "Lo demás está en man dh. La clave no la digas nunca en voz alta: no hace falta.")


_registry_cache: dict = {}


def _registry(c) -> str:
    # Every command at a cabinet lists its files; the registry only changes when a circle opens.
    opened = c.execute("SELECT COUNT(*) FROM duo_links WHERE opened_minute IS NOT NULL").fetchone()[0]
    key = (str(c.execute("PRAGMA database_list").fetchone()[2]), opened, i18n.language())
    if key not in _registry_cache:
        _registry_cache.clear()
        _registry_cache[key] = _registry_text(c)
    return _registry_cache[key]


def _registry_text(c) -> str:
    rows = c.execute("SELECT l.code, l.opened_minute FROM duo_links l WHERE l.opened_minute IS NOT NULL "
                     "ORDER BY l.opened_minute, l.code").fetchall()
    if not rows:
        return i18n.t("(todavía no se ha abierto ningún círculo)")
    lines = []
    for code, minute in rows:
        names = " · ".join(_name(c, player) for player, *_ in _members(c, code))
        lines.append(f"{code} | {i18n.t('minuto')} {minute} | {names}")
    return "\n".join(lines)


def _new_code(c, rng) -> str:
    while True:
        code = f"C-{rng.randrange(1000, 10000)}"
        if c.execute("SELECT 1 FROM duo_links WHERE code=?", (code,)).fetchone() is None:
            return code


def _secret(code: str, player: str, p: int) -> int:
    digest = hashlib.sha256(f"duo:{code}:{player}".encode()).digest()
    return 2 + int.from_bytes(digest[:4], "big") % (p - 4)


def _open(c, player, relay, minute):
    if _mine(c, player):
        return i18n.t("Ya estás en un círculo. circulo ver te dice cómo va; circulo salir lo deja.")
    rng = random.Random(f"{player}:{minute}:{c.execute('SELECT COUNT(*) FROM duo_links').fetchone()[0]}")
    code, p = _new_code(c, rng), rng.choice(PRIMES)
    g = 2
    c.execute("INSERT INTO duo_links(code, p, g, created_minute) VALUES(?,?,?,?)", (code, p, g, minute))
    secret = _secret(code, player, p)
    c.execute("INSERT INTO duo_members(code, player_id, relay, secret) VALUES(?,?,?,?)", (code, player, relay, secret))
    return "\n".join([
        i18n.t(f"Círculo {code} abierto en {_relay_name(relay)}."),
        i18n.t(f"Parámetros públicos: p = {p}, g = {g}. Tu número secreto: a = {secret}. No se lo digas a nadie."),
        i18n.t("Otra persona tiene que unirse desde OTRO armario: circulo unirse " + code + "."),
        i18n.t("Después: calcula g^a mod p con powmod y publícalo con circulo publicar <valor>."),
    ])


def _join(c, player, relay, code):
    if _mine(c, player):
        return i18n.t("Ya estás en un círculo. circulo salir lo deja.")
    link = c.execute("SELECT p, g, opened_minute FROM duo_links WHERE code=?", (code.upper(),)).fetchone()
    if link is None or link[2] is not None:
        return i18n.t("No hay ningún círculo abierto con ese código. circulo lista enseña los que esperan.")
    members = _members(c, code.upper())
    if len(members) >= 2:
        return i18n.t("Ese círculo ya tiene a sus dos personas.")
    if members[0][1] == relay:
        return i18n.t("Tienes que unirte desde otro armario: un círculo de dos no cabe en un solo enlace.")
    p, g, _ = link
    code = code.upper()
    secret = _secret(code, player, p)
    c.execute("INSERT INTO duo_members(code, player_id, relay, secret) VALUES(?,?,?,?)", (code, player, relay, secret))
    return "\n".join([
        i18n.t(f"Te unes al círculo {code} desde {_relay_name(relay)}, con {_name(c, members[0][0])}."),
        i18n.t(f"Parámetros públicos: p = {p}, g = {g}. Tu número secreto: b = {secret}. No se lo digas a nadie."),
        i18n.t("Calcula g^b mod p con powmod y publícalo con circulo publicar <valor>."),
    ])


def _list(c, player):
    rows = c.execute("SELECT l.code, MIN(m.player_id), MIN(m.relay) FROM duo_links l JOIN duo_members m ON m.code=l.code "
                     "WHERE l.opened_minute IS NULL GROUP BY l.code HAVING COUNT(*)=1 ORDER BY l.created_minute DESC "
                     "LIMIT 8").fetchall()
    if not rows:
        return i18n.t("Ningún círculo espera a nadie ahora mismo. circulo abrir empieza uno.")
    return "\n".join([i18n.t("Círculos que esperan a su segunda persona:")] +
                     [f"  {code}  {_name(c, owner)}  ({_relay_name(relay)})" for code, owner, relay in rows])


def _show(c, player):
    mine = _mine(c, player)
    if mine is None:
        return i18n.t("No estás en ningún círculo. circulo abrir o circulo lista.")
    code, p, g = mine[0], mine[1], mine[2]
    lines = [i18n.t(f"Círculo {code} · p = {p}, g = {g}")]
    for member, relay, public, confirmed in _members(c, code):
        value = str(public) if public is not None else i18n.t("sin publicar")
        state = i18n.t("ha confirmado el enlace") if confirmed is not None else ""
        lines.append(f"  {_name(c, member)} ({_relay_name(relay)}): {i18n.t('valor público')} {value}  {state}".rstrip())
    if len(_members(c, code)) < 2:
        lines.append(i18n.t("Falta la segunda persona."))
    return "\n".join(lines)


def _publish(c, player, args):
    mine = _mine(c, player)
    if mine is None:
        return i18n.t("No estás en ningún círculo.")
    if not args or not args[0].isdigit():
        return i18n.t("Uso: circulo publicar <valor>")
    code, p, g, _relay, secret = mine[:5]
    if int(args[0]) != pow(g, secret, p):
        return i18n.t("Ese valor no sale de tu número secreto. Es g elevado a tu secreto, módulo p (man powmod).")
    c.execute("UPDATE duo_members SET public=? WHERE code=? AND player_id=?", (int(args[0]), code, player))
    return i18n.t("Publicado. La otra persona ya puede verlo con circulo ver. El tuyo puede verlo cualquiera: no importa.")


def _link(c, player, args, minute, result):
    mine = _mine(c, player)
    if mine is None:
        return i18n.t("No estás en ningún círculo.")
    if not args or not args[0].isdigit():
        return i18n.t("Uso: circulo enlazar <clave compartida>")
    code, p, _g, _relay, secret = mine[:5]
    other = [row for row in _members(c, code) if row[0] != player]
    if not other or other[0][2] is None:
        return i18n.t("La otra persona todavía no ha publicado su valor. Sin él no hay clave.")
    if int(args[0]) != pow(other[0][2], secret, p):
        return i18n.t("Esa clave no es la vuestra. Eleva el valor público de la otra persona a tu secreto, módulo p.")
    # confirmed_minute holds the real time of each confirmation (seconds), see WINDOW.
    now = int(time.time())
    c.execute("UPDATE duo_members SET confirmed_minute=? WHERE code=? AND player_id=?", (now, code, player))
    confirmed = other[0][3]
    if confirmed is None or now - confirmed > WINDOW:
        return i18n.t(f"Confirmado por tu lado. Falta la otra persona: tiene {WINDOW // 60} minutos para hacerlo.")
    return _opened(c, code, minute, result)


def _opened(c, code, minute, result):
    c.execute("UPDATE duo_links SET opened_minute=? WHERE code=?", (minute, code))
    members = _members(c, code)
    names = [_name(c, member) for member, *_ in members]
    for member, *_ in members:
        other = next(name for name in names if name != _name(c, member))
        memory = f"Abrió un círculo de dos con {other}: una clave que nunca viajó. Los Círculos crecen así."
        c.execute("INSERT OR REPLACE INTO duo_knowledge VALUES(?,?,?,?)", (member, NORA, memory, minute))
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'DUO_OPENED',?,?)",
                  (minute, member, code, other))
    result["changed"] = True
    return "\n".join([
        i18n.t(f"CÍRCULO DE DOS ABIERTO · {code} · {' · '.join(names)}"),
        i18n.t("El enlace no pasó por ningún servidor: la clave nunca viajó. Ni KAGAMI puede copiarla ni NOEMA reescribirla."),
        i18n.t("Ryoko lo anota en el registro de los Círculos: cat /var/circulos/registro."),
    ])


def _leave(c, player):
    mine = _mine(c, player)
    if mine is None:
        return i18n.t("No estás en ningún círculo.")
    c.execute("DELETE FROM duo_members WHERE code=? AND player_id=?", (mine[0], player))
    if not _members(c, mine[0]):
        c.execute("DELETE FROM duo_links WHERE code=?", (mine[0],))
    return i18n.t(f"Sales del círculo {mine[0]}.")


def _powmod(args):
    try:
        base, exponent, modulus = (int(value) for value in args)
    except ValueError:
        return i18n.t("Uso: powmod <base> <exponente> <módulo>")
    if modulus < 2 or exponent < 0 or max(base, exponent, modulus) > 10 ** 12:
        return i18n.t("Uso: powmod <base> <exponente> <módulo>")
    return f"{base}^{exponent} mod {modulus} = {pow(base, exponent, modulus)}"


def dispatch(c, player, story3, relay, result, name, args, minute):
    if name == "powmod":
        return _powmod(args)
    sub = SUB.get(args[0].lower(), args[0].lower()) if args else ""
    rest = args[1:]
    if sub not in ("", "ver", "lista", "salir", "publicar", "enlazar", "abrir", "unirse"):
        return i18n.t(HELP)
    if sub in ("ver", "lista", "salir", "publicar", "enlazar") or not sub:
        if sub == "lista":
            return _list(c, player)
        if sub == "salir":
            return _leave(c, player)
        if sub == "publicar":
            return _publish(c, player, rest)
        if sub == "enlazar":
            return _link(c, player, rest, minute, result)
        return _show(c, player)
    if relay is None:
        return i18n.t("Un círculo se abre desde la consola de un armario de enlace, no desde casa.")
    if sub == "abrir":
        return _open(c, player, relay, minute)
    if sub == "unirse":
        return _join(c, player, relay, rest[0]) if rest else i18n.t("Uso: circulo unirse <código>")
    return i18n.t(HELP)


HELP = """Círculo de dos (con otra persona, cada uno en un armario):
  circulo abrir · circulo lista · circulo unirse <código>
  circulo publicar <valor> · circulo ver · circulo enlazar <clave> · circulo salir
  powmod <base> <exponente> <módulo>      la calculadora del intercambio"""

MAN = {
    "dh": """dh · intercambio de claves Diffie-Hellman

Dos personas quieren una clave común sin enviarla nunca. Hay dos números
públicos: un primo p y una base g.
1. Cada una elige un secreto: a y b (el armario te da el tuyo).
2. Cada una publica su valor: A = g^a mod p, B = g^b mod p.
3. Cada una eleva el valor de la otra a su propio secreto:
   B^a mod p  y  A^b mod p. Salen el mismo número: (g^b)^a = (g^a)^b.
Quien solo ve p, g, A y B no puede sacar la clave sin resolver un logaritmo
discreto. Con primos de verdad (de cientos de cifras) eso es imposible.""",
    "powmod": """powmod <base> <exponente> <módulo>

Calcula base^exponente mod módulo sin números gigantes. Para tu valor público:
powmod g <tu secreto> p. Para la clave: powmod <valor de la otra persona> <tu secreto> p.""",
    "circulo": """circulo · enlaces sin dueño

  abrir                  empieza un círculo en este armario y te da tu secreto
  lista                  los círculos que esperan a su segunda persona
  unirse <código>        únete desde OTRO armario
  publicar <valor>       tu valor público (g^secreto mod p)
  ver                    cómo va: quién está y qué ha publicado
  enlazar <clave>        confirma la clave compartida; los dos en menos de 10 minutos
  salir                  deja el círculo""",
}
MAN_ALIASES = {"diffie-hellman": "dh", "diffie": "dh", "circle": "circulo", "circulos": "circulo",
               "círculo": "circulo"}


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM duo_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "DUO_OPENED", "text": text, "source": player, "learned_minute": minute} for text, minute in rows]
