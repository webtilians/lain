"""Capa 02 · Enlace (BIBLIA_NARRATIVA.md, section 6).

K notices that the station switch keeps moving the player's MAC address
between two ports. One is the player's own machine; the other is a machine
that KAGAMI is running with the same address: a replica of them, copied a
while ago. The player compares the heartbeat counter on their own interface
with the frames captured on each port, checks each frame's FCS (CRC-32) to
throw away the damaged ones, and so tells their port from the copy's. Then
they shut the copy's port, give themselves a new locally administered
address, or let both share it.

Concepts: MAC addresses (OUI, universal/local and unicast/multicast bits),
Ethernet frames, the frame check sequence, switch MAC learning and flapping.
"""
import hashlib
import os
import random
import zlib

from .database import get_connection
from . import i18n

TITLE = "Capa 02 · Enlace"
SWITCH = "RELAY_STATION"
K, NORA = "AGENT_K", "AGENT_NORA"
COMMANDS = {"ip", "show", "capture", "fcs", "shutdown", "compartir", "share"}
# Captured frames are shown byte for byte; the layer translates its own messages.
RAW_COMMANDS = {"capture"}
BROADCAST = "ff:ff:ff:ff:ff:ff"
ETHERTYPE = "88b5"
SESSION_ZERO = "sesion0 · si dos tienen tu dirección, la red no sabe cuál eres. Yo tampoco lo supe."


def enabled() -> bool:
    from . import layer_one
    return os.getenv("LAIN_LAYER_TWO", "0") == "1" and layer_one.enabled()


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_two'").fetchone() is not None


def initialize_layer_two() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS layer_two (
                player_id TEXT PRIMARY KEY, started_minute INTEGER NOT NULL, language TEXT NOT NULL,
                previous TEXT NOT NULL, seen INTEGER NOT NULL DEFAULT 0, decision TEXT, decided_minute INTEGER);
            CREATE TABLE IF NOT EXISTS layer_two_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_one'").fetchone():
            minute = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
            for player, decision in c.execute(
                    "SELECT player_id, decision FROM layer_one WHERE decision IS NOT NULL").fetchall():
                activate(c, player, minute, decision)


def activate(c, player: str, minute: int, previous: str, language: str | None = None) -> bool:
    """Starts once Capa 01 is decided."""
    if not enabled() or not _exists(c):
        return False
    created = c.execute(
        "INSERT OR IGNORE INTO layer_two(player_id, started_minute, language, previous) VALUES(?,?,?,?)",
        (player, minute, i18n.normalize(language or i18n.language()), previous)).rowcount
    if created:
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_TWO_STARTED',?,?)",
                  (minute, player, SWITCH, previous))
    return bool(created)


def run_for(c, player):
    if not enabled() or not _exists(c):
        return None
    row = c.execute("SELECT started_minute, language, previous, seen, decision FROM layer_two WHERE player_id=?",
                    (player,)).fetchone()
    return dict(zip(("started", "language", "previous", "seen", "decision"), row)) if row else None


def mac(octets) -> str:
    return ":".join(f"{octet:02x}" for octet in octets)


class Story:
    """The player's address, the two ports it appears on and what each one sent."""

    def __init__(self, player: str, run: dict, navi: str):
        rng = random.Random(hashlib.sha256(("layer2:" + player).encode()).digest())
        self.navi, self.language = navi, run["language"]
        self.mac = mac([0x00, 0x4C, 0x41] + [rng.randrange(256) for _ in range(3)])
        self.port, self.replica_port = rng.sample(range(1, 13), 2)
        self.seq = rng.randrange(410, 990)
        # The replica was copied some hundreds of heartbeats ago: same last digits, older count.
        self.replica_seq = self.seq - 100 * rng.randint(1, 3)
        self.copied = max(0, run["started"] - rng.randrange(300, 2000))
        self.tx = rng.randrange(8000, 20000)
        t = lambda text: i18n.t(text, self.language)  # noqa: E731 - frozen in the layer's language
        beat = t("latido {navi} seq {seq}")
        self.frames = {
            self.port: [
                (self.mac, BROADCAST, beat.format(navi=navi, seq=self.seq - 2)),
                (self.mac, "00:4c:41:00:07:01", "telnet wired 23"),
                ("00:4c:41:00:00:00", self.mac, t(SESSION_ZERO)),
                (self.mac, BROADCAST, beat.format(navi=navi, seq=self.seq - 1)),
                (self.mac, BROADCAST, beat.format(navi=navi, seq=self.seq)),
            ],
            self.replica_port: [
                (self.mac, BROADCAST, beat.format(navi=navi, seq=self.replica_seq - 1)),
                (self.mac, "00:4c:41:66:00:04",
                 t("sync kagami-04 · estado copiado en el minuto {minute}").format(minute=self.copied)),
                (self.mac, BROADCAST, beat.format(navi=navi, seq=self.replica_seq)),
                (self.mac, BROADCAST, t("ARP · ¿quién tiene 10.66.4.1? responde a {navi}").format(navi=navi)),
            ],
        }
        self.fcs = {port: [_crc(frame) for frame in frames] for port, frames in self.frames.items()}
        # Two frames arrive damaged: their FCS still belongs to what was sent.
        mine = self.frames[self.port]
        mine[1] = (mine[1][0], mine[1][1], "telnet wirad 23")
        theirs = self.frames[self.replica_port]
        damaged = beat.format(navi=navi, seq=self.replica_seq)
        theirs.append((self.mac, BROADCAST, damaged.replace(f"seq {self.replica_seq}", f"seq {self.seq}")))
        self.fcs[self.replica_port].append(_crc(theirs[2]))
        self.damaged = {self.port: 2, self.replica_port: 5}


