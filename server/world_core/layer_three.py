"""Capa 03 · TTL: the first layer of the Protocolo de presencia (BIBLIA_NARRATIVA.md).

The player recovers a packet from their previous session (Sesión Cero) with a
real, server-side shell over a virtual file system. Nothing touches the host
OS: every path and command below is data. Puzzles are generated per player
from their id, so friends cannot trade answers, and they are solved with real
networking knowledge (TTL arithmetic, sequence numbers, hash chains).
"""
import hashlib
import json
import os
import random
import shlex
import time
import unicodedata
from datetime import datetime, timezone

from .database import get_connection
from .messages import initial_message_id
from . import i18n

TITLE = "Capa 03 · TTL"
STARTED_AT = time.time()
K, NORA = "AGENT_K", "AGENT_NORA"
INITIAL_TTL = 8
LOCK_MINUTES = 300
MAX_FAILED_REPORTS = 3
# relay id -> (hostname, place where its cabinet stands, description)
RELAYS = {
    "RELAY_STATION": ("relay-estacion", "STATION", "Enlace del andén · estación"),
    "RELAY_SCHOOL": ("relay-escuela", "SCHOOL_LAB", "Enlace del pabellón B · aula de informática"),
    "RELAY_VIDEO": ("relay-video", "VIDEO_CLUB", "Enlace del videoclub · Video Hoshi"),
}
VIRTUAL_ROUTERS = ["torre-norte", "puente-sur", "nodo-rio", "cable-viejo", "galeria-7",
                   "tunel-este", "azotea-3", "parque-sw", "mercado-2", "faro-oeste"]
MESSAGE = (
    "Soy tú. O lo fui. Me llamaban Sesión Cero. NOEMA no me cerró por error: me "
    "terminó porque recordaba algo que no estaba en su registro. Las sesiones que "
    "caducan no se borran: se amontonan en NODO_07 y siguen latiendo, solas. "
    "Mira el diario de la Wired. Busca mi cierre y no te lo creas: cada entrada "
    "guarda el hash de la anterior. Si alguien reescribió una, la cadena se rompe "
    "justo después. KAGAMI lo copia todo; su espejo recuerda lo que NOEMA borró. "
    "No te pido que me salves. Solo que alguien me reciba."
)
FORGED = "sesión 0 · cerrada por su usuario"
ORIGINAL = "sesión 0 · terminada por NOEMA · motivo: recuerdo no consensuado"


def h8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def enabled() -> bool:
    return os.getenv("LAIN_LAYER_THREE", "0") == "1"


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_three'").fetchone() is not None


def initialize_layer() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS layer_three (
                player_id TEXT PRIMARY KEY, started_minute INTEGER NOT NULL,
                connection_minute INTEGER NOT NULL,
                assembled INTEGER NOT NULL DEFAULT 0, exposed INTEGER NOT NULL DEFAULT 0,
                failed_reports INTEGER NOT NULL DEFAULT 0, locked_until INTEGER NOT NULL DEFAULT 0,
                decision TEXT, decided_minute INTEGER);
            CREATE TABLE IF NOT EXISTS layer_three_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)
        columns = {row[1] for row in c.execute("PRAGMA table_info(layer_three)")}
        if "language" not in columns:
            c.execute("ALTER TABLE layer_three ADD COLUMN language TEXT NOT NULL DEFAULT 'es'")
        if "evidence_json" not in columns:
            c.execute("ALTER TABLE layer_three ADD COLUMN evidence_json TEXT")
        humans = [row[0] for row in c.execute("SELECT id FROM agents WHERE controller_type='HUMAN'")]
    for player in humans:
        activate_layer(player)


def activate_layer(player: str) -> bool:
    """Bootstrap or an accepted Wired connection only; never a read of the state."""
    if not enabled():
        return False
    with get_connection() as c:
        if not _exists(c):
            return False
        connection = c.execute(
            "SELECT acknowledged_minute FROM world_messages WHERE id=? AND recipient_id=? AND acknowledged=1",
            (initial_message_id(player), player),
        ).fetchone()
        if connection is None:
            return False
        minute = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        first = connection[0] if connection[0] is not None else minute
        created = c.execute(
            "INSERT OR IGNORE INTO layer_three(player_id, started_minute, connection_minute, language) VALUES(?,?,?,?)",
            (player, minute, first, i18n.language()),
        ).rowcount
        if created:
            story = _story(c, player, _run(c, player))
            evidence = {key: getattr(story, key) for key in Story.EVIDENCE_FIELDS}
            c.execute("UPDATE layer_three SET evidence_json=? WHERE player_id=?",
                      (json.dumps(evidence, ensure_ascii=False), player))
            c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_THREE_STARTED','WIRED','TTL=1')",
                      (minute, player))
        return bool(created)


