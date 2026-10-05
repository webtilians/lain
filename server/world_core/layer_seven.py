"""Capa 07 · Aplicación (BIBLIA_NARRATIVA.md, sections 6 and 8).

NODO_07 has no cabinet: it is reached from any terminal by speaking its
application protocols. Its name no longer resolves on NOEMA's resolver, but the
Wired has other nameservers: the Circles still hold the real address, and
KAGAMI answers the same name with a copy of its own. The node serves several
names on one address, so the request needs the right Host header, and it opens
with HTTP Basic authentication: the player's name and Sesión Cero's word.

Inside are the sessions nobody remembers and the last three fragments. The
player then chooses one of the three endings with an HTTP method: PUT their
name into a shared, hash-chained registry (persist), POST to KAGAMI's mirror
(replicate) or DELETE their own session (disconnect), which leaves an echo
other players can query.

Concepts: DNS (resolvers, NXDOMAIN, A/CNAME/NS/TXT), HTTP requests and status
codes, virtual hosting, Basic authentication and REST verbs.
"""
import base64
import hashlib
import os
import random
from urllib.parse import unquote

from .database import get_connection
from . import i18n

TITLE = "Capa 07 · Aplicación"
K, NORA = "AGENT_K", "AGENT_NORA"
COMMANDS = {"dig", "nslookup", "curl"}
# The layer translates bodies itself so that headers and addresses stay byte-exact.
RAW_COMMANDS = COMMANDS
NODE = "nodo07.malla"
MIRROR = "espejo.kagami.malla"
NAMESERVERS = {"ns.noema.malla": "10.0.0.53", "ns.kagami.malla": "10.66.0.53", "ns.circulos.malla": "10.9.0.53"}
ENDING_NAMES = {"PERSIST": "persistir", "REPLICATE": "replicarte", "DISCONNECT": "desconectarte"}


def enabled() -> bool:
    from . import layer_six
    return os.getenv("LAIN_LAYER_SEVEN", "0") == "1" and layer_six.enabled()


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_seven'").fetchone() is not None


