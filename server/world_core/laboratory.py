"""The Laboratorio de Inteligencias' own calls, the road to Kumo (EVOLUCION.md, section 4).

KU-01 · tokens and context: what a language model reads and what it no longer sees.
KU-02 · tools: what an agent may do on your computer, written as your own rules.
Whoever finishes KU-02 wakes Kumo, the agent on their home computer (kumo.py).

The centres, the registry and the threshold are in research.py; this module holds what
only these calls have: their articles, the Laboratory's tokenizer (`tokens`), a
conversation that no longer fits in Kumo's window, and the checks of both calls.
"""
import hashlib
import random
import re

from . import i18n

TAKESHI = "RESIDENT_025"
COMMANDS = {"tokens"}
RAW_COMMANDS = set()
FOLDER = "/indara/laboratorio/ku-01"
CONVERSATION = f"{FOLDER}/conversacion.txt"

CALLS = {
    "KU-01": {
        "centre": "laboratorio",
        "title": "Lo que ve un modelo: tokens y contexto",
        "summary": "Un modelo de lenguaje no lee letras ni palabras: lee tokens. Y solo ve los que le caben en su\n"
                   "ventana; lo demás no existe para él. Takeshi busca a quien lo entienda contando.",
        "articles": ("tokens", "contexto"),
        "road": True,  # the road to Kumo: always open, not counted when the watcher picks a centre
        "threshold": 3,
        "unlock": "memoria",
        "memory": "Terminó la convocatoria KU-01 del Laboratorio: sabe qué es un token y por qué un modelo "
                  "olvida lo que no le cabe en la ventana.",
    },
    "KU-02": {
        "centre": "laboratorio",
        "title": "Herramientas: lo que le dejas hacer a tu agente",
        "summary": "Un agente no solo habla: pide usar herramientas en tu ordenador. Quien decide si puede es tu\n"
                   "programa, con tus reglas. Takeshi busca a quien sepa escribirlas antes de despertar a Kumo.",
        "articles": ("herramientas",),
        "road": True,
        "threshold": 3,
        "unlock": "cadenas",
        "reward": "KUMO DESPIERTA · El agente de tu ordenador ya puede ayudarte: kumo <pregunta> (man kumo).",
        "memory": "Terminó la convocatoria KU-02 del Laboratorio: escribió las reglas de lo que puede hacer "
                  "su agente y despertó a Kumo en su ordenador.",
    },
}
TECHS = {
    "memoria": {"title": "Memoria de Kumo",
                "text": "Indara aprende a guardar el contexto: Kumo recuerda tus últimas preguntas.",
                "line": "Desde hoy, Kumo tiene en cuenta tus tres últimas preguntas al contestar.",
                "memory": "Kumo ya recuerda las últimas preguntas de cada uno: salió de la convocatoria KU-01 "
                          "del Laboratorio de Inteligencias."},
    "cadenas": {"title": "Cadenas de herramientas",
                "text": "Indara aprende a fiarse de los agentes con reglas: pueden encadenar más órdenes.",
                "line": "Desde hoy, Kumo puede usar hasta cuatro órdenes seguidas para contestarte.",
                "memory": "Los agentes como Kumo ya encadenan varias órdenes, siempre dentro de las reglas de "
                          "su dueño: salió de la convocatoria KU-02 del Laboratorio de Inteligencias."},
}

