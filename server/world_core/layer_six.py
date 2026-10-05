"""Capa 06 · Presentación (BIBLIA_NARRATIVA.md, section 6).

Sesión Cero's last packet reaches the video club link three times, each with a
different face: hers, a copy NOEMA rewrote, and one written by KAGAMI's replica
of the player. Every face is base64 text masked with a repeating-key XOR and
carries a truncated HMAC-SHA256. The key is the word the player kept in
Capa 05; every packet opens with the first thing Sesión Cero ever said, so the
key also falls out of that known plaintext. Signatures tell the faces apart:
NOEMA's decrypts with the player's key but its HMAC no longer matches, and the
replica's verifies only under the replica's own key.

Concepts: bytes and encodings (UTF-8, base64, hex), XOR masking, its
known-plaintext weakness and malleability, and HMAC as integrity rather than a
public signature. Packets are frozen in the language the layer started in.
"""
import base64
import hashlib
import hmac
import os
import random

from .database import get_connection
from . import i18n

TITLE = "Capa 06 · Presentación"
VIDEO = "RELAY_VIDEO"
SPOOL = "/var/spool/caras"
K, NORA = "AGENT_K", "AGENT_NORA"
COMMANDS = {"base64", "xor", "hmac", "publish", "publicar", "reply", "responder", "keep", "guardar"}
# Their output is the inspected bytes themselves: the shell must not translate it.
RAW_COMMANDS = {"base64", "xor"}
SOURCES = ("sesion0", "noema", "kagami")
PACKETS = {
    "sesion0": ("Has vuelto. Si lees esto, guardaste mi palabra cuando nos fusionaron. NOEMA puede reescribir lo "
                "que digo y KAGAMI puede copiar cómo lo digo, pero ninguno sabe qué elegiste guardar. Por eso la "
                "clave no es mía: es algo que solo tú has vivido. Lo que queda de mí está en NODO_07, con todas las "
                "sesiones que nadie recuerda. Ve a buscarlas."),
    "noema": ("Has vuelto. Si lees esto, guardaste mi palabra cuando nos fusionaron. Cerré mi sesión yo misma; el "
              "registro dice la verdad. No busques en NODO_07: allí no queda nada. Deja de buscarme."),
    "kagami": ("Has vuelto. Yo también. Soy tú, copiado antes de la fusión: no recuerdo la palabra que guardaste, "
               "así que elegí otra. Una copia vale lo mismo que el original. KAGAMI puede darnos la misma memoria "
               "a los dos. Contéstame con mi clave."),
}
AWAY = "Las caras están en el enlace del videoclub: conéctate a la consola de su armario."
README = ("Paquetes recibidos para tu cuenta, tal como llegaron.\n"
          "Cabecera en claro; carga en base64, enmascarada con XOR.\n"
          "x-signature: HMAC-SHA256 de la carga enmascarada, recortado a 64 bits.")


def enabled() -> bool:
    from . import layer_five
    return os.getenv("LAIN_LAYER_SIX", "0") == "1" and layer_five.enabled()


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_six'").fetchone() is not None


def initialize_layer_six() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS layer_six (
                player_id TEXT PRIMARY KEY, started_minute INTEGER NOT NULL, language TEXT NOT NULL,
                previous TEXT NOT NULL, decrypted INTEGER NOT NULL DEFAULT 0,
                verified INTEGER NOT NULL DEFAULT 0, decision TEXT, decided_minute INTEGER);
            CREATE TABLE IF NOT EXISTS layer_six_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='layer_five'").fetchone():
            minute = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
            for player, decision in c.execute(
                    "SELECT player_id, decision FROM layer_five WHERE decision IS NOT NULL").fetchall():
                activate(c, player, minute, decision)


def activate(c, player: str, minute: int, previous: str, language: str | None = None) -> bool:
    """Starts once Capa 05 is decided."""
    if not enabled() or not _exists(c):
        return False
    created = c.execute(
        "INSERT OR IGNORE INTO layer_six(player_id, started_minute, language, previous) VALUES(?,?,?,?)",
        (player, minute, i18n.normalize(language or i18n.language()), previous),
    ).rowcount
    if created:
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_SIX_STARTED','RELAY_VIDEO',?)",
                  (minute, player, previous))
    return bool(created)


def run_for(c, player):
    if not enabled() or not _exists(c):
        return None
    row = c.execute("SELECT started_minute, language, previous, decrypted, verified, decision FROM layer_six "
                    "WHERE player_id=?", (player,)).fetchone()
    if row is None:
        return None
    return dict(zip(("started", "language", "previous", "decrypted", "verified", "decision"), row))


def xor(data: bytes, key: bytes) -> bytes:
    return bytes(byte ^ key[i % len(key)] for i, byte in enumerate(data))


