"""Capa 04 · Transporte (BIBLIA_NARRATIVA.md, section 6).

The Kumo has no TCP stack: the player completes a three-way handshake by hand,
recovers a lost segment with cumulative ACKs (three duplicates trigger a fast
retransmit), reads the TTL of the packets to see that the sender is two hops
away, captures that cabinet's traffic and finds Nora sending keepalives on
behalf of Sesión Cero. Then they close that connection with a correct FIN
exchange, reset it, or take the keepalives over.

Everything is generated per player and checked here; the client only shows
text. Packet notation follows tcpdump/netstat and is the same in both
languages; explanations go through the translation catalogue.
"""
import hashlib
import os
import random
import re

from .database import get_connection
from . import i18n

TITLE = "Capa 04 · Transporte"
PORT = 4004
KEEPALIVE = 75
INITIAL_TTL = 64
FAST_RETRANSMIT = 3
K, NORA = "AGENT_K", "AGENT_NORA"
COMMANDS = {"netstat", "tcpdump", "send", "wait", "esperar", "keepalive", "mantener"}
MESSAGE = (
    "No soy la Sesión Cero. Ella dejó de responder hace cuarenta días. Respondo yo por ella: "
    "cada setenta y cinco segundos mando un ACK a NODO_07 en su nombre, y NODO_07 cree que "
    "sigue ahí. Si nadie la recibe, caduca, y lo que caduca se borra. Mira el TTL de mis "
    "paquetes: no vengo de tan lejos. Cuando me encuentres, decide tú. Yo ya no puedo."
)


def enabled() -> bool:
    return os.getenv("LAIN_LAYER_FOUR", "0") == "1"


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_four'").fetchone() is not None


def initialize_layer_four() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS layer_four (
                player_id TEXT PRIMARY KEY, started_minute INTEGER NOT NULL, language TEXT NOT NULL,
                isn_l INTEGER, acked INTEGER NOT NULL DEFAULT 0, gap_acks INTEGER NOT NULL DEFAULT 0,
                retransmitted INTEGER NOT NULL DEFAULT 0, lost INTEGER NOT NULL DEFAULT 0,
                complete INTEGER NOT NULL DEFAULT 0, found_nora INTEGER NOT NULL DEFAULT 0,
                syn_failures INTEGER NOT NULL DEFAULT 0, closing INTEGER NOT NULL DEFAULT 0,
                decision TEXT, decided_minute INTEGER);
            CREATE TABLE IF NOT EXISTS layer_four_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_three'").fetchone():
            done = c.execute("SELECT player_id FROM layer_three WHERE decision IS NOT NULL").fetchall()
            minute = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
            for (player,) in done:
                activate(c, player, minute)


def activate(c, player: str, minute: int, language: str | None = None) -> bool:
    """Starts once Capa 03 is decided (inside that transaction, or at boot)."""
    if not enabled() or not _exists(c):
        return False
    created = c.execute(
        "INSERT OR IGNORE INTO layer_four(player_id, started_minute, language) VALUES(?,?,?)",
        (player, minute, i18n.normalize(language or i18n.language())),
    ).rowcount
    if created:
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_FOUR_STARTED','WIRED','SYN')",
                  (minute, player))
    return bool(created)


def run_for(c, player):
    if not enabled() or not _exists(c):
        return None
    row = c.execute(
        """SELECT started_minute, language, isn_l, acked, gap_acks, retransmitted, lost, complete,
        found_nora, syn_failures, closing, decision FROM layer_four WHERE player_id=?""", (player,)).fetchone()
    if row is None:
        return None
    keys = ("started", "language", "isn_l", "acked", "gap_acks", "retransmitted", "lost", "complete",
            "found_nora", "syn_failures", "closing", "decision")
    return dict(zip(keys, row))


