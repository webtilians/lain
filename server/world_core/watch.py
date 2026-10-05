"""The watcher (el vigía): new research calls that follow real technology.

Every few days the World Core reads public headlines about networks, AI,
cryptography and physics (arXiv, Hacker News, the RFC Editor) and asks the
characters' AI to turn one of them into a call for one of the three research
centres. The call is published at once; the owner reviews it later in the
server panel and deletes it if it is wrong. Nothing waits for anyone.

The AI writes only the words (title, summary, article, what the residents will
say). The exercise and its check are always one of the generators in
research.py, chosen by the AI and filled with numbers by the code, so every
call can be solved and verified.
"""
import json
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .database import get_connection

SOURCES = (
    ("arXiv", "https://export.arxiv.org/api/query?search_query=cat:quant-ph+OR+cat:cs.CR+OR+cat:cs.NI+OR+cat:cs.AI"
              "&sortBy=submittedDate&sortOrder=descending&max_results=25"),
    ("Hacker News", "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30"),
    ("RFC Editor", "https://www.rfc-editor.org/rfcrss.xml"),
)
DAYS = 3             # a new call every this many days
RETRY = 6 * 3600     # after a failed attempt, wait this long before trying again
CHECK = 30 * 60      # how often the background thread looks at the clock
HEADLINES = 60
LIMITS = {"title": 80, "summary": 320, "article": 1900, "framing": 260, "tech": 40, "tech_text": 170,
          "tech_line": 170}
_thread = None
_stop = threading.Event()


def days() -> float:
    try:
        return max(0.01, float(os.getenv("LAIN_WATCH_DAYS", DAYS)))
    except ValueError:
        return DAYS


def ai_ready() -> bool:
    return os.getenv("LAIN_LLM_ENABLED") == "1" and bool(os.getenv("LAIN_LLM_MODEL"))


def initialize_watch() -> None:
    with get_connection() as c:
        c.execute("CREATE TABLE IF NOT EXISTS research_watch (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, "
                  "status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '')")


def log(status: str, detail: str = "") -> None:
    initialize_watch()
    with get_connection() as c:
        c.execute("INSERT INTO research_watch(at, status, detail) VALUES(?,?,?)", (time.time(), status, detail[:300]))