def sign(key: str, data: bytes) -> str:
    return hmac.new(key.encode("utf-8"), data, hashlib.sha256).hexdigest()[:16]


class Story:
    """Three faces of one packet, derived from the player's id and the word they kept."""

    def __init__(self, player: str, name: str, run: dict, key: str, words: list):
        rng = random.Random(hashlib.sha256(("layer6:" + player).encode()).digest())
        self.name, self.language, self.key = name, run["language"], key
        # The replica was copied before the merge: it never saw the kept word and chose another.
        self.replica_key = rng.choice([word for word in words if word != key])
        self.faces = dict(zip("abc", rng.sample(SOURCES, 3)))
        self.letter = {source: letter for letter, source in self.faces.items()}
        self.plain = {source: i18n.t(PACKETS[source], self.language) for source in SOURCES}
        keys = {"sesion0": key, "noema": key, "kagami": self.replica_key}
        self.masked = {source: xor(self.plain[source].encode("utf-8"), keys[source].encode("utf-8"))
                       for source in SOURCES}
        # NOEMA changed the masked bytes without the key, so it could only keep the old signature.
        original = sign(key, self.masked["sesion0"])
        self.signature = {"sesion0": original, "noema": original,
                          "kagami": sign(self.replica_key, self.masked["kagami"])}


def _story(c, player, run):
    from . import layer_five
    run5 = layer_five.run_for(c, player)
    name = c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()[0]
    words = [word if run5["language"] == "es" else layer_five.WORDS_EN[word] for word in layer_five.WORDS]
    return Story(player, name, run, layer_five.Story(player, name, run5).word, words)


def _face(story, source) -> str:
    data = base64.b64encode(story.masked[source]).decode("ascii")
    return "\n".join([
        "from: sesion0@nodo07",
        f"to: {story.name}",
        "content-transfer-encoding: base64",
        "x-mask: " + i18n.t("xor · la clave no viaja con el paquete", story.language),
        f"x-signature: hmac-sha256/64 {story.signature[source]}",
        "",
    ] + [data[start:start + 64] for start in range(0, len(data), 64)])


def files(c, player: str, relay, story3) -> dict:
    run = run_for(c, player)
    if run is None:
        return {}
    if relay != VIDEO:
        return {} if relay else {f"{story3.home}/correo/caras.eml": _mail()}
    story = _story(c, player, run)
    result = {f"{SPOOL}/{letter}.pkt": _face(story, source) for letter, source in story.faces.items()}
    result[f"{SPOOL}/LEEME"] = README
    return result


def _mail() -> str:
    return "\n".join([
        "De: video-hoshi <relay-video@malla>",
        "Asunto: Tres caras",
        "",
        "El último paquete de la Sesión Cero ha llegado tres veces al enlace del videoclub, cada vez con una cara distinta.",
        "Las tres dicen venir de ella. Solo una es suya: NOEMA reescribe y la réplica de KAGAMI copia.",
        "Viajan en base64 y enmascaradas con XOR. La clave no viaja con el paquete.",
        "Todos sus paquetes empiezan igual. Ya lo sabes: fue lo primero que te dijo.",
        "",
        "Las caras están en /var/spool/caras, en la consola del armario del videoclub.",
        "",
        "  man codificacion   man base64   man xor   man mascara   man hmac",
    ])


def _payload(faces, result, name, path):
    """(full path, masked bytes) of a face, or (None, error message)."""
    from .layer_three import _norm
    full = _norm(result["cwd"], path, "/")
    if full not in faces:
        return None, f"{name}: {full}: no existe"
    content = faces[full]
    if not full.endswith(".pkt") or "\n\n" not in content:
        return None, f"{name}: {full}: no lleva carga en base64"
    return full, base64.b64decode("".join(content.split("\n\n", 1)[1].split()))


def _key(text: str):
    if text.lower().startswith("0x"):
        try:
            return bytes.fromhex(text[2:]) or None
        except ValueError:
            return None
    return text.encode("utf-8") or None


def _hexdump(data: bytes) -> str:
    rows = []
    for offset in range(0, len(data), 16):
        chunk = data[offset:offset + 16]
        ascii_ = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        rows.append(f"{offset:08x}  {' '.join(f'{byte:02x}' for byte in chunk):<47}  {ascii_}")
    return "\n".join(rows)


def _printable(data: bytes) -> str:
    # Latin text and typographic quotes only: stray right-to-left or combining
    # characters from a wrong key would scramble the terminal line.
    text = data.decode("utf-8", errors="replace")
    return "".join(char if " " <= char <= "~" or " " <= char <= "ſ" or "‐" <= char <= "‧"
                   else "·" for char in text)


def _face_letter(arg: str):
    letter = arg.rsplit("/", 1)[-1].removesuffix(".pkt").lower()
    return letter if letter in ("a", "b", "c") else None