class Story:
    """The connection as this player sees it, derived from their id."""

    def __init__(self, player: str, run: dict, navi: str):
        from .layer_three import RELAYS
        rng = random.Random(hashlib.sha256(("layer4:" + player).encode()).digest())
        self.navi = navi
        self.message = i18n.t(MESSAGE, run["language"])
        self.isn_r = rng.randrange(1_000_000, 3_900_000_000)
        data = self.message.encode("utf-8")
        while True:
            cuts = sorted(self._boundary(data, cut) for cut in rng.sample(range(40, len(data) - 40), 5))
            bounds = [0] + cuts + [len(data)]
            if min(b - a for a, b in zip(bounds, bounds[1:])) >= 30:
                break
        first = self.isn_r + 1
        self.segments = [{"seq": first + a, "end": first + b, "len": b - a, "data": data[a:b]}
                         for a, b in zip(bounds, bounds[1:])]
        self.lost = rng.randrange(1, len(self.segments) - 1)
        self.gap = self.segments[self.lost]["seq"]
        self.end = self.segments[-1]["end"]
        relays = list(RELAYS)
        rng.shuffle(relays)
        self.nora_relay = relays[0]
        self.distances = {relays[0]: 2, relays[1]: 3, relays[2]: 4}
        self.hostnames = {relay: RELAYS[relay][0] for relay in RELAYS}
        # Nora's connection with NODO_07 on behalf of Sesión Cero.
        self.ka_seq = rng.randrange(1_000_000, 3_900_000_000)   # Nora's SND.NXT
        self.ka_ack = rng.randrange(1_000_000, 3_900_000_000)   # NODO_07's next byte (RCV.NXT)
        self.rng = rng

    @staticmethod
    def _boundary(data: bytes, cut: int) -> int:
        while cut < len(data) and (data[cut] & 0xC0) == 0x80:
            cut += 1
        return cut

    def stream(self, run: dict) -> str:
        """Bytes the application has, in order: it never sees past a hole,
        unless the player confirmed the hole away (then those words are gone)."""
        received = bytearray()
        for index, segment in enumerate(self.segments):
            if index == self.lost and not run["retransmitted"]:
                if not run["lost"]:
                    break
                received += " […] ".encode("utf-8")
                continue
            received += segment["data"]
        return received.decode("utf-8", errors="replace")


def _story(c, player, run):
    from .layer_three import _run as layer_three_run, _story as layer_three_story
    navi = layer_three_story(c, player, layer_three_run(c, player)).navi
    return Story(player, run, navi)


# ------------------------------------------------------------- files

def _mail(story: Story) -> str:
    return "\n".join([
        "De: nodo07 <syn@malla>",
        "Asunto: SYN",
        "",
        f"Alguien llama a tu puerto {PORT} desde NODO_07 y nadie contesta.",
        "Ha repetido su SYN cinco veces, esperando cada vez el doble: 3, 6, 12, 24 segundos.",
        "",
        "Tu Kumo no tiene pila TCP. Si quieres responder, el saludo lo haces tú, a mano.",
        "",
        "  netstat          <- qué conexiones hay",
        "  tcpdump          <- qué paquetes han llegado",
        "  man tcp          <- cómo se abre una conexión",
    ])


def files(c, player: str, relay, story3) -> dict:
    run = run_for(c, player)
    if run is None:
        return {}
    story = _story(c, player, run)
    if relay:
        return {}
    result = {
        f"{story3.home}/correo/syn.eml": _mail(story),
        "/net/vecinos": "\n".join(
            ["# Distancia desde " + story.navi + " en saltos IP"]
            + [f"{story.hostnames[r]:<16} {d}" for r, d in sorted(story.distances.items(), key=lambda x: x[1])]
            + [f"{'nodo07':<16} 10"]),
    }
    if run["isn_l"] is not None:
        result[f"{story3.home}/flujo-{PORT}.txt"] = story.stream(run)
    return result


# ------------------------------------------------------------- commands

def _addr(story, side):
    return f"{story.navi}.{PORT}" if side == "local" else f"nodo07.{PORT}"