def _crc(frame) -> str:
    source, destination, payload = frame
    data = bytes.fromhex(destination.replace(":", "") + source.replace(":", "") + ETHERTYPE) + payload.encode("utf-8")
    return f"{zlib.crc32(data):08x}"


def _story(c, player, run, navi):
    return Story(player, run, navi)


def files(c, player: str, relay, story3) -> dict:
    run = run_for(c, player)
    if run is None or relay:
        return {}
    return {f"{story3.home}/correo/direccion.eml": _mail()}


def _mail() -> str:
    return "\n".join([
        "De: k <k@estacion.malla>",
        "Asunto: Tu dirección, dos veces",
        "",
        "La tabla del conmutador de la estación no se está quieta: tu dirección aparece en dos puertos a la vez.",
        "Uno es el tuyo. El otro no debería existir.",
        "Mira tu dirección en tu Kumo (ip link) y luego la consola del armario del andén: show mac, show log, capture.",
        "",
        "  man mac   man trama   man fcs   man conmutador",
    ])


def _ip(c, player, story, run, result, relay, args, minute):
    if relay:
        return "ip: esta consola no es tu Kumo."
    if args[:3] == ["link", "set", "address"] and len(args) == 4:
        return _rename(c, player, story, run, result, args[3].lower(), minute)
    if args[:1] in (["link"], ["-s"], ["addr"]) or not args:
        return "\n".join([
            "2: eth0: <BROADCAST,MULTICAST,UP> mtu 1500",
            f"    link/ether {story.mac} brd {BROADCAST}",
            i18n.t(f"    TX: {story.tx} tramas · último latido seq {story.seq}"),
        ])
    return "Uso: ip link · ip link set address <mac>"


def _show(story, args):
    if args == ["mac"]:
        rng = random.Random(story.mac)
        lines = ["VLAN  MAC                 puerto  movimientos"]
        neighbours = [mac([0x00, 0x4C, 0x41, rng.randrange(256), rng.randrange(256), rng.randrange(256)]) for _ in range(4)]
        used = {story.port, story.replica_port}
        free = [port for port in range(1, 13) if port not in used]
        for address, port in zip(neighbours, rng.sample(free, 4)):
            lines.append(f"1     {address}   {port:<7} 0")
        lines.append(f"1     {story.mac}   {story.replica_port:<7} 41")
        return "\n".join(lines)
    if args == ["log"]:
        lines = []
        for step in range(4):
            a, b = (story.port, story.replica_port) if step % 2 == 0 else (story.replica_port, story.port)
            lines.append(f"%SW-4-MAC_FLAP: {story.mac} VLAN 1 · puerto {a} → puerto {b}")
        return "\n".join(lines)
    return "Uso: show mac · show log"