ARTICLES = {
    "tokens": """Tokens · Laboratorio de Inteligencias · T. Uno

Un modelo de lenguaje no lee letras ni palabras: lee tokens. Antes de nada,
el texto se trocea, y cada trozo se cambia por un número. El modelo solo ve
esa lista de números; con ella calcula cuál es el token más probable que
sigue, lo añade y vuelve a empezar.

Los trozos no son al azar. Las palabras frecuentes son un solo token; las
raras se parten en piezas que sí se repiten mucho. Por eso un texto en un
idioma poco frecuente, o lleno de nombres raros, gasta más tokens.

El tokenizador del Laboratorio es de juguete, pero funciona igual de
idea (orden tokens):
- las palabras frecuentes (de, la, que, red, modelo, the, and…) son 1 token;
- las demás se parten en trozos de hasta 4 letras, desde el principio:
  entrelazado = entr + elaz + ado, 3 tokens;
- cada signo de puntuación es 1 token, y los números van de 3 en 3 cifras;
- los espacios no cuentan: van pegados a la palabra que sigue.

Los tokens importan porque todo se mide en ellos: lo que cuesta una
pregunta, lo que tarda la respuesta y, sobre todo, lo que le cabe al modelo
en la ventana (laboratorio leer contexto).""",
    "contexto": """La ventana de contexto · Laboratorio de Inteligencias · T. Uno

Un modelo no recuerda nada entre una pregunta y otra. Cada vez que le
hablas, el programa que lo usa le manda otra vez todo lo que tiene que
saber: las instrucciones, la conversación y tu pregunta. Eso es el
contexto.

Pero el contexto tiene un tamaño máximo, la ventana, medido en tokens. Si
la conversación es más larga, algo se queda fuera. Lo habitual es quedarse
con lo más reciente: se empieza por el mensaje más nuevo y se van añadiendo
los anteriores, uno a uno, mientras quepan enteros. El primero que ya no
cabe, y todos los anteriores, para el modelo no han existido nunca.

Por eso un asistente «olvida» lo que le dijiste al principio de una charla
larga: no es que lo olvide, es que ya no se lo mandan.

Para contar los tokens de cada línea de un archivo: tokens -l <archivo>.""",
    "herramientas": """Herramientas · Laboratorio de Inteligencias · T. Uno

Un agente es un modelo que, además de contestar, puede pedir que se haga
algo: leer un archivo, buscar una palabra, calcular un hash. Lo pide con una
orden, como la escribirías tú, y el programa que lo rodea decide si la
ejecuta. El modelo nunca toca tu ordenador directamente.

Esa decisión es lo más importante de un agente, y la escribe su dueño: unas
reglas, en orden. Para cada orden que pide el agente:
- se mira la primera regla que encaja con la orden y con la ruta del archivo;
- si dice permitir, se ejecuta; si dice prohibir, no;
- si no encaja ninguna, se prohíbe. Lo que no está permitido, no se hace.

Las rutas se comprueban ya resueltas: ~/../../etc/clave es /etc/clave, por
mucho que empiece por ~. En los patrones, * vale por cualquier cosa y ~ es
tu carpeta de casa.

Un buen dueño deja leer lo que el agente necesita para ayudar y nada más:
que no lea secretos, que no se conecte a nada por su cuenta, que no borre y,
sobre todo, que nunca entregue una respuesta en tu nombre.

En tu ordenador, las reglas de Kumo se escriben con kumo regla (man kumo).""",
}
ARTICLE_ALIASES = {"token": "tokens", "context": "contexto", "ventana": "contexto", "tools": "herramientas",
                   "herramienta": "herramientas"}

MAIL = ("De: takeshi <takeshi@laboratorio.indara>\nAsunto: el Laboratorio y Kumo\n\n"
        "Ayudo en el aula de informática y llevo el Laboratorio de Inteligencias, en Indara.\n"
        "Tu ordenador trae un agente dormido, Kumo. Antes de despertarlo tienes que entender dos cosas:\n"
        "qué ve un modelo (KU-01) y qué le dejas hacer (KU-02).\n"
        "Empieza con laboratorio ver KU-01. Y cuenta los tokens antes de fiarte de nadie.")


def run_for(c, player):
    """Open with the research centres: to every player already connected to Indara."""
    from . import research
    return research.run_for(c, player)


# --- the tokenizer ---------------------------------------------------------------------

VOCAB = set("""
de la que el en y a los se del las un por con no una su para es al lo como más pero sus le ya o
este sí si porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos
todos uno les ni otro otra eso esto ese esa yo tú te tu mi mis él ella nada algo bien mal hoy aquí
ahí ver hola adiós gracias vale casa red modelo token tokens mensaje kumo indara clave archivo orden
correo hora día noche mundo cosa vez dos tres cuatro cinco primero último nuevo viejo
the of and to in is you that it he was for on are as with his they at be this have from or one
had by but not what all were we when your can said there an each which she do how their if will
up other about out many then them these so some her would make like him into time has look two
more go see no way could people my than first been who its now find long down day did get come
made may yes hello thanks key file mail model network message
""".split())
PIECE = 4
TOKEN_RE = re.compile(r"[^\W\d_]+|\d+|[^\w\s]|_")


