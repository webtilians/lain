"""Hints: `pista` in any terminal, for the step the player is on.

Each step has three hints: the idea, the method, and finally the concrete
values of the player's own game. The level starts over on every new step.

`pista` gives the first one (Nora's) and says who knows more: a neighbour whose
trade fits the layer, and the real players who already finished it. Talking
to that neighbour and asking ("Me han dicho que sabes de esto…") gives the
second hint, and asking again the third. Everyone who helped remembers it.
Without residents in the world, `pista` climbs the three levels itself.
"""
import os

from .database import get_connection
from . import i18n

NORA = "AGENT_NORA"
COMMANDS = {"pista", "hint"}
LAYERS = ("layer_one", "layer_two", "layer_three", "layer_four", "layer_five", "layer_six", "layer_seven")
TITLES = {"layer_one": "Capa 01 · Física", "layer_two": "Capa 02 · Enlace", "layer_three": "Capa 03 · TTL",
          "layer_four": "Capa 04 · Transporte", "layer_five": "Capa 05 · Sesión",
          "layer_six": "Capa 06 · Presentación", "layer_seven": "Capa 07 · Aplicación"}


# Who in the neighbourhood knows about each layer, and why (their trade).
EXPERTS = {
    "layer_one": ("RESIDENT_027", "el aula de informática", "sabe de electrónica: cables, señales y osciloscopios"),
    "layer_two": ("RESIDENT_049", "la librería", "colecciona conmutadores y tarjetas de red antiguas"),
    "layer_three": ("RESIDENT_035", "la estación", "se sabe todas las rutas y cuántos saltos tiene cada una"),
    "layer_four": ("RESIDENT_001", "el barrio", "sabe lo que es esperar un acuse de recibo"),
    "layer_five": ("RESIDENT_045", "el videoclub", "lleva préstamos que caducan y copias que se pisan"),
    "layer_six": ("RESIDENT_056", "Kissa Café", "escribe en clave y le encantan los cifrados"),
    "layer_seven": ("RESIDENT_025", "el aula de informática", "mantiene los servidores del aula: nombres, direcciones y páginas"),
}
EXPERT_OPENERS = {2: "«Algo sé de esto. Te explico cómo lo haría yo:»",
                  3: "«Vale, con tus datos. Escúchame bien:»"}


def enabled() -> bool:
    from . import layer_three
    return os.getenv("LAIN_HINTS", "0") == "1" and layer_three.enabled()


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='hint_progress'").fetchone() is not None