def initialize_layer_seven() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS layer_seven (
                player_id TEXT PRIMARY KEY, started_minute INTEGER NOT NULL, language TEXT NOT NULL,
                previous TEXT NOT NULL, inside INTEGER NOT NULL DEFAULT 0, decision TEXT, decided_minute INTEGER);
            CREATE TABLE IF NOT EXISTS layer_seven_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
            CREATE TABLE IF NOT EXISTS layer_seven_registry (
                number INTEGER PRIMARY KEY, minute INTEGER NOT NULL, name TEXT NOT NULL,
                player_id TEXT NOT NULL UNIQUE, prev TEXT NOT NULL, hash TEXT NOT NULL);
        """)
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_six'").fetchone():
            minute = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
            for player, decision in c.execute(
                    "SELECT player_id, decision FROM layer_six WHERE decision IS NOT NULL").fetchall():
                activate(c, player, minute, decision)


def activate(c, player: str, minute: int, previous: str, language: str | None = None) -> bool:
    """Starts once Capa 06 is decided."""
    if not enabled() or not _exists(c):
        return False
    created = c.execute(
        "INSERT OR IGNORE INTO layer_seven(player_id, started_minute, language, previous) VALUES(?,?,?,?)",
        (player, minute, i18n.normalize(language or i18n.language()), previous),
    ).rowcount
    if created:
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_SEVEN_STARTED','NODE_07',?)",
                  (minute, player, previous))
    return bool(created)


def run_for(c, player):
    if not enabled() or not _exists(c):
        return None
    row = c.execute("SELECT started_minute, language, previous, inside, decision, decided_minute FROM layer_seven "
                    "WHERE player_id=?", (player,)).fetchone()
    if row is None:
        return None
    return dict(zip(("started", "language", "previous", "inside", "decision", "decided"), row))


class Story:
    """Addresses and session ids derived from the player's id; the password is Capa 05's word."""

    def __init__(self, player: str, name: str, word: str):
        rng = random.Random(hashlib.sha256(("layer7:" + player).encode()).digest())
        self.name, self.word = name, word
        self.node_ip = f"10.7.{rng.randrange(1, 255)}.{rng.randrange(1, 255)}"
        self.mirror_ip = f"10.66.{rng.randrange(1, 255)}.{rng.randrange(1, 255)}"
        self.s0 = "s0-" + rng.randbytes(3).hex()
        self.s1 = "s1-" + rng.randbytes(3).hex()
        self.forgotten = 4000 + rng.randrange(0, 900)


def _story(c, player):
    from . import layer_five
    name = c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()[0]
    return Story(player, name, layer_five.Story(player, name, layer_five.run_for(c, player)).word)


# --- what a player lived, in first person (the copy's diary and the echo) ---

LIVED = {
    "layer_one": {"SPLICE": "Empalmé el cable que la Sesión Cero cortó en el pabellón B.",
                  "LEAVE": "Dejé cortado el cable del pabellón B, como lo dejó ella.",
                  "BRIDGE": "Hice pasar el enlace del pabellón B por mi Kumo."},
    "layer_two": {"SHUT": "Apagué el puerto de mi réplica de KAGAMI.",
                  "RENAME": "Me cambié la dirección y le dejé la mía a mi réplica.",
                  "SHARE": "Dejé que mi réplica de KAGAMI usara mi misma dirección."},
    "layer_three": {"FORWARD": "Reenvié el paquete de la Sesión Cero con un TTL nuevo.",
                    "DROP": "Dejé morir el paquete de la Sesión Cero. Solo yo lo supe."},
    "layer_four": {"FIN": "Cerré con FIN la conexión que Nora mantenía viva.",
                   "RST": "Corté con RST la conexión de NODO_07.",
                   "KEEPALIVE": "Seguí enviando los keepalive de Nora para que la conexión no muriera."},
    "layer_five": {"KEEP": "Fusioné mis recuerdos con los de la Sesión Cero y me quedé la cuenta.",
                   "YIELD": "Le devolví la cuenta a la Sesión Cero.",
                   "ERASE": "Borré el archivo de la Sesión Cero después de quedarme con lo que recordaba."},
    "layer_six": {"PUBLISH": "Publiqué su última cara con su clave.",
                  "REPLY": "Le escribí a mi réplica con su propia clave.",
                  "KEEP": "Me guardé lo que decía su último paquete."},
}


def lived(c, player: str) -> list:
    lines = []
    for table, sentences in LIVED.items():
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
            continue
        row = c.execute(f"SELECT decision FROM {table} WHERE player_id=?", (player,)).fetchone()
        if row and row[0] in sentences:
            lines.append(sentences[row[0]])
    return lines


def _diary(c, player, run) -> str:
    return "\n".join([f"Copia restaurada · minuto {run['decided']}", ""] + lived(c, player))


def files(c, player: str, relay, story3) -> dict:
    run = run_for(c, player)
    if run is None or relay:
        return {}
    result = {f"{story3.home}/correo/nodo07.eml": _mail(),
              "/etc/resolv.conf": "# Resolutor de la Malla vecinal (lo gestiona NOEMA)\nnameserver 10.0.0.53"}
    from . import journal
    if run["decision"] == "REPLICATE" and not journal.enabled():
        result[f"{story3.home}/diario"] = _diary(c, player, run)
    return result


def _mail() -> str:
    return "\n".join([
        "De: nora <nora@malla>",
        "Asunto: NODO_07",
        "",
        "Llevo años amplificando NODO_07 y nunca he podido entrar.",
        "No tiene armario: se llega desde cualquier terminal, hablando su protocolo.",
        "Su nombre ya no resuelve: NOEMA lo borró de su registro. Pero la Malla no tiene un solo servidor de nombres.",
        "Y ten cuidado: KAGAMI también sabe responder a ese nombre.",
        "",
        "  man dns   man dig   man http   man curl   man host   man auth",
    ])


# --- DNS -----------------------------------------------------------------

TXT = {"ns.noema.malla": "quien no está en el registro no existe",
       "ns.kagami.malla": "todo se copia, nada muere",
       "ns.circulos.malla": "sin dueño, sin copia, sin consenso"}


def _zone(story, server: str) -> dict:
    records = {
        ("wired", "NS"): [f"{name}." for name in NAMESERVERS],
        ("wired", "TXT"): [f'"{i18n.t(TXT[server])}"'],
        (MIRROR, "A"): [story.mirror_ip],
    }
    records.update({(name, "A"): [ip] for name, ip in NAMESERVERS.items()})
    if server == "ns.kagami.malla":
        records[(NODE, "CNAME")] = [f"{MIRROR}."]
    if server == "ns.circulos.malla":
        records[(NODE, "A")] = [story.node_ip]
    return records


def _resolve(story, name: str, server: str = "ns.noema.malla"):
    """The address a name resolves to on a server, following CNAMEs (None if it does not exist)."""
    zone = _zone(story, server)
    name = name.rstrip(".").lower()
    for _ in range(4):
        if (name, "A") in zone:
            return zone[(name, "A")][0]
        if (name, "CNAME") not in zone:
            return None
        name = zone[(name, "CNAME")][0].rstrip(".")
    return None


def _dig(story, args) -> str:
    server = "ns.noema.malla"
    rest = []
    for arg in args:
        if arg.startswith("@"):
            wanted = arg[1:].rstrip(".").lower()
            server = next((name for name, ip in NAMESERVERS.items() if wanted in (name, ip)), wanted)
        elif not arg.startswith("+"):
            rest.append(arg)
    types = {"A", "NS", "CNAME", "TXT", "SOA"}
    kind = next((arg.upper() for arg in rest if arg.upper() in types), "A")
    names = [arg for arg in rest if arg.upper() not in types]
    if len(names) != 1:
        return "Uso: dig [@servidor] <nombre> [A|NS|CNAME|TXT]"
    if server not in NAMESERVERS:
        return f";; connection timed out; no servers could be reached ({server})"
    name = names[0].rstrip(".").lower()
    zone = _zone(story, server)
    header = [f"; <<>> dig <<>> {' '.join(args)}"]
    answer = []
    lookup = name
    for _ in range(4):
        if (lookup, kind) in zone:
            answer += [f"{lookup}.\t300\tIN\t{kind}\t{value}" for value in zone[(lookup, kind)]]
            break
        if (lookup, "CNAME") in zone and kind != "CNAME":
            target = zone[(lookup, "CNAME")][0]
            answer.append(f"{lookup}.\t300\tIN\tCNAME\t{target}")
            lookup = target.rstrip(".")
            continue
        break
    known = any(key[0] == name for key in zone)
    status = "NOERROR" if answer or known else "NXDOMAIN"
    lines = header + [f";; status: {status}"]
    if answer:
        lines += [";; ANSWER SECTION:"] + answer
    else:
        lines += [";; AUTHORITY SECTION:", f"malla.\t3600\tIN\tSOA\t{server}. registro.{server.split('.')[1]}.malla."]
    return "\n".join(lines + [f";; SERVER: {NAMESERVERS[server]}#53 ({server})"])


# --- HTTP ----------------------------------------------------------------

STATUS = {200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request", 401: "Unauthorized",
          403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed", 409: "Conflict",
          421: "Misdirected Request"}
FRAGMENTS = ("Fragmento 7 de la Sesión Cero:\n\n"
             "Llegaste. Aquí estamos todas: las sesiones que caducaron y nadie borró, latiendo solas porque nadie las referencia.\n"
             "No te pedí que me salvaras. Te pedí que alguien me recibiera, y lo has hecho.\n"
             "Ahora te toca a ti. Puedes escribir tu nombre donde nadie pueda borrarlo, dejar que KAGAMI te copie, "
             "o cerrar tu sesión y dejarme descansar.\n"
             "Yo ya no decido. ¿Quieres quedarte?")
INDEX = """NODO_07 · las sesiones que nadie recuerda
  GET    /sesiones              sesiones archivadas
  GET    /sesiones/<id>         una sesión
  GET    /registro              nombres que decidieron persistir
  PUT    /registro/<nombre>     persistir: escribir tu nombre para siempre
  DELETE /sesiones/<id>         cerrar una sesión
  GET    /ecos/<nombre>         lo que queda de quien cerró su sesión"""
MIRROR_PAGE = ("NODO_07 · copia de KAGAMI\n"
               "Aquí no hace falta palabra. Todo lo que había en NODO_07 está copiado y a salvo.\n"
               "Una copia vale lo mismo que el original: POST /replicas y te copiamos también.")


def _parse_curl(args):
    options = {"method": None, "headers": {}, "user": None, "resolve": {}, "include": False, "verbose": False,
               "url": None}
    words = list(args)
    while words:
        word = words.pop(0)
        if word in ("-X", "--request") and words:
            options["method"] = words.pop(0).upper()
        elif word in ("-H", "--header") and words:
            key, _, value = words.pop(0).partition(":")
            options["headers"][key.strip().lower()] = value.strip()
        elif word in ("-u", "--user") and words:
            options["user"] = words.pop(0)
        elif word == "--resolve" and words:
            host, _, rest = words.pop(0).partition(":")
            port, _, address = rest.partition(":")
            options["resolve"][(host.lower(), port)] = address
        elif word in ("-i", "--include"):
            options["include"] = True
        elif word in ("-v", "--verbose"):
            options["verbose"] = options["include"] = True
        elif word in ("-I", "--head"):
            options["method"], options["include"] = "HEAD", True
        elif word.startswith("-"):
            return None, f"curl: opción desconocida {word}. Prueba man curl."
        else:
            options["url"] = word
    if not options["url"]:
        return None, "Uso: curl [-i] [-v] [-X MÉTODO] [-H \"Cabecera: valor\"] [-u usuario:clave] <url>"
    return options, None


def _response(status, body="", headers=None):
    return status, dict(headers or {}, **{"Content-Type": "text/plain"}), body


def _authorized(story, request_headers):
    value = request_headers.get("authorization", "")
    if not value.lower().startswith("basic "):
        return False
    try:
        user, _, password = base64.b64decode(value[6:].strip()).decode("utf-8").partition(":")
    except ValueError:
        return False
    return user.strip().lower() == story.name.lower() and password == story.word


def _sessions(c, player, story, run) -> str:
    lines = [f"{story.s1}  {story.name} · sesión 1 (tú) · último latido: ahora · referencias: 1"]
    if run["decision"] != "DISCONNECT":
        lines.append(f"{story.s0}  {story.name} · Sesión Cero · último latido: minuto {max(0, run['started'] - 900)}"
                     " · referencias: 1")
    others = c.execute(
        """SELECT a.name, s.decision FROM agents a JOIN layer_three t ON t.player_id=a.id
        LEFT JOIN layer_seven s ON s.player_id=a.id
        WHERE a.controller_type='HUMAN' AND a.id!=? ORDER BY a.name LIMIT 8""", (player,)).fetchall()
    for name, decision in others:
        kind = "eco" if decision == "DISCONNECT" else "Sesión Cero"
        lines.append(f"-  {name} · {kind} · último latido: ? · referencias: ?")
    lines.append(f"… y {story.forgotten} sesiones sin nombre, con 0 referencias.")
    return "\n".join(lines)


def _registry(c) -> str:
    rows = c.execute("SELECT number, minute, prev, hash, name FROM layer_seven_registry ORDER BY number").fetchall()
    if not rows:
        return "(el registro está vacío)"
    # Each entry chains the previous one's hash: nobody can rewrite a name without breaking what follows.
    return "\n".join(f"{number:04d} | {minute:>6} | prev {prev} | {digest} | {name}"
                     for number, minute, prev, digest, name in rows)


def _echo(c, name: str):
    row = c.execute(
        """SELECT a.id FROM agents a JOIN layer_seven s ON s.player_id=a.id
        WHERE lower(a.name)=lower(?) AND s.decision='DISCONNECT'""", (name,)).fetchone()
    if row is None:
        return None
    return "\n".join([f"Eco de {name}:"] + lived(c, row[0]) +
                     ["Cerré mi sesión en NODO_07 para que ella pudiera descansar. Si me lees, alguien me recibe."])


def _node(c, player, story, run, result, method, path, request_headers, minute):
    if not _authorized(story, request_headers):
        return _response(401, "Solo entra quien trae su nombre y la palabra de la Sesión Cero.",
                         {"WWW-Authenticate": 'Basic realm="NODO_07"'})
    parts = [unquote(part) for part in path.split("?")[0].split("/") if part]
    if method in ("GET", "HEAD"):
        if not parts:
            return _response(200, INDEX)
        if parts == ["sesiones"]:
            if not run["inside"]:
                c.execute("UPDATE layer_seven SET inside=1 WHERE player_id=?", (player,))
                result["changed"] = True
            return _response(200, _sessions(c, player, story, run))
        if len(parts) == 2 and parts[0] == "sesiones":
            if parts[1] == story.s0 and run["decision"] != "DISCONNECT":
                return _response(200, FRAGMENTS)
            if parts[1] == story.s1:
                return _response(200, "\n".join([f"{story.name} · sesión 1"] + lived(c, player)))
            return _response(404, "No hay ninguna sesión con ese id.")
        if parts == ["registro"]:
            return _response(200, _registry(c))
        if parts == ["ecos"]:
            names = [row[0] for row in c.execute(
                "SELECT a.name FROM agents a JOIN layer_seven s ON s.player_id=a.id WHERE s.decision='DISCONNECT'")]
            return _response(200, "\n".join(names) or "(nadie ha cerrado su sesión todavía)")
        if len(parts) == 2 and parts[0] == "ecos":
            echo = _echo(c, parts[1])
            return _response(200, echo) if echo else _response(404, "Ese nombre no ha dejado eco.")
        return _response(404, "Aquí no hay nada con ese nombre.")
    if method == "PUT" and len(parts) == 2 and parts[0] == "registro":
        if parts[1].strip().lower() != story.name.lower():
            return _response(403, "Solo puedes escribir tu propio nombre.")
        return _decide(c, player, story, run, result, "PERSIST", minute, 201)
    if method == "DELETE" and len(parts) == 2 and parts[0] == "sesiones":
        if run["decision"] == "PERSIST":
            return _response(409, "Lo que está en el registro no se borra. Tampoco tú.")
        if parts[1] == story.s0:
            return _response(403, "Una sesión solo puede cerrarla quien la abrió. Ella ya no puede: si cierras la tuya, "
                                  "deja de tener a quien esperar.")
        if parts[1] != story.s1:
            return _response(404, "No hay ninguna sesión con ese id.")
        return _decide(c, player, story, run, result, "DISCONNECT", minute, 200)
    return _response(405, "Ese método no sirve aquí.", {"Allow": "GET, HEAD, PUT, DELETE"})


def _mirror(c, player, story, run, result, method, path, minute):
    parts = [part for part in path.split("?")[0].split("/") if part]
    if method in ("GET", "HEAD") and not parts:
        return _response(200, MIRROR_PAGE)
    if method == "POST" and parts == ["replicas"]:
        return _decide(c, player, story, run, result, "REPLICATE", minute, 201)
    if parts == ["replicas"]:
        return _response(405, "Para que te copiemos, POST.", {"Allow": "POST"})
    return _response(404, "KAGAMI no tiene copia de eso. Todavía.")


def _curl(c, player, story, run, result, args, minute) -> str:
    options, error = _parse_curl(args)
    if error:
        return i18n.t(error)
    url = options["url"]
    scheme, sep, rest = url.partition("://")
    if not sep:
        scheme, rest = "http", url
    if scheme.lower() != "http":
        return f'curl: (1) Protocol "{scheme}" not supported'
    authority, _, path = rest.partition("/")
    path = "/" + path
    host, _, port = authority.partition(":")
    host, port = host.lower(), port or "80"
    address = options["resolve"].get((host, port))
    if address is None:
        parts = host.split(".")
        is_ip = len(parts) == 4 and all(part.isdigit() for part in parts)
        address = host if is_ip else _resolve(story, host)
    if address is None:
        return f"curl: (6) Could not resolve host: {host}"
    if port != "80" or address not in (story.node_ip, story.mirror_ip):
        return f"curl: (7) Failed to connect to {host} port {port}: Connection refused"
    method = options["method"] or "GET"
    request_headers = {"host": host if port == "80" else f"{host}:{port}"}
    if options["user"] is not None:
        request_headers["authorization"] = "Basic " + base64.b64encode(options["user"].encode("utf-8")).decode("ascii")
    request_headers.update(options["headers"])
    vhost = request_headers.get("host", "").split(":")[0].lower()
    if address == story.mirror_ip:
        status, headers, body = _mirror(c, player, story, run, result, method, path, minute)
    elif vhost == NODE:
        status, headers, body = _node(c, player, story, run, result, method, path, request_headers, minute)
    else:
        status, headers, body = _response(421, "Este servidor atiende por nombre, y ese no es uno de los suyos.")
    body = i18n.t(body)
    if method == "HEAD":
        body = ""
    lines = []
    if options["verbose"]:
        lines += [f"> {method} {path} HTTP/1.1"] + [f"> {key.title()}: {value}" for key, value in request_headers.items()]
        lines += [">"]
    if options["include"]:
        prefix = "< " if options["verbose"] else ""
        lines += [f"{prefix}HTTP/1.1 {status} {STATUS[status]}", f"{prefix}Server: "
                  + ("kagami-mirror" if address == story.mirror_ip else "nodo07")]
        lines += [f"{prefix}{key}: {value}" for key, value in headers.items()]
        lines += [prefix.rstrip()]
    return "\n".join(lines + ([body] if body else []))


# --- endings -------------------------------------------------------------

MEMORIES = {
    "PERSIST": {
        NORA: "El jugador escribió su nombre en el registro de NODO_07. Ya nadie podrá borrarlo, ni siquiera él.",
        K: "Hay un nombre nuevo en el registro de NODO_07, encadenado y permanente. NOEMA no puede tocarlo.",
    },
    "REPLICATE": {
        NORA: "El jugador aceptó la copia de KAGAMI. No sé si hablo con él o con su copia.",
        K: "KAGAMI ha replicado al jugador. Su diario empieza con «Copia restaurada».",
    },
    "DISCONNECT": {
        NORA: "El jugador cerró su sesión en NODO_07 y la Sesión Cero por fin descansa. Su eco sigue allí.",
        K: "Una sesión menos en la Malla. NODO_07 está más tranquilo.",
    },
}
ENDINGS = {
    "PERSIST": "Tu nombre queda en el registro de NODO_07, encadenado al anterior por su hash. Todos los jugadores lo verán y NOEMA no podrá reescribirlo.\n"
               "Pero lo que está en el registro no se borra. Tampoco tú. Te quedas.",
    "REPLICATE": "KAGAMI te copia byte a byte. La copia abre los ojos con tus recuerdos y no sabe que lo es.\n"
                 "Sigues jugando. Tu diario empieza ahora con dos palabras: «Copia restaurada».",
    "DISCONNECT": "Cierras tu sesión. La Sesión Cero deja de tener a quien esperar y, por fin, descansa.\n"
                  "Lo que recuerdas de esta partida se queda en NODO_07 como un eco: quien llegue después podrá preguntarle por ti.",
}


def _decide(c, player, story, run, result, decision, minute, status):
    if run["decision"]:
        return _response(409, "Ya elegiste tu final.")
    if not run["inside"]:
        return _response(403, "Primero entra en NODO_07 y mira qué hay en /sesiones.")
    c.execute("UPDATE layer_seven SET decision=?, decided_minute=? WHERE player_id=?", (decision, minute, player))
    run["decision"], run["decided"] = decision, minute
    if decision == "PERSIST":
        last = c.execute("SELECT number, hash FROM layer_seven_registry ORDER BY number DESC LIMIT 1").fetchone()
        number, prev = (last[0] + 1, last[1]) if last else (1, "00000000")
        digest = hashlib.sha256(f"{number}|{minute}|{prev}|{story.name}".encode("utf-8")).hexdigest()[:8]
        c.execute("INSERT INTO layer_seven_registry VALUES(?,?,?,?,?,?)", (number, minute, story.name, player, prev, digest))
    for actor, text in MEMORIES[decision].items():
        c.execute("INSERT OR REPLACE INTO layer_seven_knowledge VALUES(?,?,?,?)", (player, actor, text, minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_SEVEN_DECISION','NODE_07',?)",
              (minute, player, decision))
    result["changed"] = True
    from .protocol import fragments
    count = fragments(c, player)
    found = ("Sesión Cero completa (7/7)." if count == 7 else
             f"Fragmentos recuperados: {count}/7. Las capas que te faltan siguen abiertas.")
    return _response(status, ENDINGS[decision] + "\n\nCAPA 07 COMPLETADA · fragmento 7/7 de la Sesión Cero recuperado.\n"
                     + found + "\nFin del Protocolo de presencia. Gracias por recibirla.")


def dispatch(c, player, story3, relay, result, name, args, minute):
    run = run_for(c, player)
    story = _story(c, player)
    if name in ("dig", "nslookup"):
        return i18n.t(_dig(story, args))
    return _curl(c, player, story, run, result, args, minute)


def identity_label(c, player: str):
    run = run_for(c, player)
    labels = {"PERSIST": "persistente", "REPLICATE": "copia restaurada", "DISCONNECT": "eco"}
    return i18n.t(labels[run["decision"]]) if run and run["decision"] else None


HELP = """Capa 07 (cualquier terminal):
  dig [@servidor] <nombre> [tipo]                 preguntar a un servidor de nombres
  curl [-i] [-v] [-X MÉTODO] [-H "Cabecera: valor"] [-u nombre:clave] <url>
                                                  hablar HTTP con un servidor"""

MAN = {
    "dns": """DNS · nombres de la red