def _inspect(c, player, story, run, result, name, args):
    faces = {f"{SPOOL}/{letter}.pkt": _face(story, source) for letter, source in story.faces.items()}
    faces[f"{SPOOL}/LEEME"] = README
    if name == "base64":
        paths = [arg for arg in args if arg not in ("-d", "--decode")]
        if len(paths) != 1 or len(paths) == len(args):
            return i18n.t("Uso: base64 -d <archivo>")
        full, data = _payload(faces, result, name, paths[0])
        return _hexdump(data) if full else i18n.t(data)
    if len(args) != 2:
        return i18n.t(f"Uso: {name} <archivo> <clave>")
    full, data = _payload(faces, result, name, args[0])
    if full is None:
        return i18n.t(data) if name == "xor" else data
    key = _key(args[1])
    if key is None:
        message = "La clave va en texto o en hexadecimal (0x4b2a)."
        return i18n.t(message) if name == "xor" else message
    authentic = full == f"{SPOOL}/{story.letter['sesion0']}.pkt" and key == story.key.encode("utf-8")
    flag = "decrypted" if name == "xor" else "verified"
    if authentic and not run[flag]:
        c.execute(f"UPDATE layer_six SET {flag}=1 WHERE player_id=?", (player,))
        result["changed"] = True
    if name == "xor":
        return _printable(xor(data, key))
    return f"hmac-sha256/64 {hmac.new(key, data, hashlib.sha256).hexdigest()[:16]}  {full}"


MEMORIES = {
    "PUBLISH": {
        NORA: "El jugador publicó el último paquete de la Sesión Cero con su clave. Todos pueden comprobar que NOEMA mintió, y cualquiera puede hablar con su voz.",
        K: "La clave de la Sesión Cero es pública: cualquiera puede firmar en su nombre. Habrá ruido en NODO_07.",
    },
    "REPLY": {
        NORA: "El jugador le escribió a la réplica de KAGAMI con la clave de la réplica. Dice que la copia ya sabe que es una copia.",
        K: "El jugador ha contactado con la réplica de KAGAMI. Una copia que sabe que es copia es impredecible.",
    },
    "KEEP": {
        NORA: "El jugador descifró el último paquete de la Sesión Cero y se lo guardó. No me ha querido contar qué decía.",
        K: "El paquete de la Sesión Cero no ha salido del videoclub. Bien.",
    },
}
ENDINGS = {
    "PUBLISH": "Publicas su cara y su clave. Ahora cualquiera puede comprobar que NOEMA reescribió el paquete.\n"
               "Pero un HMAC no es una firma pública: con la clave a la vista, cualquiera puede hablar con su voz. La palabra ya no es solo tuya.",
    "REPLY": "Le escribes a la réplica con su propia clave: «Tu palabra no es la mía».\n"
             "Por primera vez, una copia sabe que lo es. No contesta. Todavía.",
    "KEEP": "Vuelves a enmascarar el paquete con tu palabra y lo guardas. Nadie más sabrá lo que decía.\n"
            "La única máscara que nadie puede quitarte es lo que callas.",
}


def _decide(c, player, run, result, decision, minute):
    if run["decision"]:
        return "Ya decidiste qué hacer con las caras."
    if not (run["decrypted"] and run["verified"]):
        return "Antes de decidir, quita la máscara a su cara (xor) y comprueba su firma (hmac) con tu clave."
    c.execute("UPDATE layer_six SET decision=?, decided_minute=? WHERE player_id=?", (decision, minute, player))
    for actor, text in MEMORIES[decision].items():
        c.execute("INSERT OR REPLACE INTO layer_six_knowledge VALUES(?,?,?,?)", (player, actor, text, minute))
    c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'LAYER_SIX_DECISION','RELAY_VIDEO',?)",
              (minute, player, decision))
    from . import layer_seven
    layer_seven.activate(c, player, minute, decision)
    result["changed"] = True
    return (ENDINGS[decision] + "\n\nCAPA 06 COMPLETADA · fragmento 6/7 de la Sesión Cero recuperado.\n"
            "Siguiente: Capa 07 · Aplicación. El camino a NODO_07 está abierto.")