def initialize_hints() -> None:
    if not enabled():
        return
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS hint_progress (
                player_id TEXT NOT NULL, layer TEXT NOT NULL, step TEXT NOT NULL, level INTEGER NOT NULL,
                asked INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(player_id, layer));
            CREATE TABLE IF NOT EXISTS hint_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, text TEXT NOT NULL,
                minute INTEGER NOT NULL, PRIMARY KEY(player_id, actor_id));
        """)


def run_for(c, player):
    return {} if enabled() and _exists(c) else None


def _module(name):
    from importlib import import_module
    return import_module(f"server.world_core.{name}")


def _runs(c, player) -> dict:
    """Every layer the player has opened, with its saved state."""
    runs = {}
    for name in LAYERS:
        module = _module(name)
        run = module._run(c, player) if name == "layer_three" else module.run_for(c, player)
        if run is not None:
            runs[name] = run
    return runs


def current(runs: dict):
    """The lowest open layer until Capa 03 is decided; then the main thread first."""
    three = runs.get("layer_three")
    order = LAYERS[3:] + LAYERS[:3] if three and three.get("decision") else LAYERS
    return next((name for name in order if name in runs and not runs[name].get("decision")), None)


def _decide(what: str, options: str, example: str):
    # The pieces are translated first, so the whole sentence can be translated around them.
    what, options, example = i18n.t(what), i18n.t(options), i18n.t(example)
    return ("decide", [
        f"Ya has resuelto lo difícil de esta capa. Ahora toca decidir {what}.",
        f"Tienes tres opciones: {options}. Ninguna es incorrecta; Nora y K recordarán la que elijas.",
        f"Por ejemplo: {example}",
    ])


def _layer_one(c, player, run):
    from . import layer_one
    if run["decoded"]:
        return _decide("qué haces con el cable, en la consola del aula de informática", "empalmar, dejar o puentear", "empalmar")
    story = layer_one._story(c, player, run)
    return ("leer", [
        "El cable cortado está en el armario del aula de informática. Conéctate a su consola y mira la señal: "
        "scope naranja y scope verde.",
        "Solo un par lleva datos. 10BASE-T va a 10 Mbit/s y Manchester usa dos medios bits por bit, así que la línea "
        "cambia 20 millones de veces por segundo: divide el muestreo (MS/s) entre 20 y sabrás cuántas muestras "
        "forman un medio bit (man señal, man manchester).",
        f"Los datos van por el par {story.pair}, con {story.samples} muestras por medio bit. Escribe "
        f"decode {story.pair} {story.samples} {story.convention}.",
    ])


def _layer_two(c, player, run, story3):
    from . import layer_two
    story = layer_two._story(c, player, run, story3.navi)
    if run["seen"]:
        return _decide("qué haces con tu copia", "shutdown <puerto> en el andén, una dirección nueva con ip link set address "
                       "<mac> en tu Navi, o compartir", f"shutdown {story.replica_port} (en la consola del andén)")
    first, second = sorted((story.port, story.replica_port))
    return ("puertos", [
        "Mira tu dirección en el Terminal de casa (ip link) y luego conéctate a la consola del armario del andén: "
        "show mac y show log.",
        "show log dice entre qué dos puertos salta tu dirección. capture <puerto> enseña las tramas de cada uno: "
        "compara sus latidos con el último que da ip link, y usa fcs para descartar las tramas dañadas.",
        f"Tu dirección salta entre los puertos {first} y {second}. El tuyo es el {story.port}, con latidos hasta "
        f"seq {story.seq}; el otro, el {story.replica_port}, es la copia. Escribe capture {story.replica_port}.",
    ])


def _layer_three(c, player, run, story3):
    from .layer_three import RELAYS
    if run["exposed"]:
        return _decide("qué haces con el paquete de la Sesión Cero", f"reenviar {story3.packet} o soltar {story3.packet}",
                       f"reenviar {story3.packet}")
    if run["assembled"]:
        return ("diario", [
            "Ya tienes el mensaje. Ahora comprueba el diario de la Wired, en el Terminal de casa: "
            "cat /var/log/wired/diario.",
            "Cada entrada guarda el hash (prev) de la anterior. sha256 /var/log/wired/diario <línea> calcula el de "
            "una línea: compáralo con el prev de la siguiente. Donde no coincida, alguien la reescribió (man cadena).",
            f"La entrada reescrita es la {story3.forged_number:04d}. Escribe denunciar {story3.forged_number}.",
        ])
    host, place, label = RELAYS[story3.drop]
    label = i18n.t(label)
    return ("ruta", [
        f"El paquete murió por el camino: averigua en qué armario. En casa, traceroute {story3.packet} y "
        "cat /net/rutas te dan los saltos y cuánto lo retuvo cada router.",
        "Salió con TTL 8. Cada router resta 1, pero los de la norma rfc791 restan los segundos que lo retuvieron "
        "(como mínimo 1). Cuenta salto a salto hasta llegar a 0: ese router es el armario (man ttl, man rutas). "
        "Allí, en su consola, se ensambla.",
        f"Murió en {host} ({label}). Ve allí y mira /var/spool/descartes: ordena los segmentos de {story3.packet} "
        "por seq, quita el repetido y el que no cumple su sha256, y escribe ensamblar "
        f"{story3.packet} <archivos en orden>.",
    ])


def _layer_four(c, player, run):
    from . import layer_four
    from .layer_three import RELAYS
    story = layer_four._story(c, player, run)
    host, place, label = RELAYS[story.nora_relay]
    label = i18n.t(label)
    if run["decision"] is None and run["complete"] and run.get("found_nora"):
        return _decide(f"qué haces con la conexión de Nora, en la consola de {host}", "relevar los keepalive, cerrarla con FIN o cortarla con RST",
                       f"keepalive nodo07; o bien send nodo07 FIN+ACK seq={story.ka_seq} ack={story.ka_ack} y "
                       f"después send nodo07 ACK seq={story.ka_seq + 1} ack={story.ka_ack + 1}")
    if run["complete"]:
        return ("ttl", [
            "El mensaje dice no venir de tan lejos. Fíjate en el TTL de sus paquetes en tcpdump.",
            "Casi todos los sistemas empiezan con TTL 64: 64 menos el TTL que llega son los saltos recorridos. "
            "/net/vecinos dice a cuántos saltos está cada armario (man ttl). Ve a ese armario y usa tcpdump en su "
            "consola.",
            f"Llega con TTL {64 - story.distances[story.nora_relay]}: está a {story.distances[story.nora_relay]} "
            f"saltos, en {host} ({label}). Ve allí y escribe tcpdump en su consola.",
        ])
    if run["isn_l"] is not None:
        return ("flujo", [
            "Llega un mensaje en varios segmentos. Míralos en tcpdump y confirma lo que tienes seguido con "
            "send nodo07 ACK ack=<n>.",
            "El ACK es acumulativo: confirma el primer byte que te falta, no el último que viste. Si falta un "
            "segmento, repite ese ACK tres veces (retransmisión rápida) o espera con wait (man ack, man retransmision).",
            f"Falta el segmento que empieza en seq {story.gap}. Escribe send nodo07 ACK ack={story.gap} tres veces y, "
            f"cuando llegue, confirma hasta el final: send nodo07 ACK ack={story.end}.",
        ])
    return ("saludo", [
        "Alguien llama a tu puerto 4004. En el Terminal de casa: tcpdump para ver su SYN y netstat para ver la "
        "conexión a medias.",
        "Para aceptar una conexión TCP se contesta con SYN+ACK: tu propio número de secuencia (el que quieras) y "
        "ack = su número de secuencia + 1 (man tcp).",
        f"Su SYN trae seq {story.isn_r}. Escribe send nodo07 SYN+ACK seq=5000 ack={story.isn_r + 1}.",
    ])


def _layer_five(c, player, run):
    from . import layer_five
    if run["committed"]:
        return _decide("qué sesión conserva la cuenta, en la consola del andén", "lease s1, lease s0 o expire s0", "lease s1")
    story = layer_five._story(c, player, run)
    only_s0 = [f for f in layer_five.FIELDS if story.resolution(f)[0] == "auto" and story.s0[f] != story.base[f]
               and story.s1[f] == story.base[f]]
    conflicts = [f for f in layer_five.FIELDS if story.resolution(f)[0] == "conflict"]
    return ("fusión", [
        "En la consola del armario del andén, sessions enseña las dos sesiones. Sus estados están en "
        "/var/lib/sesiones: base.json, s0.json y s1.json.",
        "Compara cada campo con base.json: si cambió en una sola sesión, gana ese cambio; si cambió en las dos, eliges "
        "tú. merge <campo> <base|s0|s1> elige, y commit version=<la siguiente> token=<el del lease> escribe "
        "(man merge, man version, man fencing).",
        f"Coge de s0: {', '.join(only_s0) or i18n.t('ninguno')}. Conflictos, eliges tú entre s0 y s1: "
        f"{', '.join(conflicts)}. El resto, de s1. Al final: commit version={story.version + 1} token={story.token}.",
    ])


def _layer_six(c, player, run):
    from . import layer_six
    story = layer_six._story(c, player, run)
    letter = story.letter["sesion0"]
    if run["decrypted"] and run["verified"]:
        return _decide("qué haces con su último paquete, en la consola del videoclub", "publish <cara>, reply <cara> <clave> o keep",
                       f"publish {letter}")
    return ("caras", [
        "Las tres caras están en /var/spool/caras, en la consola del videoclub. base64 -d enseña sus bytes y "
        "xor <archivo> <clave> les quita la máscara.",
        "La clave es la palabra que guardaba la Sesión Cero en la Capa 05. Si no la recuerdas: todos sus paquetes "
        "empiezan por «Has vuelto.», así que xor <cara> \"Has vuelto.\" enseña la clave repetida. Luego compara "
        "hmac <cara> <clave> con su x-signature (man xor, man hmac).",
        f"La clave es {story.key} y la cara de la Sesión Cero es la {letter}. Escribe "
        f"xor /var/spool/caras/{letter}.pkt {story.key} y hmac /var/spool/caras/{letter}.pkt {story.key}.",
    ])


def _layer_seven(c, player, run):
    from . import layer_seven
    story = layer_seven._story(c, player)
    auth = f'--resolve nodo07.wired:80:{story.node_ip} -u "{story.name}:{story.word}"'
    if run["inside"]:
        return _decide("cómo termina tu historia", "persistir (PUT), replicarte (POST al espejo de KAGAMI) o desconectarte (DELETE)",
                       f"curl -X PUT {auth} http://nodo07.wired/registro/{story.name}")
    return ("nodo07", [
        "NODO_07 se alcanza desde cualquier terminal. dig nodo07.wired dice que no existe… según NOEMA. "
        "dig NS wired lista los otros servidores de nombres.",
        "Pregúntale a otro: dig @ns.circulos.wired nodo07.wired. Después habla HTTP con curl: el servidor atiende "
        "por nombre (cabecera Host) y pide autenticación Basic con tu nombre y la palabra de la Sesión Cero "
        "(man host, man auth).",
        f"Escribe curl {auth} http://nodo07.wired/sesiones",
    ])


def _plan(c, player, name, run):
    from .layer_three import _run, _story
    story3 = _story(c, player, _run(c, player))
    if name == "layer_one":
        return _layer_one(c, player, run)
    if name == "layer_two":
        return _layer_two(c, player, run, story3)
    if name == "layer_three":
        return _layer_three(c, player, run, story3)
    return {"layer_four": _layer_four, "layer_five": _layer_five, "layer_six": _layer_six,
            "layer_seven": _layer_seven}[name](c, player, run)


def files(c, player: str, relay, story3) -> dict:
    return {}


def expert(c, layer: str):
    """(actor_id, name, role, place, why) of the neighbour who knows the layer, if they live in this world."""
    actor, place, why = EXPERTS[layer]
    row = c.execute("SELECT name FROM agents WHERE id=?", (actor,)).fetchone()
    if row is None:
        return None
    from .residents import load_catalog
    role = next((item["role"] for item in load_catalog() if item["id"] == actor), "")
    return actor, row[0], role, place, why


def finished_by(c, player: str, layer: str) -> list[str]:
    """Real players who already finished this layer: they can be asked in the chat."""
    if c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (layer,)).fetchone() is None:
        return []
    return [name for (name,) in c.execute(
        f"SELECT a.name FROM {layer} l JOIN agents a ON a.id=l.player_id WHERE l.decision IS NOT NULL "
        "AND l.player_id<>? AND a.controller_type='HUMAN' ORDER BY a.name LIMIT 3", (player,)).fetchall()]


def _level(c, player: str, layer: str, step: str) -> int:
    row = c.execute("SELECT step, level FROM hint_progress WHERE player_id=? AND layer=?", (player, layer)).fetchone()
    return row[1] if row and row[0] == step else 0


def _save(c, player: str, layer: str, step: str, level: int) -> None:
    c.execute("INSERT INTO hint_progress(player_id, layer, step, level, asked) VALUES(?,?,?,?,1) "
              "ON CONFLICT(player_id, layer) DO UPDATE SET step=excluded.step, level=excluded.level, asked=asked+1",
              (player, layer, step, level))


def _header(level: int, layer: str) -> str:
    return i18n.t(f"PISTA {level}/3 · {i18n.t(TITLES[layer])}")


def dispatch(c, player, story3, relay, result, name, args, minute):
    runs = _runs(c, player)
    if args and args[0].isdigit() and 1 <= int(args[0]) <= 7:
        layer = LAYERS[int(args[0]) - 1]
        if layer not in runs:
            return i18n.t(f"Todavía no has llegado a la Capa 0{args[0]}.")
        if runs[layer].get("decision"):
            return i18n.t(f"La Capa 0{args[0]} ya está completada.")
    else:
        layer = current(runs)
    if layer is None:
        return i18n.t("Has completado todas las capas que tienes abiertas. No hay nada en lo que pueda ayudarte.")
    step, texts = _plan(c, player, layer, runs[layer])
    known = _level(c, player, layer, step)
    who = expert(c, layer)
    memory = f"El jugador me pidió ayuda con la {TITLES[layer]}. Le di pistas sin resolverle nada que no quisiera."
    c.execute("INSERT OR REPLACE INTO hint_knowledge VALUES(?,?,?,?)", (player, NORA, memory, minute))
    result["changed"] = True
    if who is None:
        # No neighbours to ask: Nora climbs the three levels herself.
        level = min(known + 1, 3)
        _save(c, player, layer, step, level)
        lines = [_header(level, layer), "Nora: " + i18n.t(texts[level - 1])]
        if level < 3:
            lines.append(i18n.t("(Escribe pista otra vez y te daré una más clara.)"))
        return "\n".join(lines)
    _save(c, player, layer, step, max(known, 1))
    actor, person, role, place, why = who
    lines = [_header(1, layer), "Nora: " + i18n.t(texts[0]),
             i18n.t(f"Quien sabe de esto es {person} ({i18n.t(role)}), en {i18n.t(place)}: {i18n.t(why)}. "
                    "Ve a buscarle y pregúntale.")]
    players = finished_by(c, player, layer)
    if players:
        lines.append(i18n.t(f"También la han superado: {', '.join(players)}. Pregúntales por el chat."))
    # What the neighbour already said, to read it again.
    for level in range(2, known + 1):
        lines += ["", _header(level, layer), f"{person}: " + i18n.t(texts[level - 1])]
    return "\n".join(lines)


def expert_layer(c, player: str, actor: str):
    """The layer this neighbour can help the player with now: they were sent here and have more to learn."""
    if not enabled() or not _exists(c):
        return None
    runs = _runs(c, player)
    layer = current(runs)
    if layer is None or EXPERTS[layer][0] != actor:
        return None
    step, _ = _plan(c, player, layer, runs[layer])
    return layer if _level(c, player, layer, step) >= 1 else None


def consult(c, player: str, actor: str, minute: int) -> str:
    """The neighbour's answer: the next hint for the player's step, the method first and then their values."""
    layer = expert_layer(c, player, actor)
    if layer is None:
        raise ValueError("NO_HINT_HERE")
    runs = _runs(c, player)
    step, texts = _plan(c, player, layer, runs[layer])
    level = min(max(_level(c, player, layer, step), 1) + 1, 3)
    _save(c, player, layer, step, level)
    memory = (f"El jugador vino a preguntarme por la {TITLES[layer]} porque le dijeron que yo sabía de eso. "
              "Le ayudé con lo que sé.")
    c.execute("INSERT OR REPLACE INTO hint_knowledge VALUES(?,?,?,?)", (player, actor, memory, minute))
    # Saved in Spanish like every conversation turn; it is translated line by line when shown.
    reply = [f"PISTA {level}/3 · {TITLES[layer]}", EXPERT_OPENERS[level], texts[level - 1]]
    if level < 3:
        reply.append("(Si con esto no te basta, vuelve a preguntarme.)")
    return "\n".join(reply)


def ask_line(layer: str) -> str:
    return f"Me han dicho que sabes de esto. ¿Me ayudas con la {TITLES[layer]}?"


HELP = """Ayuda:
  pista [capa]            una pista para lo que estás haciendo y quién sabe más"""
MAN = {"pista": """pista [capa]

Nora te da la primera pista para el paso en el que estás (la idea) y te dice
quién sabe más: alguien del barrio cuyo oficio tiene que ver con esa capa, y
los jugadores que ya la superaron. Ve a hablar con esa persona y pregúntale:
te explicará el método y, si vuelves a preguntar, los valores de tu propia
partida. pista te recuerda después lo que te contó. Con un número (pista 3)
pides ayuda con esa capa."""}
MAN_ALIASES = {"hint": "pista", "hints": "pista", "pistas": "pista", "ayuda": "pista"}
# The hint is translated here, sentence by sentence, so the shell must not translate it again.
RAW_COMMANDS = {"pista", "hint"}


def layer_actor_context(actor: str, player: str) -> list:
    with get_connection() as c:
        if not _exists(c):
            return []
        rows = c.execute("SELECT text, minute FROM hint_knowledge WHERE player_id=? AND actor_id=?",
                         (player, actor)).fetchall()
    return [{"id": "HINTS_ASKED", "text": text, "source": player, "learned_minute": minute} for text, minute in rows]
