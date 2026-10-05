"""Capa 01 · Física (BIBLIA_NARRATIVA.md, section 6).

The link of the school's pavilion B has been dead for days: someone cut the
cable in its cabinet. The physical layer chip at the cut end still holds the
last thing the line carried. At the cabinet's console the player reads the
capture on an oscilloscope and decodes it: work out the samples per half-bit
from the sampling rate and the 10BASE-T line rate, vote out the noise, and
pick the Manchester convention that fits the pair's polarity, which the
Ethernet preamble gives away. The frame is Sesión Cero's: she cut the cable
herself so nobody could follow her. Then the player splices it, leaves it cut
or bridges the link through their own machine.

Concepts: signals and levels, Manchester encoding (IEEE 802.3 and G. E.
Thomas), oversampling and majority voting, polarity, the Ethernet preamble
and start frame delimiter, least significant bit first.
"""
import hashlib
import os
import random

from .database import get_connection
from . import i18n

TITLE = "Capa 01 · Física"
CABINET = "RELAY_SCHOOL"
K, NORA = "AGENT_K", "AGENT_NORA"
COMMANDS = {"scope", "osciloscopio", "decode", "decodificar", "empalmar", "splice", "dejar", "leave",
            "puentear", "bridge"}
# The capture and the decoded bytes are shown exactly; the layer translates its own messages.
RAW_COMMANDS = {"scope", "osciloscopio", "decode", "decodificar"}
PAIRS = {"naranja": "1-2", "verde": "3-6"}
PAIR_ALIASES = {"orange": "naranja", "green": "verde"}
RATES = {3: 60, 5: 100}
PREAMBLE = bytes([0x55] * 7 + [0xD5])
MESSAGE = ("Has vuelto. Este cable lo corté yo, para que nadie me siguiera hasta NODO_07. Un cuerpo es el medio "
           "por el que pasa una señal: si lo cortas, la señal se queda sin sitio. Si lo empalmas, me seguirán. "
           "Si no, tú tampoco podrás.")
README = ("Captura del chip de capa física, del lado cortado del cable.\n"
          "scope <par> enseña la señal; decode <par> <muestras por medio bit> <ieee|thomas> intenta leerla.\n"
          "Pares: naranja (pines 1-2) y verde (pines 3-6).")
SHOWN = 240


def enabled() -> bool:
    from . import layer_three
    return os.getenv("LAIN_LAYER_ONE", "0") == "1" and layer_three.enabled()


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_one'").fetchone() is not None


def initialize_layer_one() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS layer_one (
                player_id TEXT PRIMARY KEY, started_minute INTEGER NOT NULL, language TEXT NOT NULL,
                decoded INTEGER NOT NULL DEFAULT 0, decision TEXT, decided_minute INTEGER);
            CREATE TABLE IF NOT EXISTS layer_one_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_three'").fetchone():
            minute = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
            for (player,) in c.execute("SELECT player_id FROM layer_three").fetchall():
                activate(c, player, minute)


def activate(c, player: str, minute: int, language: str | None = None) -> bool:
    """Opens with the Wired connection, beside Capa 03; earlier players get it as an open layer."""
    if not enabled() or not _exists(c):
        return False
    created = c.execute("INSERT OR IGNORE INTO layer_one(player_id, started_minute, language) VALUES(?,?,?)",
                        (player, minute, i18n.normalize(language or i18n.language()))).rowcount
    if created:
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_ONE_STARTED',?,'')",
                  (minute, player, CABINET))
    return bool(created)


def run_for(c, player):
    if not enabled() or not _exists(c):
        return None
    row = c.execute("SELECT started_minute, language, decoded, decision FROM layer_one WHERE player_id=?",
                    (player,)).fetchone()
    return dict(zip(("started", "language", "decoded", "decision"), row)) if row else None