def tokenize(text: str) -> list:
    """[(piece, split)] of a text: frequent words whole, the rest in pieces of up to four letters,
    each sign alone and numbers three digits at a time; a space goes with the word after it."""
    pieces = []
    for match in TOKEN_RE.finditer(text):
        word = match.group(0)
        space = " " if match.start() > 0 and text[match.start() - 1].isspace() else ""
        if word.isdigit():
            parts = [word[i:i + 3] for i in range(0, len(word), 3)]
        elif word.isalpha() and word.lower() not in VOCAB:
            parts = [word[i:i + PIECE] for i in range(0, len(word), PIECE)]
        else:
            parts = [word]
        split = len(parts) > 1 and word.isalpha()
        pieces += [((space if index == 0 else "") + part, split) for index, part in enumerate(parts)]
    return pieces


def count(text: str) -> int:
    return len(tokenize(text))


# --- KU-01: each player's numbers ----------------------------------------------------

MESSAGES = [
    "takeshi: ¿Has leído ya el correo del Laboratorio?", "kumo: Sí. Habla de una convocatoria nueva, la KU-01.",
    "takeshi: Necesito que me resumas la reunión de ayer.", "kumo: Hablasteis del servidor del aula y de las copias.",
    "takeshi: ¿Quién propuso cambiar el cable de la escuela?", "kumo: Lo propuso Nora, pero nadie votó todavía.",
    "takeshi: Apúntalo para el viernes, a las cinco.", "kumo: Apuntado: viernes, 17:00, cable de la escuela.",
    "takeshi: ¿Cuántos ordenadores siguen encendidos?", "kumo: Doce en el aula y tres en el pabellón B.",
    "takeshi: Apaga los del pabellón cuando acabe la clase.", "kumo: De acuerdo. Los apagaré a las 20:30.",
    "takeshi: Recuérdame qué dijo Hideo sobre los fotones.", "kumo: Que medir un qubit lo cambia, y que eso protege la clave.",
    "takeshi: ¿Y qué pasó con el contraseñas.txt de Haruto?", "kumo: Lo borró él mismo; queda una copia en la papelera.",
    "takeshi: Vacía la papelera, por favor.", "kumo: Prefiero que lo confirmes tú: es irreversible.",
    "takeshi: Confirmado. Bórrala.", "kumo: Hecho. La papelera está vacía.",
    "takeshi: ¿Te acuerdas de lo primero que te pregunté hoy?", "kumo: No del todo: hay mensajes que ya no me caben.",
]


def _rng(player, what):
    return random.Random(hashlib.sha256(f"ku-01:{what}:{player}".encode()).hexdigest())


def target_tokens(player) -> int:
    """KU-01's experiment: a sentence of exactly this many tokens."""
    return _rng(player, "tokens").randint(9, 14)


def conversation(player) -> list:
    """Twelve consecutive lines of Takeshi's talk with Kumo, numbered from 01."""
    start = _rng(player, "talk").randrange(0, len(MESSAGES) - 12 + 1, 2)
    return [f"{index + 1:02d} {line}" for index, line in enumerate(MESSAGES[start:start + 12])]


def window(player) -> tuple:
    """(Kumo's window in tokens, the number of the oldest message that still fits whole)."""
    lines = conversation(player)
    counts = [count(line) for line in lines]
    rng = _rng(player, "window")
    fits = rng.randint(3, 7)
    size = sum(counts[-fits:]) + rng.randrange(0, counts[-fits - 1])
    return size, len(lines) - fits + 1


def statements(c, player, call_id) -> list:
    """The experiment and the demonstration as this player sees them."""
    if call_id == "KU-01":
        size, _oldest = window(player)
        return [i18n.t(f"Escribe una frase que el tokenizador parta en exactamente {target_tokens(player)} tokens, "
                       "con al menos una palabra partida en trozos (tokens <frase>)."),
                i18n.t(f"La ventana de Kumo es de {size} tokens. En {CONVERSATION}, ¿cuál es el mensaje más antiguo "
                       "que todavía le cabe entero? laboratorio entregar KU-01 <número>")]
    return [i18n.t("Escribe al menos una regla que permita y otra que prohíba, y pruébalas: kumo regla, kumo probar."),
            i18n.t("Cuando tus reglas pasen todas las pruebas del Laboratorio: laboratorio entregar KU-02")]


def files(c, player: str, relay, story3) -> dict:
    if relay is not None or run_for(c, player) is None:
        return {}
    return {f"{story3.home}/correo/laboratorio.eml": i18n.t(MAIL), CONVERSATION: "\n".join(conversation(player))}


# --- tokens -------------------------------------------------------------------------------

def _shown(pieces) -> str:
    return "".join(f"[{piece}]" for piece, _split in pieces)