def _netstat(story, run, relay):
    lines = ["Proto  Local                       Remote              State"]
    if relay:
        lines.append(f"tcp    {story.hostnames[relay]}.22         *.*                 LISTEN")
        return "\n".join(lines)
    local, remote = _addr(story, "local"), _addr(story, "remote")
    if run["decision"] in {"FIN", "RST"} or run["closing"] == 2:
        state = "CLOSED"
    elif run["isn_l"] is None:
        state = i18n.t("SYN_RECV   (sin SYN+ACK: pila manual)")
    else:
        state = "ESTABLISHED"
    lines.append(f"tcp    {local:<27} {remote:<19} {state}")
    if run["isn_l"] is not None:
        lines.append(f"       snd.nxt={run['isn_l'] + 1}  rcv.ack={run['acked'] or '-'}")
    return "\n".join(lines)


def _seg_line(time, src, dst, segment, ttl, retransmission=False):
    tag = "  " + i18n.t("(retransmisión)") if retransmission else ""
    return f"{time}  IP {src} > {dst}: Flags [P.], seq {segment['seq']}:{segment['end']}, length {segment['len']}, ttl {ttl}{tag}"


def _tcpdump(c, player, story, run, relay, result, minute):
    local, remote = _addr(story, "local"), _addr(story, "remote")
    ttl = INITIAL_TTL - story.distances[story.nora_relay]
    if relay and relay != story.nora_relay:
        rng = random.Random(f"{story.isn_r}:{relay}")
        return "\n".join(
            f"{i * 7 % 60:02d}:{i * 13 % 60:02d}.{rng.randrange(1000):03d}  IP {rng.choice(['kissa-tpv', 'video-tpv', 'noema-sync'])}"
            f".{rng.randrange(1024, 9000)} > {rng.choice(['kagami-bk', 'noema-sync', 'wired-dns'])}.53: UDP, length {rng.randrange(40, 300)}"
            for i in range(6))
    if relay == story.nora_relay:
        lines = []
        for i in range(4):
            lines.append(f"{i * KEEPALIVE // 60:02d}:{i * KEEPALIVE % 60:02d}.000  IP nora-pda.{PORT} > nodo07.{PORT}: Flags [.], "
                         f"seq {story.ka_seq - 1}, ack {story.ka_ack}, win 512, length 0  (keepalive)")
        if run["isn_l"] is not None:
            for index, segment in enumerate(story.segments):
                if index != story.lost:
                    lines.append(_seg_line("04:51.0" + str(10 + index), f"nora-pda.{PORT}", local, segment, INITIAL_TTL))
        lines.append(f"# Conexión nora-pda.{PORT} <-> nodo07.{PORT}: abierta hace 40 días, "
                     f"solo keepalives cada {KEEPALIVE} s.")
        if not run["found_nora"]:
            c.execute("UPDATE layer_four SET found_nora=1 WHERE player_id=?", (player,))
            text = ("El jugador ha descubierto que mantengo viva la conexión de la Sesión Cero con NODO_07: "
                    "mando ACK de mantenimiento en su nombre desde hace cuarenta días para que no caduque. "
                    "Todavía no sé qué hará con eso.")
            c.execute("INSERT OR REPLACE INTO layer_four_knowledge VALUES(?,?,?,?)", (player, NORA, text, minute))
            result["changed"] = True
        return "\n".join(lines)
    lines = []
    if run["isn_l"] is None:
        for i, wait in enumerate((0, 3, 9, 21, 45)):
            lines.append(f"00:{wait:02d}.000  IP {remote} > {local}: Flags [S], seq {story.isn_r}, win 512, length 0, ttl {ttl}")
        lines.append("# Nadie responde: el SYN se repite y la espera se duplica.")
        return "\n".join(lines)
    lines.append(f"00:00.000  IP {remote} > {local}: Flags [S], seq {story.isn_r}, length 0, ttl {ttl}")
    lines.append(f"00:01.000  IP {local} > {remote}: Flags [S.], seq {run['isn_l']}, ack {story.isn_r + 1}, length 0")
    lines.append(f"00:01.020  IP {remote} > {local}: Flags [.], ack {run['isn_l'] + 1}, length 0, ttl {ttl}")
    for index, segment in enumerate(story.segments):
        if index == story.lost and not run["retransmitted"]:
            continue
        lines.append(_seg_line(f"00:01.{100 + index * 20}", remote, local, segment, ttl,
                               retransmission=index == story.lost))
    if run["acked"]:
        lines.append(f"00:02.000  IP {local} > {remote}: Flags [.], ack {run['acked']}, length 0")
    return "\n".join(lines)