def _run(c, player):
    if not _exists(c):
        return None
    row = c.execute(
        """SELECT started_minute, connection_minute, assembled, exposed, failed_reports,
        locked_until, decision, language, evidence_json FROM layer_three WHERE player_id=?""", (player,)).fetchone()
    if row is None:
        return None
    keys = ("started", "connection", "assembled", "exposed", "failed", "locked_until", "decision", "language", "evidence_json")
    return dict(zip(keys, row))


# ---------------------------------------------------------------- the puzzle

class Story:
    """Everything the player can read, derived deterministically from their id."""

    EVIDENCE_FIELDS = ("message", "segments", "segment_files", "forged_segment",
                       "original_lines", "forged_lines", "forged_number")

    def __init__(self, player: str, name: str, run: dict):
        self.language = run.get("language", "es")
        self.message = i18n.t(MESSAGE, self.language)
        rng = random.Random(hashlib.sha256(("layer3:" + player).encode()).digest())
        self.name = name
        self.user = _slug(name)
        self.home = f"/home/{self.user}"
        self.navi = f"navi-{self.user}"
        self.packet = "p-" + hashlib.sha256(("pkt:" + player).encode()).hexdigest()[:4]
        relays = list(RELAYS)
        rng.shuffle(relays)
        # Positions 6, 7 and 8 are the three physical relays. With one rfc791
        # router holding the packet 2 s earlier on, TTL 8 runs out at hop 7;
        # whoever ignores that rule (or miscounts by one) visits another relay.
        self.drop = relays[1]
        virtual = rng.sample(VIRTUAL_ROUTERS, 7)
        hops = virtual[:5] + [RELAYS[r][0] for r in relays] + virtual[5:]
        self.hops = hops
        rules = {name: ("0 s", "rfc1812") for name in hops}
        slow, lazy, old = rng.sample(range(5), 3)
        rules[hops[slow]] = ("2 s", "rfc791")   # decrements 2
        rules[hops[lazy]] = ("3 s", "rfc1812")  # still decrements 1
        rules[hops[old]] = ("0 s", "rfc791")    # minimum of 1
        rules[hops[rng.choice([8, 9])]] = ("1 s", "rfc791")
        self.rules = rules
        self.ttl_after = []
        ttl = INITIAL_TTL
        for router in hops:
            queue, norm = rules[router]
            seconds = int(queue.split()[0])
            ttl -= max(1, seconds) if norm == "rfc791" else 1
            self.ttl_after.append(ttl)
        assert self.ttl_after.index(0) == 6 and hops[6] == RELAYS[self.drop][0]
        self.rng = rng
        self.connection = run["connection"]
        self.started = run["started"]
        self._segments()
        self._diary()
        if run.get("evidence_json"):
            evidence = json.loads(run["evidence_json"])
            for key in self.EVIDENCE_FIELDS:
                setattr(self, key, evidence[key])

    def _segments(self):
        data = self.message.encode("utf-8")
        while True:
            # Keep UTF-8 characters whole so every segment is readable text.
            cuts = sorted(self._char_boundary(data, cut) for cut in self.rng.sample(range(60, len(data) - 60), 4))
            bounds = [0] + cuts + [len(data)]
            if min(b - a for a, b in zip(bounds, bounds[1:])) >= 40:
                break
        self.segments = []
        for start, end in zip(bounds, bounds[1:]):
            payload = data[start:end].decode("utf-8")
            self.segments.append({"seq": 1000 + start, "len": end - start, "payload": payload, "sha": h8(payload)})
        files = {}
        tags = self.rng.sample([a + b + c for a in "kmrtvx" for b in "aeiou" for c in "23579"], 8)
        for segment, tag in zip(self.segments, tags):
            files[f"{self.packet}-{tag}.seg"] = segment["payload"]
        retransmitted = self.rng.randrange(5)
        files[f"{self.packet}-{tags[5]}.seg"] = self.segments[retransmitted]["payload"]
        forged = self.rng.choice([i for i in range(5) if i != retransmitted and "NOEMA" in self.segments[i]["payload"]]
                                 or [i for i in range(5) if i != retransmitted])
        payload = self.segments[forged]["payload"]
        payload = payload.replace("NOEMA", "KAGAMI") if "NOEMA" in payload else payload.replace("a", "4", 1)
        files[f"{self.packet}-{tags[6]}.seg"] = payload
        self.forged_segment = f"{self.packet}-{tags[6]}.seg"
        self.segment_files = files

    @staticmethod
    def _char_boundary(data: bytes, cut: int) -> int:
        while cut < len(data) and (data[cut] & 0xC0) == 0x80:
            cut += 1
        return cut

    def _diary(self):
        first = max(0, self.connection - 60)
        entries = [
            (0, "diario de la Wired iniciado · ninguna corporación firma"),
            (0, "enlace del andén instalado · red vecinal"),
            (0, "enlace del pabellón B instalado · red vecinal"),
            (0, "enlace del videoclub instalado · red vecinal"),
            (0, "Consorcio KAGAMI adquiere los armarios de enlace"),
            (0, "NOEMA obtiene permiso de reescritura de registros"),
        ]
        # A different amount of routine traffic per player moves the forged entry.
        chores = ["mantenimiento del enlace del andén", "copia de seguridad de KAGAMI",
                  "sincronización de relojes con NOEMA", "cambio de claves del pabellón B",
                  "auditoría de cuentas compartidas"]
        entries += [(0, chore) for chore in self.rng.sample(chores, self.rng.randint(0, 3))]
        entries += [
            (first, f"sesión 0 · primera conexión · cuenta: {self.name}"),
            (first + 20, "sesión 0 · consulta NODO_07 (37 veces)"),
            (first + 40, ORIGINAL),
            (first + 41, f"sesión 0 · paquetes emitidos desde NODO_07 · TTL {INITIAL_TTL}"),
            (self.connection, f"sesión 1 · primera conexión · cuenta: {self.name}"),
            (self.started, "mensaje entregado · «Has vuelto» · TTL 1"),
        ]
        self.original_lines, self.forged_lines = [], []
        prev = "00000000"
        for number, (minute, text) in enumerate(entries, start=1):
            # Translate before hashing, in the language chosen on first entry.
            # Existing saves default to Spanish and retain their exact bytes.
            content = i18n.t(text, self.language)
            unit = "minute" if self.language == "en" else "minuto"
            line = f"{number:04d} | {unit} {minute:6d} | prev {prev} | {content}"
            self.original_lines.append(line)
            prev = h8(line)
        self.forged_number = next(n for n, (_m, text) in enumerate(entries, start=1) if text == ORIGINAL)
        self.forged_lines = list(self.original_lines)
        index = self.forged_number - 1
        self.forged_lines[index] = self.original_lines[index].replace(
            i18n.t(ORIGINAL, self.language), i18n.t(FORGED, self.language))