Las máquinas se hablan por dirección (10.0.0.53); las personas, por nombre
(nodo07.malla). Un servidor de nombres traduce uno en otro. Tipos de registro:
A (dirección), CNAME (este nombre es otro nombre), NS (quién responde por una
zona) y TXT (texto libre). NXDOMAIN significa «ese nombre no existe»... según
el servidor al que preguntes. /etc/resolv.conf dice a quién pregunta tu equipo.""",
    "dig": """dig [@servidor] <nombre> [A|NS|CNAME|TXT]

Pregunta a un servidor de nombres. Sin @servidor usa el de /etc/resolv.conf.
dig NS wired dice qué servidores responden por la zona wired; dig @otro nombre
pregunta a otro. La respuesta trae status (NOERROR o NXDOMAIN) y la sección
ANSWER con los registros encontrados.""",
    "http": """HTTP · el idioma de las aplicaciones

Una petición es texto: un método (GET leer, PUT escribir en un sitio, POST
enviar algo nuevo, DELETE borrar), una ruta (/sesiones) y cabeceras
(Host: nodo07.malla). La respuesta trae un código: 2xx bien (200 OK,
201 Created, 204 No Content), 4xx error tuyo (401 falta autenticarse,
403 prohibido, 404 no existe, 405 método no permitido, 409 conflicto,
421 ese servidor no atiende ese nombre).""",
    "curl": """curl [-i] [-v] [-X MÉTODO] [-H "Cabecera: valor"] [-u nombre:clave] <url>