def _numbers(args):
    values = {}
    for arg in args:
        match = re.fullmatch(r"(seq|ack)=(\d{1,10})", arg.lower())
        if match:
            values[match.group(1)] = int(match.group(2))
    return values


def _flags(arg: str) -> frozenset:
    return frozenset(part for part in re.split(r"[+,|]", arg.upper()) if part)


def _send(c, player, story, run, relay, result, args, minute):
    if len(args) < 2 or args[0].split(":")[0] not in {"nodo07", "node07"}:
        return "Uso: send nodo07 <SYN+ACK|ACK|FIN+ACK|RST> seq=<n> ack=<n>"
    flags, numbers = _flags(args[1]), _numbers(args[2:])
    if relay:
        return _send_on_link(c, player, story, run, relay, result, flags, numbers, minute)
    if run["decision"]:
        return "Esa conexión ya no existe."
    if run["isn_l"] is None:
        if flags == {"SYN"}:
            return "nodo07 ya te envió su SYN: no hace falta abrir otra conexión, hay que contestar a la suya."
        if flags != {"SYN", "ACK"}:
            return "nodo07 responde con RST: todavía no hay conexión que confirmar."
        if "seq" not in numbers or "ack" not in numbers:
            return "Un SYN+ACK necesita tu número inicial (seq=) y la confirmación de su SYN (ack=)."
        if numbers["ack"] != story.isn_r + 1:
            c.execute("UPDATE layer_four SET syn_failures=syn_failures+1 WHERE player_id=?", (player,))
            result["changed"] = True
            return "nodo07 responde con RST: ese ack no confirma su SYN."
        isn_l = numbers["seq"] % (2 ** 32)
        c.execute("UPDATE layer_four SET isn_l=? WHERE player_id=?", (isn_l, player))
        result["changed"] = True
        arrived = len(story.segments) - 1
        return (f"nodo07 confirma: ACK ack={isn_l + 1}. Conexión ESTABLISHED.\n"
                f"Llegan {arrived} segmentos de datos. Revisa tcpdump antes de confirmar nada.")
    if flags != {"ACK"} or "ack" not in numbers:
        return "Ahora toca confirmar lo recibido: send nodo07 ACK ack=<siguiente byte que esperas>."
    ack = numbers["ack"]
    if run["complete"]:
        return "Ya confirmaste todo el flujo."
    if ack <= story.isn_r or ack > story.end:
        return "ACK fuera de la ventana: nodo07 lo descarta."
    if ack < story.gap:
        return f"ACK {ack} confirma menos de lo que ya has recibido seguido. No cambia nada."
    if ack == story.gap and not run["retransmitted"]:
        count = run["gap_acks"] + 1
        if count >= FAST_RETRANSMIT:
            c.execute("UPDATE layer_four SET acked=?, gap_acks=?, retransmitted=1 WHERE player_id=?", (ack, count, player))
            result["changed"] = True
            segment = story.segments[story.lost]
            return (f"ACK repetido {count}/{FAST_RETRANSMIT}: retransmisión rápida.\n"
                    f"nodo07 reenvía seq {segment['seq']}:{segment['end']}. El hueco está cubierto.")
        c.execute("UPDATE layer_four SET acked=?, gap_acks=? WHERE player_id=?", (ack, count, player))
        result["changed"] = True
        return f"ACK {ack} enviado. ACK repetidos para este hueco: {count}/{FAST_RETRANSMIT}."
    if not run["retransmitted"]:
        # Confirming bytes that never arrived: the sender forgets them.
        complete = 1 if ack == story.end else 0
        c.execute("UPDATE layer_four SET acked=?, lost=1, complete=? WHERE player_id=?", (ack, complete, player))
        result["changed"] = True
        segment = story.segments[story.lost]
        return (f"nodo07 da por entregado todo hasta el byte {ack - 1}.\n"
                f"El segmento {segment['seq']}:{segment['end']} nunca te llegó: esas palabras se han perdido.")
    complete = 1 if ack == story.end else 0
    c.execute("UPDATE layer_four SET acked=?, complete=? WHERE player_id=?", (ack, complete, player))
    result["changed"] = True
    if complete:
        return f"Flujo completo: {story.end - story.isn_r - 1} bytes. Léelo en ~/flujo-{PORT}.txt"
    return f"ACK {ack} enviado."