def history(limit: int = 12) -> list:
    initialize_watch()
    with get_connection() as c:
        return [{"at": at, "status": status, "detail": detail} for at, status, detail in c.execute(
            "SELECT at, status, detail FROM research_watch ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


# --- headlines ------------------------------------------------------------------

def _get(url: str, timeout: float = 15.0) -> bytes:
    request = Request(url, headers={"User-Agent": "SesionCero-Vigia/1.0 (+https://github.com/webtilians/lain)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read(2_000_000)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def parse(source: str, raw: bytes) -> list:
    """Headlines as {source, title, url}; anything unreadable is skipped, never fatal."""
    items = []
    if source == "Hacker News":
        for hit in json.loads(raw.decode("utf-8")).get("hits", []):
            title, url = _clean(hit.get("title")), hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            if title:
                items.append({"source": source, "title": title, "url": url})
        return items
    root = ET.fromstring(raw)
    atom = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(atom + "entry"):
        title = _clean(entry.findtext(atom + "title"))
        link = next((node.get("href") for node in entry.findall(atom + "link") if node.get("rel") in (None, "alternate")),
                    entry.findtext(atom + "id"))
        if title:
            items.append({"source": source, "title": title, "url": link})
    for entry in root.iter("item"):
        title = _clean(entry.findtext("title"))
        if title:
            items.append({"source": source, "title": title, "url": _clean(entry.findtext("link"))})
    return items


def headlines(fetch=_get) -> list:
    found = []
    for source, url in SOURCES:
        try:
            found += parse(source, fetch(url))[:25]
        except (OSError, ValueError, ET.ParseError):
            continue
    # Only web links survive: the panel shows them and the owner may open them.
    found = [item for item in found if urlsplit(str(item["url"])).scheme in ("http", "https")]
    return found[:HEADLINES]


# --- the AI ---------------------------------------------------------------------

def target_centre() -> str:
    """The centre with the fewest open calls (in CENTRES order on a tie): every centre gets its turn."""
    from . import research
    counts = research.open_counts()
    return min(research.CENTRES, key=lambda key: (counts.get(key, 0), list(research.CENTRES).index(key)))


def prompt(items: list, existing: list, centre: str, recent_kinds: list | None = None) -> list:
    from . import research
    kinds = {key: generator.ABOUT for key, generator in research.GENERATORS.items()}
    director = research.CENTRES[centre]["who"].removeprefix("Dirige: ").rstrip(".")
    system = (
        "Eres el vigía de la Malla, la red de un videojuego de misterio llamado Sesión Cero. Cada pocos días eliges "
        "UNA noticia real de la lista y la conviertes en una convocatoria de estudio para un centro de "
        f"investigación del juego. Esta vez es para {research.centre_focus(centre)}. Elige la noticia que mejor "
        "encaje con ese centro. Prefiere avances de ciencia, tecnología o estándares; evita sucesos (filtraciones "
        "de datos, muertes, juicios, despidos, polémicas de empresas o de personas concretas). "
        "Escribes para jugadores curiosos, sin dar nada por sabido. No inventes datos técnicos: explica solo lo "
        "que es cierto y general sobre el tema, y si la noticia es muy concreta, explica la idea de fondo. "
        f"El artículo lo firma el director del centro, {director}: escríbelo en primera persona, con su voz, sin "
        "saludos ni fórmulas como «Saludos, operador». En español, los títulos llevan mayúscula solo al principio "
        "y en los nombres propios. "
        "El ejercicio NO lo escribes tú: eliges uno de los tipos de ejercicio (kind) y escribes una frase (framing) "
        "que lo presente. Sé honesto: si la tecnología no usa esa operación, no digas que la usa; di qué idea de "
        "fondo comparte con ella (integridad, errores, claves, conteo…). Si puedes, no repitas los tipos de "
        "recent_kinds. "
        "Responde solo con un objeto JSON, sin texto alrededor, con estas claves: "
        '"headline" (el número de la noticia), "kind" (una de las claves de kinds), "title_es", "title_en" '
        '(máx. 70 caracteres), "summary_es", "summary_en" (dos frases), "article_es", "article_en" (artículo de '
        'estudio de 120 a 220 palabras, con saltos de línea), "framing_es", "framing_en" (una frase), "tech" '
        '(nombre corto de la tecnología, máx. 30 caracteres), "tech_text_es", "tech_text_en" (una frase: qué '
        'aprende la Malla), "tech_line_es", "tech_line_en" (una frase: qué cambia para quien juega), "memory_es" '
        "(lo que el director recordará de ello, en primera persona y en una frase). No repitas temas ya estudiados.")
    user = json.dumps({
        "centre": research.centre_focus(centre), "kinds": kinds, "recent_kinds": recent_kinds or [],
        "already_studied": existing,
        "headlines": [{"n": index, "source": item["source"], "title": item["title"]} for index, item in enumerate(items)],
    }, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def ask(messages: list) -> str:
    """One chat completion through the same provider the characters use."""
    from . import llm_dialogue, shared_ai
    body = {"model": os.getenv("LAIN_LLM_MODEL", ""), "messages": messages, "temperature": 0.7, "max_tokens": 3000}
    timeout = max(20.0, min(90.0, float(os.getenv("LAIN_LLM_TIMEOUT", "15")) * 4))
    if shared_ai.enabled():
        raw = shared_ai.completion(body, "dialogue", timeout)
    else:
        payload = json.dumps(llm_dialogue.with_provider_options(body), ensure_ascii=False).encode("utf-8")
        request = Request(llm_dialogue._endpoint(), data=payload, headers=llm_dialogue.provider_headers(), method="POST")
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(262_144)
    return json.loads(raw.decode("utf-8"))["choices"][0]["message"]["content"]


def _text(value, limit: int) -> str:
    text = str(value or "").replace("\r", "")
    text = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32).strip()
    if not text:
        raise ValueError("EMPTY_FIELD")
    return text[:limit].rstrip()


def proposal(reply: str, items: list, centre: str) -> dict:
    """Validate the AI's answer into a call for `centre`; the source always comes from our own headline list."""
    from . import research
    match = re.search(r"\{.*\}", reply, re.S)
    if match is None:
        raise ValueError("NO_JSON")
    data = json.loads(match.group(0))
    if centre not in research.CENTRES:
        raise ValueError("UNKNOWN_CENTRE")
    if data.get("kind") not in research.GENERATORS:
        raise ValueError("UNKNOWN_KIND")
    index = data.get("headline")
    if not isinstance(index, int) or not 0 <= index < len(items):
        raise ValueError("UNKNOWN_HEADLINE")
    both = {}
    for field, limit in (("title", LIMITS["title"]), ("summary", LIMITS["summary"]), ("article", LIMITS["article"]),
                         ("framing", LIMITS["framing"]), ("tech_text", LIMITS["tech_text"]),
                         ("tech_line", LIMITS["tech_line"])):
        both[field] = {lang: _text(data.get(f"{field}_{lang}"), limit) for lang in ("es", "en")}
    return {
        "centre": centre, "kind": data["kind"], **both,
        "tech": _text(data.get("tech"), LIMITS["tech"]).replace("\n", " "),
        "memory": _text(data.get("memory_es"), 300).replace("\n", " "),
        "source": {"name": items[index]["source"], "title": items[index]["title"][:200], "url": items[index]["url"]},
    }


# --- running it -------------------------------------------------------------------

def due(now: float | None = None) -> bool:
    """A call every few days; after a failure, try again a few hours later."""
    from . import research
    now = time.time() if now is None else now
    last = research.last_generated()
    if last is not None and now - last < days() * 86400:
        return False
    tried = [entry for entry in history(5) if entry["status"] != "PUBLISHED"]
    return not tried or now - tried[0]["at"] >= RETRY or (last is not None and tried[0]["at"] < last)


def run(fetch=_get, chat=ask) -> dict | None:
    """Fetch, ask and publish one call. Returns the call, or None (the reason is in the log)."""
    from . import research
    if not ai_ready():
        log("SKIPPED", "IA desactivada")
        return None
    items = headlines(fetch)
    if not items:
        log("FAILED", "sin titulares (¿sin red?)")
        return None
    try:
        centre = target_centre()
        messages = prompt(items, research.studied_topics(), centre, research.recent_kinds())
        call = research.publish(proposal(chat(messages), items, centre))
    except HTTPError as error:
        log("FAILED", f"IA HTTP {error.code}")
        return None
    except (URLError, OSError, TimeoutError) as error:
        log("FAILED", f"IA sin respuesta ({type(error).__name__})")
        return None
    except (ValueError, KeyError, IndexError, TypeError) as error:
        log("FAILED", f"respuesta no válida ({error})")
        return None
    log("PUBLISHED", f"{call['id']} · {call['title']['es']}")
    return call


_running = threading.Lock()


def run_soon() -> bool:
    """The owner's «look for one now»: a run in the background, unless one is already going."""
    if not _running.acquire(blocking=False):
        return False

    def work():
        try:
            run()
        except Exception as error:  # noqa: BLE001 - a failed run is logged, never raised into the server
            log("FAILED", f"error inesperado ({type(error).__name__})")
        finally:
            _running.release()

    threading.Thread(target=work, name="lain-vigia-ahora", daemon=True).start()
    return True


def next_run() -> float | None:
    """When the watcher will next look for a call (for the panel)."""
    from . import research
    last = research.last_generated()
    return None if last is None else last + days() * 86400


def maybe_run(now: float | None = None):
    if not ai_ready() or not due(now) or not _running.acquire(blocking=False):
        return None
    try:
        return run()
    finally:
        _running.release()


def _loop() -> None:
    delay = 60  # a minute after start, then every CHECK
    while not _stop.wait(delay):
        delay = CHECK
        try:
            maybe_run()
        except Exception as error:  # noqa: BLE001 - the watcher must never stop the world
            log("FAILED", f"error inesperado ({type(error).__name__})")


def start() -> None:
    """The background watcher of the online server (never in tests or offline games)."""
    global _thread
    if os.getenv("LAIN_WATCH", "1") != "1" or os.getenv("PYTEST_CURRENT_TEST") or _thread is not None:
        return
    initialize_watch()
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="lain-vigia", daemon=True)
    _thread.start()


def stop() -> None:
    global _thread
    _stop.set()
    _thread = None