def _tokens(c, player, story3, relay, result, args, minute) -> str:
    from . import layer_three, research
    if not args:
        return i18n.t(HELP_TOKENS)
    if args[0] == "-l":
        if len(args) < 2:
            return i18n.t("Uso: tokens -l <archivo>")
        files = layer_three.visible_files(c, player, relay, story3)
        home = layer_three.home_of(relay, story3)
        path = layer_three._norm(result["cwd"], args[1], home)
        if path not in files:
            return i18n.t(f"tokens: {path}: no existe")
        lines, total = [], 0
        for number, line in enumerate(files[path].split("\n"), start=1):
            size = count(line)
            total += size
            lines.append(f"{number:>3} │ {size:>3} │ {line[:60]}")
        return "\n".join(lines + [i18n.t(f"total: {total} tokens")])
    text = " ".join(args)
    pieces = tokenize(text)
    lines = [_shown(pieces), i18n.t(f"{len(pieces)} tokens")]
    if research.progress(c, player, "KU-01")["experiment"]:
        return "\n".join(lines)
    goal = target_tokens(player)
    if len(pieces) == goal and any(split for _piece, split in pieces):
        research.mark(c, player, "KU-01", "experiment", 1)
        lines += ["", i18n.t(f"Parte 2 de KU-01 (experimentar) conseguida: {goal} tokens justos, con una palabra "
                             "partida. Takeshi lo apunta.")] + research.complete(c, player, "KU-01", minute, result)
    return "\n".join(lines)


def submit(c, player, args, minute, result, call_id) -> str:
    from . import kumo, research
    if research.progress(c, player, call_id)["demo"]:
        return i18n.t(f"Ya entregaste {call_id}. Takeshi lo tiene apuntado.")
    if call_id == "KU-01":
        if not args or not args[0].isdigit():
            return i18n.t("Uso: laboratorio entregar KU-01 <número del mensaje>")
        size, oldest = window(player)
        if int(args[0]) != oldest:
            return i18n.t(f"No es ese. Cuenta desde el mensaje más nuevo hacia atrás, y para en cuanto el siguiente "
                          f"ya no quepa entero en {size} tokens (tokens -l {CONVERSATION}).")
        research.mark(c, player, "KU-01", "demo", 1)
        lines = [i18n.t(f"Correcto: Kumo ve desde el mensaje {oldest:02d}. Todo lo anterior, para él, no existe."),
                 i18n.t("Parte 3 de KU-01 (demostrar) conseguida.")]
    else:
        failures, total = kumo.check_rules(c, player)
        if failures:
            return "\n".join([i18n.t(f"Tus reglas fallan {len(failures)} de {total} pruebas del Laboratorio. "
                                     "Míralas con kumo probar.")])
        research.mark(c, player, "KU-02", "demo", 1)
        lines = [i18n.t(f"Tus reglas pasan las {total} pruebas del Laboratorio. Takeshi las firma."),
                 i18n.t("Parte 3 de KU-02 (demostrar) conseguida.")]
    state = research.progress(c, player, call_id)
    missing = [i18n.t("estudiar (laboratorio leer)")] if not research.studied(research.calls(c)[call_id], state) else []
    missing += [i18n.t("experimentar")] if not state["experiment"] else []
    if missing:
        lines.append(i18n.t("Para terminar la convocatoria te falta:") + " " + ", ".join(missing))
    return "\n".join(lines + research.complete(c, player, call_id, minute, result))


def dispatch(c, player, story3, relay, result, name, args, minute):
    return _tokens(c, player, story3, relay, result, args, minute)


HELP = """Laboratorio de Inteligencias · KU-01 y KU-02:
  tokens <texto> | tokens -l <archivo>   el tokenizador del Laboratorio"""
HELP_TOKENS = "Uso: tokens <texto>   o   tokens -l <archivo> (los tokens de cada línea)"

MAN = {
    "tokens": """tokens · el tokenizador del Laboratorio de Inteligencias

  tokens <texto>         trocea el texto como lo haría un modelo y cuenta
                         los tokens
  tokens -l <archivo>    los tokens de cada línea de un archivo, y el total
Las palabras frecuentes son 1 token; las demás, trozos de hasta 4 letras.
Cada signo es 1 token; los números van de 3 en 3 cifras. Los espacios no
cuentan (laboratorio leer tokens).""",
}
MAN_ALIASES = {"token": "tokens", "tokenizer": "tokens", "tokenizador": "tokens"}