def _wait(c, player, story, run, result):
    if run["isn_l"] is None or run["complete"]:
        return "Pasa el tiempo. Nada cambia."
    if run["acked"] == story.gap and not run["retransmitted"]:
        c.execute("UPDATE layer_four SET retransmitted=1 WHERE player_id=?", (player,))
        result["changed"] = True
        segment = story.segments[story.lost]
        return (f"Vence el temporizador de retransmisión (RTO).\n"
                f"nodo07 reenvía seq {segment['seq']}:{segment['end']}.")
    return "Pasa el tiempo. nodo07 espera tu ACK."


def _send_on_link(c, player, story, run, relay, result, flags, numbers, minute):
    if relay != story.nora_relay or not run["found_nora"]:
        return "Por este armario no pasa ninguna conexión con nodo07."
    if run["decision"]:
        return "Ya decidiste qué hacer con esa conexión."
    if not run["complete"]:
        return "Todavía no sabes qué dice ese flujo. Termina de recibirlo en casa."
    if flags == {"RST"}:
        if numbers.get("seq") != story.ka_seq:
            return "nodo07 ignora el RST: su seq no es exactamente el siguiente byte de la conexión."
        return _decide(c, player, story, result, "RST", minute)
    if flags == {"FIN", "ACK"} and run["closing"] == 0:
        if numbers.get("seq") != story.ka_seq or numbers.get("ack") != story.ka_ack:
            return "nodo07 descarta el FIN: seq o ack no encajan con la conexión."
        c.execute("UPDATE layer_four SET closing=1 WHERE player_id=?", (player,))
        result["changed"] = True
        return (f"nodo07 responde: Flags [.], ack {story.ka_seq + 1}\n"
                f"nodo07 responde: Flags [F.], seq {story.ka_ack}, ack {story.ka_seq + 1}\n"
                "Falta tu último ACK para cerrar.")
    if flags == {"ACK"} and run["closing"] == 1:
        if numbers.get("seq") != story.ka_seq + 1 or numbers.get("ack") != story.ka_ack + 1:
            return "Ese ACK no confirma el FIN de nodo07."
        c.execute("UPDATE layer_four SET closing=2 WHERE player_id=?", (player,))
        return _decide(c, player, story, result, "FIN", minute)
    return "Esa combinación no cierra ni corta nada. Consulta man fin y man rst."


def _keepalive(c, player, story, run, relay, result, args, minute):
    if not args or args[0].split(":")[0] not in {"nodo07", "node07"}:
        return "Uso: keepalive nodo07"
    if relay != story.nora_relay or not run["found_nora"]:
        return "Por este armario no pasa ninguna conexión con nodo07."
    if run["decision"]:
        return "Ya decidiste qué hacer con esa conexión."
    if not run["complete"]:
        return "Todavía no sabes qué dice ese flujo. Termina de recibirlo en casa."
    return _decide(c, player, story, result, "KEEPALIVE", minute)