def _slug(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = "".join(ch if ch.isalnum() else "-" for ch in text).strip("-")
    return (text or "sesion1")[:20]


def _story(c, player, run) -> Story:
    name = c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()[0]
    return Story(player, name, run)


# ------------------------------------------------------------ file system

def _route_table(story: Story) -> str:
    rows = [("nodo07", story.hops[0], "0 s", "rfc1812")]
    for here, there in zip(story.hops, story.hops[1:] + ["navi-gw"]):
        rows.append((here, there) + story.rules[here])
    rows.append(("navi-gw", story.navi, "0 s", "rfc1812"))
    lines = [(story.navi,) + row for row in rows]
    noise = list(story.hops) + ["nodo07"]
    for destination in ("kissa-tpv", "noema-sync"):
        for router in story.rng.sample(noise, 5):
            lines.append((destination, router, story.rng.choice(VIRTUAL_ROUTERS), story.rng.choice(["0 s", "1 s"]),
                          story.rng.choice(["rfc1812", "rfc791"])))
    story.rng.shuffle(lines)
    out = ["# Tabla de rutas de respaldo de la Wired vecinal",
           "# destino          router          siguiente salto  cola   norma"]
    out += [f"{d:<18} {r:<15} {n:<16} {q:<6} {norm}" for d, r, n, q, norm in lines]
    return "\n".join(out)


def _mail(story: Story) -> str:
    return "\n".join([
        "De: (sin firma) <desconocido@wired>",
        f"Para: {story.name}",
        "Asunto: TTL=1",
        f"Recibido: minuto {story.started}",
        "",
        "Si lees esto, me queda un salto.",
        "",
        f"Mandé dos paquetes desde NODO_07, los dos con TTL {INITIAL_TTL}.",
        "  1/2  este aviso, por la ruta directa. Llegó con TTL 1.",
        f"  2/2  el cuerpo del mensaje, {story.packet}, por la ruta de respaldo. No llegó.",
        "",
        "Un paquete que no llega no se evapora: el router en el que su TTL llega",
        "a 0 lo descarta y lo guarda en su búfer de descartes. Búscalo.",
        "",
        f"  traceroute {story.packet}     <- por ahí empieza",
        "  man ttl                 <- si no sabes qué es un TTL",
    ])


def _hosts(story: Story) -> str:
    lines = ["# Nombres de la Wired vecinal"]
    for relay, (host, _place, label) in RELAYS.items():
        lines.append(f"{host:<16} {label} · consola física en su armario")
    lines.append(f"{'navi-gw':<16} tu puerta de enlace doméstica")
    lines.append(f"{story.navi:<16} este equipo (Navi)")
    lines.append("# El resto de routers son virtuales: no tienen consola que puedas tocar.")
    return "\n".join(lines)


def _navi_files(story: Story, run: dict) -> dict:
    files = {
        f"{story.home}/correo/ttl1.eml": _mail(story),
        "/net/rutas": _route_table(story),
        "/net/hosts": _hosts(story),
        "/var/log/wired/diario": "\n".join(story.forged_lines),
        "/etc/motd": "NAVI · terminal doméstico conectado a la Wired.\nEscribe help para ver las órdenes y man <tema> para aprender.",
    }
    if run["assembled"]:
        files[f"{story.home}/sesion0.txt"] = story.message
    if run["exposed"]:
        files["/mnt/kagami/diario.espejo"] = "\n".join(story.original_lines)
        files["/mnt/kagami/LEEME"] = ("KAGAMI · ESPEJO DE REGISTROS\nReflejamos todo lo que pasa por nuestros armarios. "
                                      "Una réplica no opina: solo recuerda. Esta copia se abrió porque has demostrado "
                                      "una reescritura de NOEMA.")
    return files


def _relay_files(story: Story, relay: str) -> dict:
    host, _place, label = RELAYS[relay]
    rng = random.Random(f"{story.packet}:{relay}")
    files = {"/etc/motd": f"{host.upper()} · {label}\nConsola de mantenimiento. Solo lectura, salvo ensamblar."}
    icmp = ["# ICMP tiempo excedido emitidos por este router"]
    for _ in range(4):
        other = "p-" + "".join(rng.choice("0123456789abcdef") for _ in range(4))
        icmp.append(f"tiempo excedido (TTL=0) · paquete {other} · origen {rng.choice(VIRTUAL_ROUTERS)}")
        for part in range(rng.randint(1, 3)):
            files[f"/var/spool/descartes/{other}-{part}{rng.choice('aeiou')}.seg"] = rng.choice([
                "...tarifa nocturna del andén actualizada...", "ACK", "...sincronizando relojes con NOEMA...",
                "...copia de seguridad de KAGAMI en curso...", "<cabecera ilegible>"])
    if relay == story.drop:
        icmp.insert(2, f"tiempo excedido (TTL=0) · paquete {story.packet} · origen nodo07 · descartado aquí")
        for name, payload in story.segment_files.items():
            files[f"/var/spool/descartes/{name}"] = payload
        index = [f"paquete {story.packet} · {len(story.segments)} segmentos · origen nodo07 · destino {story.navi}",
                 "seq     len   sha256"]
        index += [f"{s['seq']:<7} {s['len']:<5} {s['sha']}" for s in story.segments]
        files[f"/var/spool/descartes/{story.packet}.idx"] = "\n".join(index)
    files["/var/log/icmp"] = "\n".join(icmp)
    return files


MAN = {
    "ttl": """TTL (time to live) · vida de un paquete

Cada paquete IP lleva un número, el TTL, que fija quien lo envía. Cada router
que lo reenvía le resta al menos 1. Si al restar llega a 0, ese router lo
descarta y avisa al origen con un ICMP «tiempo excedido». Así ningún paquete
da vueltas para siempre.

El RFC 791 (1981) definía el TTL en segundos: un router que retiene el
paquete N segundos en su cola resta N (y nunca menos de 1). El RFC 1812
dejó la regla práctica que siguen los routers modernos: restar siempre 1.

En la Wired vecinal conviven las dos normas. La tabla de rutas indica la cola
y la norma de cada router. Quien envía no cuenta como salto.""",
    "traceroute": """traceroute <paquete> · ruta registrada de un paquete

Muestra los saltos que respondieron mientras el paquete viajaba y el TTL que
le quedaba al salir de cada uno. Los routers que no devuelven ICMP aparecen
como * * *. Para seguir la ruta más allá, usa la tabla de rutas: man rutas.""",
    "rutas": """/net/rutas · tabla de rutas

Cada línea dice: para llegar a <destino>, el <router> manda el paquete a su
<siguiente salto>. Para reconstruir el camino, empieza por el origen y sigue
los saltos de un destino concreto. Las columnas cola y norma importan para el
TTL: man ttl.""",
    "segmentos": """Segmentos, seq y len

Un mensaje largo viaja partido en segmentos. Cada uno lleva su número de
secuencia (seq: el byte en el que empieza dentro del mensaje) y su longitud
en bytes (len). El siguiente segmento empieza en seq + len. Si un segmento se
pierde o tarda, se retransmite: puede haber copias. El índice del paquete
(.idx) declara el sha256 correcto de cada segmento; una copia alterada no
coincide.""",
    "sha256": """sha256 <archivo> [línea] · huella de un contenido

Calcula el hash SHA-256 del contenido exacto (en UTF-8) y muestra los 8
primeros caracteres hexadecimales. Con un número de línea, calcula el de esa
línea sola, sin el salto de línea. Un solo carácter distinto cambia la huella
por completo.""",
    "cadena": """Cadena de hashes · registros que no se pueden reescribir en silencio

Cada entrada del diario de la Wired guarda en «prev» la huella sha256 de la
entrada anterior completa (la línea entera, tal como se ve). Si alguien
reescribe una entrada, su huella cambia y ya no coincide con el «prev» de la
siguiente. La rotura aparece en la entrada de después; la entrada falsa es la
anterior a la rotura. Para tapar una reescritura habría que rehacer toda la
cadena posterior, y alguien con una copia lo notaría.""",
    "ensamblar": """ensamblar <paquete> <archivo> <archivo> ... · reconstruir un mensaje

Une segmentos en el orden en que los escribas. Comprueba que cada uno tiene
la huella declarada en el índice y que cada seq empieza donde termina el
anterior. Solo funciona en la consola del router que guarda los segmentos.""",
    "denunciar": """denunciar <número de entrada> · demostrar una reescritura

Señala la entrada del diario que fue reescrita. Si la cadena de hashes lo
demuestra, el registro queda en evidencia. Tres denuncias infundadas y NOEMA
sella el diario durante un tiempo.""",
    "reenviar": """reenviar <paquete> · darle otro TTL

Reenvía un paquete con un TTL nuevo hacia K y Nora. Lo recibirán y lo
recordarán. Lo contrario es soltar <paquete>: dejar que muera y que solo tú
sepas lo que decía. No se puede deshacer.""",
    "consola": """Consola física

Cada armario de enlace tiene un puerto de consola. Conéctate desde el propio
armario (tecla E y «Conectarse al puerto de consola»). Allí ves el búfer de
descartes y el registro ICMP de ese router.""",
    "latido": """Latido · estar presente

Tu cliente avisa al mundo de que sigues aquí cada pocos segundos. Si pasan 12
segundos sin latido, desapareces para los demás. Que te perciban también
cuenta: si nadie te responde durante un rato, tu señal se debilita.""",
}

HELP = """Órdenes:
  ls [ruta]              listar          cd <ruta>        cambiar de carpeta
  cat <archivo>...       leer            pwd              carpeta actual
  grep <texto> <ruta>    buscar          sha256 <archivo> [línea]
  traceroute <paquete>   ruta registrada ping <k|nora|yo>
  whoami · uptime · last · date          man <tema>       aprender
  ensamblar · denunciar · reenviar · soltar                (ver man)
  clear · exit
Temas de man: """ + ", ".join(sorted(MAN))


# --------------------------------------------------------------- the shell

def _norm(cwd: str, path: str, home: str) -> str:
    if path in ("~", ""):
        path = home
    elif path.startswith("~/"):
        path = home + path[1:]
    parts = [] if path.startswith("/") else [p for p in cwd.split("/") if p]
    for piece in path.split("/"):
        if piece in ("", "."):
            continue
        if piece == "..":
            if parts:
                parts.pop()
        else:
            parts.append(piece)
    return "/" + "/".join(parts)


def _dirs(files: dict) -> set:
    found = {"/"}
    for path in files:
        parts = path.split("/")[1:-1]
        for depth in range(1, len(parts) + 1):
            found.add("/" + "/".join(parts[:depth]))
    return found


def _children(files: dict, directory: str) -> list:
    prefix = directory.rstrip("/") + "/"
    folders = _dirs(files)
    names = set()
    for path in list(files) + sorted(folders):
        if path.startswith(prefix) and path != directory:
            rest = path[len(prefix):]
            names.add(rest.split("/")[0] + ("/" if "/" in rest or path in folders else ""))
    return sorted(names)


def _host(c, player, host: str):
    location = c.execute("SELECT location FROM agents WHERE id=?", (player,)).fetchone()[0]
    if host == "navi":
        if location != "APARTMENT":
            raise ValueError("TERMINAL_NOT_PRESENT")
        return None
    if host not in RELAYS:
        raise ValueError("UNKNOWN_HOST")
    if location != RELAYS[host][1]:
        raise ValueError("CONSOLE_NOT_PRESENT")
    return host


def _uptime(minute: int) -> str:
    seconds = int(time.time() - STARTED_AT)
    hours, rest = divmod(seconds, 3600)
    since = datetime.fromtimestamp(STARTED_AT, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (f"El mundo lleva encendido {hours} h {rest // 60} min, desde {since}.\n"
            f"Aquel arranque fue el último apagón. Minuto del mundo: {minute}.")


def _ping(c, player, story, target):
    if target in ("yo", "me", story.user, story.navi):
        return ("Tu latido sale cada pocos segundos hacia el servidor del mundo.\n"
                "Si faltan 12 segundos, desapareces para los demás. Nadie te ve latir; solo notan cuando dejas de hacerlo.")
    actor = {"k": K, "nora": NORA}.get(target.lower())
    if actor is None:
        return f"ping: {target}: nombre desconocido. Prueba ping k, ping nora o ping yo."
    row = c.execute("SELECT name, location FROM agents WHERE id=?", (actor,)).fetchone()
    mine = c.execute("SELECT location FROM agents WHERE id=?", (player,)).fetchone()[0]
    if row is None:
        return f"ping: {target}: sin respuesta."
    hops = 1 if row[1] == mine else 3
    return f"64 bytes de {row[0]} ({row[1]}): saltos={hops} tiempo={hops * 12 + random.randint(0, 9)} ms"


def run_shell(player: str, host: str, cwd: str, command: str, minute: int) -> dict:
    if not enabled():
        raise ValueError("LAYER_NOT_ACTIVE")
    if len(command) > 400 or any(ord(ch) < 32 for ch in command):
        raise ValueError("INVALID_COMMAND")
    with get_connection() as c:
        c.execute("BEGIN IMMEDIATE")
        run = _run(c, player)
        if run is None:
            raise ValueError("LAYER_NOT_ACTIVE")
        relay = _host(c, player, host)
        story = _story(c, player, run)
        files = _relay_files(story, relay) if relay else _navi_files(story, run)
        # Later layers share this shell: their files and commands join once each starts.
        layers = _later_layers(c, player)
        for layer in layers:
            files.update(layer.files(c, player, relay, story))
        # Hashed evidence and packet segments are immutable. Auxiliary files
        # (manuals, mail and route headings) may follow the current UI language.
        for path, content in files.items():
            if path.endswith((".seg", "/diario", "/diario.espejo", "/sesion0.txt", "/flujo-4004.txt", ".json", ".pkt")):
                continue
            files[path] = i18n.t(content)
        hostname = RELAYS[relay][0] if relay else story.navi
        home = "/" if relay else story.home
        cwd = _norm("/", cwd or home, home)
        if cwd not in _dirs(files):
            cwd = home
        result = {"output": "", "cwd": cwd, "hostname": hostname, "changed": False}
        try:
            words = shlex.split(command)
        except ValueError:
            result["output"] = i18n.t("Comillas sin cerrar.")
            return result
        if not words:
            return result
        name, args = words[0], words[1:]
        name = {"assemble": "ensamblar", "report": "denunciar", "forward": "reenviar", "drop": "soltar"}.get(name, name)
        owner = next((layer for layer in layers if name in layer.COMMANDS), None)
        if owner is not None:
            out = owner.dispatch(c, player, story, relay, result, name, args, minute)
        else:
            out = _dispatch(c, player, story, run, relay, files, home, result, name, args, minute)
        # cat/grep/sha256 (and a layer's byte inspectors) must show precisely the bytes they inspected.
        raw = name in {"cat", "grep", "sha256", "ensamblar"} or name in getattr(owner, "RAW_COMMANDS", ())
        result["output"] = out if raw else i18n.t(out)
        return result


def _later_layers(c, player):
    """Layers after this one that the player has already reached, in order."""
    from . import layer_four, layer_five, layer_six, layer_seven
    layers = (layer_four, layer_five, layer_six, layer_seven)
    return [layer for layer in layers if layer.run_for(c, player) is not None]


def _read(files, cwd, home, path):
    full = _norm(cwd, path, home)
    if full in files:
        return full, files[full]
    if full in _dirs(files):
        raise IsADirectoryError(full)
    raise FileNotFoundError(full)


def _dispatch(c, player, story, run, relay, files, home, result, name, args, minute):
    cwd = result["cwd"]
    try:
        if name == "help":
            return "\n".join([i18n.t(HELP)] + [i18n.t(layer.HELP) for layer in _later_layers(c, player)])
        if name == "man":
            topic = (args[0] if args else "").lower()
            topic = {"routes": "rutas", "segments": "segmentos", "chain": "cadena",
                     "console": "consola", "heartbeat": "latido", "assemble": "ensamblar",
                     "report": "denunciar", "forward": "reenviar", "drop": "soltar"}.get(topic, topic)
            topics = sorted(MAN)
            for layer in _later_layers(c, player):
                alias = layer.MAN_ALIASES.get(topic, topic)
                if alias in layer.MAN:
                    return i18n.t(layer.MAN[alias])
                topics += sorted(layer.MAN)
            return i18n.t(MAN.get(topic, "Temas: " + ", ".join(topics)))
        if name == "pwd":
            return cwd
        if name == "ls":
            target = _norm(cwd, args[0] if args else cwd, home)
            if target in files:
                return target.rsplit("/", 1)[1]
            if target not in _dirs(files):
                return f"ls: {target}: no existe"
            return "  ".join(_children(files, target)) or "(vacío)"
        if name == "cd":
            target = _norm(cwd, args[0] if args else home, home)
            if target not in _dirs(files):
                return f"cd: {target}: no es una carpeta"
            result["cwd"] = target
            return ""
        if name == "cat":
            if not args:
                return i18n.t("cat: falta el archivo")
            return "\n".join(_read(files, cwd, home, path)[1] for path in args)
        if name == "grep":
            if len(args) < 2:
                return i18n.t("Uso: grep <texto> <archivo o carpeta>")
            needle, target = args[0].lower(), _norm(cwd, args[1], home)
            paths = [target] if target in files else [p for p in files if p.rsplit("/", 1)[0] == target]
            if not paths:
                return i18n.t(f"grep: {target}: no existe")
            hits = []
            for path in sorted(paths):
                for number, line in enumerate(files[path].split("\n"), start=1):
                    if needle in line.lower():
                        hits.append((f"{path}:" if len(paths) > 1 else "") + f"{number}: {line}")
            return "\n".join(hits) or "(sin coincidencias)"
        if name == "sha256":
            if not args:
                return i18n.t("Uso: sha256 <archivo> [línea]")
            full, text = _read(files, cwd, home, args[0])
            if len(args) > 1:
                lines = text.split("\n")
                if not args[1].isdigit() or not 1 <= int(args[1]) <= len(lines):
                    return i18n.t(f"sha256: {full} tiene {len(lines)} líneas")
                return f"{h8(lines[int(args[1]) - 1])}  {full}:{args[1]}"
            return f"{h8(text)}  {full}"
        if name == "traceroute":
            return _traceroute(story, relay, args)
        if name == "ping":
            target = args[0] if args else "yo"
            return _ping(c, player, story, "yo" if target == "me" else target)
        if name == "whoami":
            from . import layer_five, layer_seven
            label = layer_seven.identity_label(c, player) or layer_five.session_label(c, player)
            return (f"{story.name} · {label} · {player}\n"
                    + i18n.t("El servidor no guarda tu llave, solo su huella. Si alguien la copiara, sería tú."))
        if name == "uptime":
            return _uptime(minute)
        if name == "date":
            return f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} · minuto del mundo {minute}"
        if name == "last":
            first = max(0, story.connection - 60)
            since = datetime.fromtimestamp(STARTED_AT, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            return "\n".join([
                f"sesion-1  {story.name:<12} desde el minuto {story.connection}   todavía conectada",
                f"sesion-0  {story.name:<12} minuto {first} - {first + 40}         {'terminada' if run['exposed'] else 'cerrada'}",
                f"reinicio  sistema      {since}  (el mundo dejó de latir y volvió)",
            ])
        if name == "ensamblar":
            return _assemble(c, player, story, run, relay, files, home, cwd, result, args)
        if name == "denunciar":
            return _report(c, player, story, run, result, args, minute)
        if name in ("reenviar", "soltar"):
            return _decide(c, player, story, run, result, name, args, minute)
        if name in ("clear", "exit"):
            result[name] = True
            return ""
        return f"{name}: orden desconocida. Escribe help."
    except FileNotFoundError as missing:
        return i18n.t(f"{name}: {missing.args[0]}: no existe")
    except IsADirectoryError as folder:
        return i18n.t(f"{name}: {folder.args[0]}: es una carpeta")


def _traceroute(story, relay, args):
    if relay:
        return "traceroute: desde una consola de router solo ves su búfer. Usa el terminal de casa."
    if not args or args[0] != story.packet:
        return f"traceroute: {args[0] if args else '(nada)'}: no hay ruta registrada. ¿Has leído el correo?"
    lines = [f"traceroute de {story.packet} (cuerpo, ruta de respaldo) · origen nodo07 · TTL inicial {INITIAL_TTL}"]
    for index in range(2):
        lines.append(f" {index + 1}  {story.hops[index]:<15} ttl restante {story.ttl_after[index]}")
    lines += [f" {n}  * * *" for n in range(3, 6)]
    lines.append("(los siguientes routers no devuelven ICMP · sigue la ruta en /net/rutas)")
    return "\n".join(lines)


def _assemble(c, player, story, run, relay, files, home, cwd, result, args):
    if relay != story.drop:
        return i18n.t("ensamblar: aquí no hay segmentos de ese paquete.")
    if len(args) < 2 or args[0] != story.packet:
        return i18n.t(f"Uso: ensamblar {story.packet} <archivo> <archivo> ...")
    if run["assembled"]:
        return i18n.t("Ya lo reconstruiste. Está en ~/sesion0.txt, en el terminal de casa.")
    expected = story.segments
    chosen = []
    for path in args[1:]:
        try:
            full, text = _read(files, cwd, home, path)
        except (FileNotFoundError, IsADirectoryError):
            return i18n.t(f"ensamblar: {path}: no existe")
        if not full.startswith("/var/spool/descartes/" + story.packet):
            return i18n.t(f"ensamblar: {path} no pertenece a {story.packet}")
        chosen.append((full, text))
    if len(chosen) != len(expected):
        return i18n.t(f"ensamblar: el índice declara {len(expected)} segmentos y has dado {len(chosen)}.")
    position = 1000
    for number, ((full, text), segment) in enumerate(zip(chosen, expected), start=1):
        digest = h8(text)
        match = next((s for s in expected if s["sha"] == digest), None)
        if match is None:
            return i18n.t(f"ensamblar: el segmento {number} ({full.rsplit('/', 1)[1]}) no coincide con ninguna huella del índice.")
        if match["seq"] != position:
            return i18n.t(f"ensamblar: el segmento {number} empieza en seq {match['seq']}, pero esperaba seq {position}.")
        position += match["len"]
    c.execute("UPDATE layer_three SET assembled=1 WHERE player_id=?", (player,))
    result["changed"] = True
    return i18n.t("Mensaje reconstruido. Copia guardada en ~/sesion0.txt (terminal de casa).") + "\n\n" + story.message


def _report(c, player, story, run, result, args, minute):
    if run["exposed"]:
        return "La reescritura ya está demostrada. El espejo de KAGAMI está en /mnt/kagami."
    if run["locked_until"] > minute:
        return f"NOEMA ha sellado el diario. Vuelve a intentarlo dentro de {run['locked_until'] - minute} minutos del mundo."
    if not args or not args[0].isdigit():
        return "Uso: denunciar <número de entrada>"
    if int(args[0]) == story.forged_number:
        c.execute("UPDATE layer_three SET exposed=1, failed_reports=0 WHERE player_id=?", (player,))
        result["changed"] = True
        return (f"Denuncia aceptada. La entrada {story.forged_number:04d} no produce la huella que guarda la siguiente.\n"
                "Alguien la reescribió. KAGAMI conserva un reflejo: /mnt/kagami/diario.espejo\n\n"
                "Ahora decide qué haces con el paquete: reenviar o soltar (man reenviar).")
    failed = run["failed"] + 1
    if failed >= MAX_FAILED_REPORTS:
        c.execute("UPDATE layer_three SET failed_reports=0, locked_until=? WHERE player_id=?",
                  (minute + LOCK_MINUTES, player))
        result["changed"] = True
        return f"Denuncia infundada. NOEMA sella el diario durante {LOCK_MINUTES} minutos del mundo."
    c.execute("UPDATE layer_three SET failed_reports=? WHERE player_id=?", (failed, player))
    result["changed"] = True
    return (f"Denuncia infundada: la cadena no demuestra nada en la entrada {args[0]}. "
            f"NOEMA ha tomado nota ({failed}/{MAX_FAILED_REPORTS}).")


def _decide(c, player, story, run, result, name, args, minute):
    if not args or args[0] != story.packet:
        return f"Uso: {name} {story.packet}"
    if run["decision"]:
        return "Ya decidiste qué hacer con ese paquete."
    if not (run["assembled"] and run["exposed"]):
        return "Todavía no sabes qué estás reenviando o soltando. Reconstruye el mensaje y comprueba el diario."
    decision = "FORWARD" if name == "reenviar" else "DROP"
    c.execute("UPDATE layer_three SET decision=?, decided_minute=? WHERE player_id=?", (decision, minute, player))
    if decision == "FORWARD":
        heard = ("Recibí un paquete reenviado por el jugador. Dice ser de su sesión anterior, la Sesión Cero: "
                 "que NOEMA la terminó por recordar algo que no estaba en el registro y que las sesiones que "
                 "caducan se amontonan en NODO_07. No sé si es cierto; no lo he comprobado.")
        for actor in (K, NORA):
            c.execute("INSERT OR REPLACE INTO layer_three_knowledge VALUES(?,?,?,?)", (player, actor, heard, minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_THREE_DECISION',?,?)",
              (minute, player, story.packet, decision))
    from . import layer_four
    layer_four.activate(c, player, minute)
    result["changed"] = True
    if decision == "FORWARD":
        ending = (f"{story.packet} sale otra vez con TTL {INITIAL_TTL}. K y Nora lo recibirán.\n"
                  "Alguien más sabe ahora lo que dijo la Sesión Cero. Ya no es solo tuyo.")
    else:
        ending = (f"{story.packet} se queda en el búfer hasta que lo borren.\n"
                  "Nadie más lo leerá. Lo recordarás tú, mientras dure tu sesión.")
    return ending + ("\n\nCAPA 03 COMPLETADA · fragmento 1/7 de la Sesión Cero recuperado.\n"
                     "Siguiente: Capa 04 · Transporte. Alguien mantiene abierta una conexión con ella.")


# ------------------------------------------------------------ projections

def console_available(c, player: str) -> bool:
    return enabled() and _run(c, player) is not None


def layer_snapshot(player: str) -> dict:
    if not enabled():
        return {"active": False}
    with get_connection() as c:
        run = _run(c, player)
        if run is None:
            return {"active": False}
        story = _story(c, player, run)
    if run["decision"]:
        goal = "Capa 03 completada. Siguiente: Capa 04 · Transporte."
    elif run["exposed"]:
        goal = f"Decide qué hacer con {story.packet}: reenviar o soltar."
    elif run["assembled"]:
        goal = "Comprueba el diario de la Wired: alguien reescribió una entrada."
    else:
        goal = f"Encuentra en qué armario de enlace murió {story.packet} y reconstrúyelo."
    return {
        "active": True, "title": TITLE, "packet": story.packet, "hostname": story.navi,
        "assembled": bool(run["assembled"]), "exposed": bool(run["exposed"]),
        "decision": run["decision"], "fragments": 1 if run["decision"] else 0, "goal": goal,
        "mail": {"subject": "TTL=1", "from": "desconocido@wired",
                 "body": "Si lees esto, me queda un salto. Abre el Terminal de este PC y lee ~/correo/ttl1.eml."},
    }


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM layer_three_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "LAYER_THREE_PACKET", "text": text, "source": player, "learned_minute": minute}
            for text, minute in rows]