class Story:
    """One capture per player: which pair carries the frame, its polarity, sampling and noise."""

    def __init__(self, player: str, run: dict):
        rng = random.Random(hashlib.sha256(("layer1:" + player).encode()).digest())
        self.pair = rng.choice(sorted(PAIRS))
        self.inverted = rng.random() < 0.5
        self.samples = rng.choice(sorted(RATES))
        self.convention = "thomas" if self.inverted else "ieee"
        self.message = i18n.t(MESSAGE, run["language"])
        frame = PREAMBLE + self.message.encode("utf-8")
        # Ethernet puts each byte on the wire least significant bit first.
        bits = [(byte >> shift) & 1 for byte in frame for shift in range(8)]
        levels = [level for bit in bits for level in ((0, 1) if bit else (1, 0))]
        if self.inverted:
            levels = [1 - level for level in levels]
        self.capture = {}
        data = []
        for level in levels:
            chunk = [level] * self.samples
            if rng.random() < 0.2:
                for spot in rng.sample(range(self.samples), rng.randint(1, self.samples // 2)):
                    chunk[spot] = 1 - level
            data += chunk
        self.capture[self.pair] = data
        # The other pair only carries 10BASE-T normal link pulses.
        idle = [0] * len(data)
        for spot in range(rng.randrange(40, 90), len(idle), 400):
            idle[spot] = 1
        self.capture[next(name for name in PAIRS if name != self.pair)] = idle


def _story(c, player, run):
    return Story(player, run)


def files(c, player: str, relay, story3) -> dict:
    run = run_for(c, player)
    if run is None:
        return {}
    if relay is None:
        return {f"{story3.home}/correo/cable.eml": _mail()}
    return {"/var/log/phy/LEEME": README} if relay == CABINET else {}


def _mail() -> str:
    return "\n".join([
        "De: profesor <partes@escuela.malla>",
        "Asunto: Parte de incidencia · enlace del pabellón B",
        "",
        "El enlace del pabellón B lleva días mudo. Alguien cortó el cable de su armario, en el aula de informática.",
        "Antes de empalmarlo, mira qué llevaba: el chip del lado cortado guarda la última señal que pasó por él.",
        "La consola del armario tiene un osciloscopio.",
        "",
        "  man señal   man manchester   man ruido   man preambulo   man cable",
    ])


def _scope(story, args):
    args = [PAIR_ALIASES.get(arg, arg) for arg in args]
    if not args or args[0] not in PAIRS:
        return i18n.t("Uso: scope <naranja|verde> [desde la muestra]")
    start = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
    data = story.capture[args[0]]
    rate = RATES[story.samples]
    window = data[start:start + SHOWN]
    rows = ["".join("¯" if level else "_" for level in window[i:i + 60]) for i in range(0, len(window), 60)]
    header = i18n.t(f"osciloscopio · par {args[0]} (pines {PAIRS[args[0]]}) · muestreo {rate} MS/s · "
                    "línea 10BASE-T (10 Mbit/s, Manchester)")
    shown = i18n.t(f"captura: {len(data)} muestras · de la {start} a la {start + len(window)}")
    return "\n".join([header, shown, ""] + rows)


def _decode(c, player, story, run, result, args):
    args = [PAIR_ALIASES.get(arg, arg) for arg in args]
    if len(args) != 3 or args[0] not in PAIRS or not args[1].isdigit() or args[2] not in ("ieee", "thomas"):
        return i18n.t("Uso: decode <naranja|verde> <muestras por medio bit> <ieee|thomas>")
    pair, samples, convention = args[0], int(args[1]), args[2]
    if not 1 <= samples <= 9:
        return i18n.t("Las muestras por medio bit van de 1 a 9.")
    data = story.capture[pair]
    halves = [int(sum(data[i:i + samples]) * 2 > samples) for i in range(0, len(data) - samples + 1, samples)]
    bits, violations = [], 0
    for first, second in zip(halves[0::2], halves[1::2]):
        if first == second:
            violations += 1
        rising = first == 0 and second == 1
        bits.append(int(rising) if convention == "ieee" else int(not rising))
    if violations * 4 > len(bits):
        return i18n.t(f"bits: {len(bits)} · violaciones de código Manchester: {violations}\n"
                      "Faltan transiciones en mitad de bit: leída así, esto no es una trama Manchester.")
    data_bytes = bytes(sum(bit << shift for shift, bit in enumerate(bits[i:i + 8])) for i in range(0, len(bits) - 7, 8))
    lines = [i18n.t(f"bits: {len(bits)} · violaciones de código Manchester: {violations}"),
             " ".join(f"{byte:02x}" for byte in data_bytes[:16])]
    start = data_bytes.find(PREAMBLE)
    if start < 0:
        lines.append(i18n.t("preámbulo y SFD no encontrados"))
        return "\n".join(lines)
    payload = data_bytes[start + len(PREAMBLE):]
    lines.append(i18n.t(f"preámbulo y SFD encontrados · carga: {len(payload)} bytes"))
    lines.append(payload.decode("utf-8", errors="replace"))
    if (pair, samples, convention) == (story.pair, story.samples, story.convention) and not run["decoded"]:
        c.execute("UPDATE layer_one SET decoded=1 WHERE player_id=?", (player,))
        result["changed"] = True
    return "\n".join(lines)


MEMORIES = {
    "SPLICE": {
        NORA: "El jugador empalmó el cable que la Sesión Cero cortó en el pabellón B. Ahora cualquiera puede seguir su rastro, también yo.",
        K: "El enlace del pabellón B vuelve a funcionar. Puedo ver otra vez lo que pasa por él.",
    },
    "LEAVE": {
        NORA: "El jugador dejó cortado el cable del pabellón B. Respetó que la Sesión Cero no quisiera que la siguieran.",
        K: "El pabellón B sigue a oscuras. No me gustan los enlaces que nadie puede vigilar.",
    },
    "BRIDGE": {
        NORA: "El jugador hizo pasar el enlace del pabellón B por su propio equipo. Ahora la señal pasa por él.",
        K: "El enlace del pabellón B depende ahora del equipo del jugador. Si se desconecta, se cae.",
    },
}
ENDINGS = {
    "SPLICE": "Empalmas los pares en su orden. El enlace del pabellón B vuelve a latir.\n"
              "K puede ver otra vez el tráfico. Quien la seguía, también.",
    "LEAVE": "Dejas el cable como lo dejó ella. El pabellón B se queda a oscuras, y su rastro también.\n"
             "Un cuerpo cortado no lleva a ningún sitio.",
    "BRIDGE": "Llevas los dos extremos a tu Kumo. Ahora la señal pasa por ti: eres el medio.\n"
              "Si te desconectas, el pabellón B se queda mudo.",
}


def _decide(c, player, run, result, decision, minute):
    if run["decision"]:
        return "Ya decidiste qué hacer con el cable."
    if not run["decoded"]:
        return "Antes de tocar el cable, lee lo que llevaba (decode)."
    c.execute("UPDATE layer_one SET decision=?, decided_minute=? WHERE player_id=?", (decision, minute, player))
    for actor, text in MEMORIES[decision].items():
        c.execute("INSERT OR REPLACE INTO layer_one_knowledge VALUES(?,?,?,?)", (player, actor, text, minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_ONE_DECISION',?,?)",
              (minute, player, CABINET, decision))
    from . import layer_two
    layer_two.activate(c, player, minute, decision)
    result["changed"] = True
    return (ENDINGS[decision] + "\n\nCAPA 01 COMPLETADA · fragmento 1/7 de la Sesión Cero recuperado.\n"
            "Siguiente: Capa 02 · Enlace. Hay otra máquina en la red con tu dirección.")


def dispatch(c, player, story3, relay, result, name, args, minute):
    run = run_for(c, player)
    name = {"osciloscopio": "scope", "decodificar": "decode", "splice": "empalmar", "leave": "dejar",
            "bridge": "puentear"}.get(name, name)
    if relay != CABINET:
        message = "El cable cortado está en el armario del aula de informática: conéctate a su consola."
        return i18n.t(message) if name in ("scope", "decode") else message
    story = _story(c, player, run)
    if name == "scope":
        return _scope(story, args)
    if name == "decode":
        return _decode(c, player, story, run, result, args)
    decision = {"empalmar": "SPLICE", "dejar": "LEAVE", "puentear": "BRIDGE"}[name]
    return _decide(c, player, run, result, decision, minute)


HELP = """Capa 01 (consola del aula de informática):
  scope <par> [desde]     la señal capturada (pares: naranja, verde)
  decode <par> <muestras por medio bit> <ieee|thomas>     leerla como Manchester
  empalmar · dejar · puentear                     qué haces con el cable"""

MAN = {
    "señal": """Señal · niveles en un cable

Por un cable no viajan bits, sino niveles de tensión que cambian con el tiempo.
Un osciloscopio los muestrea: mide el nivel muchas veces por segundo y dibuja
alto (¯) o bajo (_). Si la línea va a 10 Mbit/s con Manchester, cambia de
nivel hasta 20 millones de veces por segundo (20 Mbaud). Muestreando a 60 MS/s
salen 3 muestras por cada medio bit.""",
    "manchester": """Codificación Manchester

Cada bit ocupa dos medios bits con una transición en el centro, así el receptor
recupera el reloj de la propia señal. En IEEE 802.3 (Ethernet 10BASE-T), un 1
es bajo→alto y un 0 es alto→bajo. La convención de G. E. Thomas es la contraria.
Si un par tiene los hilos cruzados, la señal llega invertida y se lee con la
convención opuesta. Dos medios bits iguales son una violación de código.""",
    "ruido": """Ruido · votación por mayoría

El ruido cambia muestras sueltas. Si cada medio bit tiene varias muestras, se
decide por mayoría: con 3 muestras, dos iguales ganan. Por eso se muestrea más
deprisa que la señal. Si eliges mal cuántas muestras forman un medio bit, los
grupos se desalinean y salen violaciones de código por todas partes.""",
    "preambulo": """Preámbulo y SFD

Toda trama Ethernet empieza con 7 bytes 0x55 (10101010 en el cable) para que el
receptor sincronice, y un byte 0xD5 (SFD, start frame delimiter) que marca el
comienzo de verdad. Ethernet envía cada byte empezando por el bit menos
significativo. Si al decodificar sale 0xAA en lugar de 0x55, los bits están
invertidos.""",
    "cable": """Cable de par trenzado

10BASE-T usa dos pares: naranja (pines 1-2) para transmitir y verde (pines 3-6)
para recibir. Cada par lleva la señal en dos hilos con tensiones opuestas; si se
cruzan, la polaridad se invierte. Un par sin datos solo lleva pulsos de enlace
(NLP), un pico aislado cada 16 ms, para decir «sigo aquí».""",
}
MAN_ALIASES = {"senal": "señal", "signal": "señal", "noise": "ruido", "preámbulo": "preambulo",
               "preamble": "preambulo", "sfd": "preambulo", "par": "cable", "pairs": "cable"}


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
        goal = "Capa 01 completada. Siguiente: Capa 02 · Enlace."
    elif run["decoded"]:
        goal = "Ya sabes qué llevaba el cable. Decide: empalmar, dejar o puentear."
    else:
        goal = "Alguien cortó el cable del armario del aula de informática. Lee en el osciloscopio lo último que llevaba."
    return {
        "active": True, "title": TITLE, "goal": goal, "decision": run["decision"], "fragments": count,
        "mail": {"subject": "Parte de incidencia · enlace del pabellón B", "from": "partes@escuela.malla",
                 "body": "El enlace del pabellón B lleva días mudo. Lee ~/correo/cable.eml en el Terminal."},
    }


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM layer_one_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "LAYER_ONE_PHYSICAL", "text": text, "source": player, "learned_minute": minute}
            for text, minute in rows]


def story_for(player: str) -> Story:
    with get_connection() as c:
        return _story(c, player, run_for(c, player))