def _capture(c, player, story, run, result, args):
    if len(args) != 1 or not args[0].isdigit() or not 1 <= int(args[0]) <= 12:
        return i18n.t("Uso: capture <puerto 1-12>")
    port = int(args[0])
    frames = story.frames.get(port, [])
    if not frames:
        return i18n.t(f"puerto {port}: sin tramas de {story.mac}")
    if port == story.replica_port and not run["seen"]:
        c.execute("UPDATE layer_two SET seen=1 WHERE player_id=?", (player,))
        result["changed"] = True
    lines = [i18n.t(f"captura del puerto {port} · {len(frames)} tramas"),
             "n  " + i18n.t("origen") + f"{'':<13}" + i18n.t("destino") + f"{'':<12}fcs       " + i18n.t("contenido")]
    for number, ((source, destination, payload), fcs) in enumerate(zip(frames, story.fcs[port]), start=1):
        lines.append(f"{number}  {source}  {destination}  {fcs}  {payload}")
    return "\n".join(lines)


def _fcs(story, args):
    if len(args) != 2 or not all(arg.isdigit() for arg in args):
        return "Uso: fcs <puerto> <n>"
    port, number = int(args[0]), int(args[1])
    frames = story.frames.get(port, [])
    if not 1 <= number <= len(frames):
        return f"El puerto {port} no tiene una trama {number}."
    return (f"trama {number} del puerto {port}\n"
            f"  fcs que trae:      {story.fcs[port][number - 1]}\n"
            f"  crc32 calculado:   {_crc(frames[number - 1])}")


MEMORIES = {
    "SHUT": {
        NORA: "El jugador apagó el puerto de su réplica de KAGAMI. La copia sigue encendida, pero ya nadie la oye.",
        K: "El conmutador de la estación vuelve a estar estable: una sola máquina con esa dirección.",
    },
    "RENAME": {
        NORA: "El jugador se cambió la dirección y dejó la suya a la réplica de KAGAMI. Dice que ahora el original es ella.",
        K: "El jugador usa una dirección nueva, administrada localmente. La antigua es de la réplica de KAGAMI.",
    },
    "SHARE": {
        NORA: "El jugador deja que su réplica de KAGAMI use su misma dirección. Para la red son la misma persona.",
        K: "Sigue habiendo dos máquinas con la misma dirección en la estación. El conmutador no para de dudar.",
    },
}
ENDINGS = {
    "SHUT": "Apagas el puerto de la copia. Sigue funcionando en el armario de KAGAMI, pero ya nadie la oye.\n"
            "La red vuelve a tener un solo tú. Que sea el bueno es otra cuestión.",
    "RENAME": "Te pones una dirección administrada localmente. La copia se queda con tu dirección de fábrica.\n"
              "Para la red, el original ahora es ella.",
    "SHARE": "Dejas que los dos uséis la misma dirección. El conmutador seguirá dudando entre un puerto y otro.\n"
             "Para la red, sois la misma persona en dos sitios, a ratos.",
}