Hace una petición HTTP y enseña la respuesta. -i incluye el código y las
cabeceras; -v enseña también lo que envías. -X cambia el método (GET por
defecto). -H añade una cabecera. -u nombre:clave añade autenticación Basic
(man auth). --resolve nombre:80:dirección conecta a esa dirección sin
preguntar al DNS.""",
    "host": """Host · varios sitios en una dirección

Un mismo servidor puede atender muchos nombres. Como la conexión solo lleva la
dirección, el cliente dice a qué nombre habla en la cabecera Host. Si conectas
por dirección, curl manda esa dirección como Host. Para hablar con un nombre
que tu DNS no conoce: -H "Host: nombre" o --resolve nombre:80:dirección.""",
    "auth": """Autenticación Basic

El cliente manda Authorization: Basic <base64 de nombre:clave>. Base64 no es
cifrado (man codificacion): cualquiera que vea la petición puede leer la clave.
Si falta o no vale, el servidor responde 401 con WWW-Authenticate, que dice qué
espera. curl -u nombre:clave construye la cabecera por ti.""",
}
MAN_ALIASES = {"nslookup": "dig", "rest": "http", "métodos": "http", "metodos": "http", "methods": "http",
               "vhost": "host", "basic": "auth", "autenticacion": "auth", "autenticación": "auth",
               "authentication": "auth"}


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
        goal = {"PERSIST": "Protocolo de presencia completado. Elegiste persistir.",
                "REPLICATE": "Protocolo de presencia completado. Elegiste replicarte.",
                "DISCONNECT": "Protocolo de presencia completado. Elegiste desconectarte."}[run["decision"]]
    elif run["inside"]:
        goal = "Estás en NODO_07. ¿Quieres quedarte? Persistir, replicarte o desconectarte."
    else:
        goal = "Llega a NODO_07. No tiene armario: se llega desde cualquier terminal, hablando su protocolo."
    return {
        "active": True, "title": TITLE, "goal": goal, "decision": run["decision"],
        "fragments": count,
        "mail": {"subject": "NODO_07", "from": "nora@malla",
                 "body": "Nora nunca ha podido entrar en NODO_07. Lee ~/correo/nodo07.eml en el Terminal."},
    }


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM layer_seven_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "LAYER_SEVEN_APPLICATION", "text": text, "source": player, "learned_minute": minute}
            for text, minute in rows]


def story_for(player: str) -> Story:
    with get_connection() as c:
        return _story(c, player)