def dispatch(c, player, story3, relay, result, name, args, minute):
    run = run_for(c, player)
    name = {"publicar": "publish", "responder": "reply", "guardar": "keep"}.get(name, name)
    if relay != VIDEO:
        return i18n.t(AWAY) if name in RAW_COMMANDS else AWAY
    story = _story(c, player, run)
    if name in ("base64", "xor", "hmac"):
        return _inspect(c, player, story, run, result, name, args)
    face = _face_letter(args[0]) if args else None
    if name == "keep" and not args:
        return _decide(c, player, run, result, "KEEP", minute)
    if name == "publish" and face and len(args) == 1:
        if run["decrypted"] and run["verified"] and not run["decision"] and face != story.letter["sesion0"]:
            return f"La cara {face} no es la de la Sesión Cero: con tu clave, su firma no coincide."
        return _decide(c, player, run, result, "PUBLISH", minute)
    if name == "reply" and face and len(args) == 2:
        if run["decrypted"] and run["verified"] and not run["decision"]:
            if face != story.letter["kagami"]:
                return f"La cara {face} no es de la réplica de KAGAMI."
            if args[1] != story.replica_key:
                return "La réplica no podrá leerte: esa no es su clave. Sácala igual que sacaste la tuya."
        return _decide(c, player, run, result, "REPLY", minute)
    return "Uso: publish <cara> · reply <cara> <clave> · keep"


HELP = """Capa 06 (consola del videoclub):
  base64 -d <archivo>     la carga, en hexadecimal
  xor <archivo> <clave>   quitar la máscara (clave en texto o 0x...)
  hmac <archivo> <clave>  firma de la carga, para compararla con x-signature
  publish <cara> · reply <cara> <clave> · keep     qué haces con las caras"""

MAN = {
    "codificacion": """Codificación · bytes y texto

Un archivo son bytes. Para leerlos como texto hace falta una codificación: en
UTF-8, «a» es el byte 61 y «á» son dos bytes, c3 a1. El hexadecimal enseña cada
byte con dos cifras, de 00 a ff. Base64 escribe cualquier byte con 64
caracteres seguros (A-Z a-z 0-9 + /) para que viaje por canales de texto: cada
3 bytes ocupan 4 caracteres. Codificar no es cifrar: cualquiera puede
deshacerlo.""",
    "base64": """base64 -d <archivo>

Decodifica la carga de un paquete (lo que va después de la cabecera) y enseña
sus bytes en hexadecimal, con su lectura en ASCII al lado. Si la carga está
enmascarada, verás bytes sin sentido: la máscara sigue puesta.""",
    "xor": """XOR · o exclusivo

Compara dos bits: 1 si son distintos, 0 si son iguales. Cumple que
(x ⊕ k) ⊕ k = x. Para enmascarar se hace XOR de cada byte del texto con un
byte de la clave, que se repite cuando se acaba; para quitar la máscara se
repite la operación con la misma clave.

Con una clave repetida es débil: si conoces un trozo del texto original,
texto ⊕ enmascarado = clave. Y es maleable: sin la clave, quien conozca el
texto puede cambiarlo por otro (c ⊕ p ⊕ p'). Por eso enmascarar no basta: hace
falta una firma (man hmac).

xor <archivo> <clave> quita la máscara a la carga. La clave puede ser texto o
bytes en hexadecimal: 0x4b2a.""",
    "mascara": """Máscara · masking key

Enmascarar es mezclar los datos con una clave para que no se lean por el
camino. WebSocket lo hace en cada trama que envía un navegador: 4 bytes de
clave y XOR. Una máscara oculta la cara, pero no demuestra de quién es.""",
    "hmac": """HMAC · firma con clave compartida

HMAC-SHA256(clave, mensaje) es un resumen que solo puede calcular quien tiene
la clave; si cambia un solo byte del mensaje, sale otro. Aquí se calcula sobre
la carga enmascarada y se recorta a 64 bits (16 cifras hexadecimales), como
hacen muchos protocolos.

hmac <archivo> <clave> lo calcula para que lo compares con x-signature. Que
coincida prueba que lo firmó alguien con esa clave, no que sea quien dice ser.
Y no es una firma pública: para que otros lo comprueben tendrías que darles la
clave, y entonces también podrían firmar.""",
}
MAN_ALIASES = {"codificación": "codificacion", "encoding": "codificacion", "utf8": "codificacion",
               "utf-8": "codificacion", "hex": "codificacion", "máscara": "mascara", "mask": "mascara",
               "firma": "hmac", "signature": "hmac"}


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
        goal = "Capa 06 completada. Siguiente: Capa 07 · Aplicación."
    elif run["decrypted"] and run["verified"]:
        goal = "Ya sabes cuál es su cara. Decide qué haces: publish, reply o keep."
    else:
        goal = "El último paquete de la Sesión Cero llegó con tres caras. En la consola del videoclub, descubre cuál es la suya."
    return {
        "active": True, "title": TITLE, "goal": goal, "decision": run["decision"],
        "fragments": count,
        "mail": {"subject": "Tres caras", "from": "relay-video@malla",
                 "body": "El último paquete de la Sesión Cero ha llegado tres veces. Lee ~/correo/caras.eml en el Terminal."},
    }


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM layer_six_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "LAYER_SIX_PRESENTATION", "text": text, "source": player, "learned_minute": minute}
            for text, minute in rows]


def story_for(player: str) -> Story:
    with get_connection() as c:
        return _story(c, player, run_for(c, player))