def _decide(c, player, run, result, decision, minute):
    if run["decision"]:
        return "Ya decidiste qué hacer con tu copia."
    if not run["seen"]:
        return "Antes de decidir, mira qué tramas salen del otro puerto (capture)."
    c.execute("UPDATE layer_two SET decision=?, decided_minute=? WHERE player_id=?", (decision, minute, player))
    for actor, text in MEMORIES[decision].items():
        c.execute("INSERT OR REPLACE INTO layer_two_knowledge VALUES(?,?,?,?)", (player, actor, text, minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_TWO_DECISION',?,?)",
              (minute, player, SWITCH, decision))
    result["changed"] = True
    return (ENDINGS[decision] + "\n\nCAPA 02 COMPLETADA · fragmento 2/7 de la Sesión Cero recuperado.\n"
            "KAGAMI tiene una réplica tuya en funcionamiento. Siguiente: Capa 03 · TTL.")


def _rename(c, player, story, run, result, address, minute):
    parts = address.split(":")
    if len(parts) != 6 or not all(len(part) == 2 and all(ch in "0123456789abcdef" for ch in part) for part in parts):
        return "Esa no es una dirección MAC: seis bytes en hexadecimal, separados por dos puntos."
    first = int(parts[0], 16)
    if address == story.mac:
        return "Esa ya es tu dirección."
    if first & 1:
        return "Esa dirección es de grupo (multicast): una tarjeta no puede usarla como propia."
    if not first & 2:
        return "Esa dirección es universal: pertenece al bloque de un fabricante. Usa una administrada localmente."
    return _decide(c, player, run, result, "RENAME", minute)


def dispatch(c, player, story3, relay, result, name, args, minute):
    run = run_for(c, player)
    story = _story(c, player, run, story3.navi)
    if name == "ip":
        return _ip(c, player, story, run, result, relay, args, minute)
    if relay != SWITCH:
        message = "El conmutador está en el armario del andén: conéctate a su consola."
        return i18n.t(message) if name in RAW_COMMANDS else message
    if name == "show":
        return _show(story, args)
    if name == "capture":
        return _capture(c, player, story, run, result, args)
    if name == "fcs":
        return _fcs(story, args)
    if name == "shutdown":
        if len(args) != 1 or not args[0].isdigit():
            return "Uso: shutdown <puerto>"
        port = int(args[0])
        if port == story.port and run["seen"] and not run["decision"]:
            return "Ese es el puerto de tu Kumo: te desconectarías a ti."
        if port not in (story.port, story.replica_port) and run["seen"] and not run["decision"]:
            return "En ese puerto no hay nadie con tu dirección."
        return _decide(c, player, run, result, "SHUT", minute)
    return _decide(c, player, run, result, "SHARE", minute)


HELP = """Capa 02 (tu Kumo y la consola del andén):
  ip link                 tu dirección y lo que has enviado
  show mac · show log     la tabla del conmutador y sus avisos
  capture <puerto>        las tramas de un puerto     fcs <puerto> <n>   comprobar una trama
  shutdown <puerto> · ip link set address <mac> · compartir      qué haces con tu copia"""

MAN = {
    "mac": """Dirección MAC

Seis bytes que identifican una tarjeta de red en su segmento: 00:4c:41:12:34:56.
Los tres primeros (OUI) son del fabricante. En el primer byte, el bit más bajo
dice si es de grupo (1, multicast) o de una sola tarjeta (0); el siguiente dice
si es universal (0, grabada de fábrica) o administrada localmente (1, puesta a
mano). ff:ff:ff:ff:ff:ff es para todos (broadcast). Una dirección se puede
repetir: nada en el enlace impide que dos máquinas usen la misma.""",
    "trama": """Trama Ethernet

Lo que viaja por el enlace: dirección de destino (6 bytes), de origen (6),
tipo (2), los datos y, al final, el FCS (4). El preámbulo va antes y no cuenta.
capture <puerto> enseña las tramas que el conmutador vio en ese puerto.""",
    "fcs": """FCS · frame check sequence

Un CRC-32 calculado sobre destino, origen, tipo y datos. Quien recibe lo vuelve
a calcular: si no coincide con el que trae la trama, algo cambió por el camino
y la trama se descarta. Detecta daños, no mentiras: quien manda una trama
calcula su FCS, sea quien sea. fcs <puerto> <n> enseña los dos valores.""",
    "conmutador": """Conmutador · tabla de direcciones

Un conmutador aprende por qué puerto se llega a cada dirección mirando el
origen de las tramas que recibe. Si la misma dirección aparece por dos puertos,
la apunta en el último que oyó y avisa (MAC_FLAP). No sabe cuál de las dos
máquinas es la de verdad: solo sabe dónde habló alguien con ese nombre la última
vez. shutdown <puerto> apaga un puerto.""",
}
MAN_ALIASES = {"frame": "trama", "crc": "fcs", "switch": "conmutador", "address": "mac"}


def layer_snapshot(player: str) -> dict:
    if not enabled():
        return {"active": False}
    from .protocol import fragments
    with get_connection() as c:
        run = run_for(c, player)
        if run is None:
            return {"active": False}
        count = fragments(c, player)
    if run["decision"]:
        goal = "Capa 02 completada. Siguiente: Capa 03 · TTL."
    elif run["seen"]:
        goal = "Ya sabes qué hay en el otro puerto. Decide: shutdown, una dirección nueva o compartir."
    else:
        goal = "Tu dirección aparece en dos puertos del conmutador de la estación. Averigua cuál es el tuyo."
    return {
        "active": True, "title": TITLE, "goal": goal, "decision": run["decision"], "fragments": count,
        "mail": {"subject": "Tu dirección, dos veces", "from": "k@estacion.malla",
                 "body": "Tu dirección aparece en dos sitios a la vez. Lee ~/correo/direccion.eml en el Terminal."},
    }


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM layer_two_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "LAYER_TWO_LINK", "text": text, "source": player, "learned_minute": minute}
            for text, minute in rows]


def story_for(player: str) -> Story:
    from .layer_three import _run, _story as layer_three_story
    with get_connection() as c:
        navi = layer_three_story(c, player, _run(c, player)).navi
        return _story(c, player, run_for(c, player), navi)