MEMORIES = {
    "FIN": {
        NORA: "El jugador cerró con cuidado, con un FIN correcto, la conexión que yo mantenía por la Sesión Cero. "
              "Ya no tengo que responder por ella. Me duele, pero quizá era lo que ella habría querido.",
        K: "La conexión fantasma con NODO_07 se cerró limpiamente. Hay menos tráfico huérfano en la red.",
    },
    "RST": {
        NORA: "El jugador cortó de golpe, con un RST, la conexión que yo mantenía por la Sesión Cero. "
              "No me preguntó. No se lo perdono fácilmente.",
        K: "Alguien reinició bruscamente una conexión antigua con NODO_07. Fue eficaz, no amable.",
    },
    "KEEPALIVE": {
        NORA: "El jugador se ha quedado con los ACK de la Sesión Cero. Ya no la sostengo sola.",
        K: "El jugador mantiene viva artificialmente una sesión caducada en NODO_07. Eso no es estable.",
    },
}
ENDINGS = {
    "FIN": "FIN, ACK, FIN, ACK. La conexión pasa a TIME_WAIT y después a CLOSED.\n"
           "NODO_07 deja de esperar a la Sesión Cero. Nadie tiene que fingir que sigue ahí.",
    "RST": "RST. La conexión deja de existir sin despedida.\n"
           "NODO_07 olvida a la Sesión Cero en un instante. Nora lo verá en su pantalla.",
    "KEEPALIVE": f"A partir de ahora tu Kumo manda un ACK cada {KEEPALIVE} segundos en nombre de la Sesión Cero.\n"
                 "Mientras tú la recibas, no caducará. Nora puede descansar. Tú ya no.",
}


def _decide(c, player, story, result, decision, minute):
    c.execute("UPDATE layer_four SET decision=?, decided_minute=? WHERE player_id=?", (decision, minute, player))
    for actor, text in MEMORIES[decision].items():
        c.execute("INSERT OR REPLACE INTO layer_four_knowledge VALUES(?,?,?,?)", (player, actor, text, minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_FOUR_DECISION','NODE_07',?)",
              (minute, player, decision))
    from . import layer_five
    layer_five.activate(c, player, minute, decision)
    result["changed"] = True
    return (ENDINGS[decision] + "\n\nCAPA 04 COMPLETADA · fragmento 4/7 de la Sesión Cero recuperado.\n"
            "Siguiente: Capa 05 · Sesión. Solo una de las dos sesiones puede seguir activa.")


def dispatch(c, player, story3, relay, result, name, args, minute):
    run = run_for(c, player)
    if run is None:
        return f"{name}: orden desconocida. Escribe help."
    story = _story(c, player, run)
    if name == "netstat":
        return _netstat(story, run, relay)
    if name == "tcpdump":
        return _tcpdump(c, player, story, run, relay, result, minute)
    if name == "send":
        return _send(c, player, story, run, relay, result, args, minute)
    if name in {"wait", "esperar"}:
        return _wait(c, player, story, run, result)
    return _keepalive(c, player, story, run, relay, result, args, minute)


HELP = """Capa 04:
  netstat                conexiones      tcpdump          paquetes capturados
  send nodo07 <FLAGS> seq=<n> ack=<n>    enviar un segmento a mano
  wait                   dejar pasar el tiempo   keepalive nodo07"""

MAN = {
    "tcp": """TCP · abrir una conexión (saludo de tres pasos)

1. Quien llama envía SYN con su número de secuencia inicial (seq=x).
2. Quien contesta envía SYN+ACK: su propio número inicial (seq=y) y ack=x+1,
   que significa «he recibido tu SYN; el siguiente byte que espero es x+1».
3. Quien llamó envía ACK con ack=y+1. La conexión queda ESTABLISHED.

Un SYN ocupa un número de secuencia aunque no lleve datos. Si nadie contesta,
el SYN se retransmite con el mismo seq y la espera se duplica cada vez.
Una pila TCP normal contesta sola; la del Kumo no: send nodo07 SYN+ACK ...""",
    "ack": """ACK acumulativo

ack=n significa «he recibido bien todo hasta el byte n-1; espero el n».
No se pueden confirmar trozos sueltos: si falta un segmento, el ack se queda
en el primer byte que falta aunque hayan llegado otros después.
Si confirmas bytes que no tienes, quien envía los da por entregados y no los
volverá a mandar.""",
    "retransmision": """Retransmisión

Quien envía guarda una copia de lo no confirmado. Lo reenvía si vence su
temporizador (RTO: deja pasar el tiempo con wait) o, antes, si recibe tres
ACK iguales que piden el mismo byte: retransmisión rápida (RFC 5681).""",
    "keepalive": """Keepalive

Una conexión sin datos puede durar para siempre si alguien la mantiene.
Un keepalive es un segmento vacío con seq = siguiente byte - 1 y el ack del
otro lado: obliga a contestar sin mandar nada nuevo (RFC 1122). Por eso, en
una captura de keepalives, el siguiente byte real de la conexión es seq + 1.""",
    "fin": """FIN · cerrar con cuidado

Cada lado cierra su mitad. Quien cierra envía FIN+ACK con su siguiente seq y el
ack de lo recibido; el otro lado confirma ese FIN (ack = seq + 1) y envía su
propio FIN; quien cerró confirma ese FIN con un último ACK (seq + 1, ack + 1)
y queda en TIME_WAIT antes de CLOSED. Un FIN ocupa un número de secuencia.""",
    "rst": """RST · cortar

Un RST destruye la conexión al instante, sin despedida. Solo se acepta si su
seq es exactamente el siguiente byte que el otro lado espera (RFC 5961).""",
    "netstat": "netstat · las conexiones de este equipo y su estado (LISTEN, SYN_RECV, ESTABLISHED, TIME_WAIT, CLOSED).",
    "tcpdump": """tcpdump · los paquetes que han pasado por aquí

Flags: S = SYN, . = ACK, P = datos, F = FIN, R = RST. seq a:b son los bytes de
a hasta b-1. ttl es el TTL con el que llegó: casi todos los equipos empiezan
en 64, así que 64 - ttl son los saltos recorridos. Solo ves el tráfico que
pasa por el equipo o armario donde ejecutas tcpdump.""",
    "send": "send nodo07 <FLAGS> seq=<n> ack=<n> · envía un segmento TCP escrito a mano (FLAGS: SYN+ACK, ACK, FIN+ACK, RST).",
}
MAN_ALIASES = {"handshake": "tcp", "saludo": "tcp", "retransmission": "retransmision", "retransmisión": "retransmision"}


# ------------------------------------------------------------- projections

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
        goal = "Capa 04 completada. Siguiente: Capa 05 · Sesión."
    elif run["found_nora"] and run["complete"]:
        goal = "Decide qué hacer con la conexión que Nora mantiene viva: cerrarla, cortarla o relevarla."
    elif run["complete"]:
        goal = "El TTL de esos paquetes dice de dónde vienen. Encuentra ese armario y captura su tráfico."
    elif run["isn_l"] is not None:
        goal = "Recibe el flujo entero: confirma con ACK solo lo que tienes seguido."
    else:
        goal = "Alguien llama a tu puerto 4004 desde NODO_07. Contesta a su SYN a mano."
    return {
        "active": True, "title": TITLE, "goal": goal, "decision": run["decision"],
        "fragments": count,
        "mail": {"subject": "SYN", "from": "syn@malla",
                 "body": "Alguien llama a tu puerto 4004 desde NODO_07 y nadie contesta. Lee ~/correo/syn.eml en el Terminal."},
    }


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM layer_four_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "LAYER_FOUR_CONNECTION", "text": text, "source": player, "learned_minute": minute}
            for text, minute in rows]


def story_for(player: str) -> Story:
    """This player's connection details (owner tools and tests)."""
    with get_connection() as c:
        return _story(c, player, run_for(c, player))
