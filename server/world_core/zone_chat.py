"""One chat for everyone in a zone, people and residents alike.

The Malla's broadcast domain: whatever is said somewhere is heard by everyone
there, and no line says whether a person or a resident wrote it. Residents go
by their first name, like players, and every speaker reaches the client under
the same kind of opaque key (online.speaker_key), never an actor id.

Only residents within earshot take part: the ones on the player's screen, as the
client reports them (nearest first). They answer when someone names them; a
player alone who was just talking with one keeps talking with them without
naming them again. When a player is alone and says something to the room (a
question, a greeting), the nearest resident may answer. With the characters' AI
on, now and then a resident near someone also says something of their own.
Answers take the time a person would take to type, and the resident remembers
what was said to them, as in a conversation. A client too old to report who is
near gets the whole zone, as before.
"""
import queue
import random
import threading
import time
import unicodedata

from .database import get_connection

TYPING_PER_SECOND = 9.0     # characters a person types in a second, more or less
MIN_DELAY, MAX_DELAY = 1.8, 7.0
COOLDOWN = 20.0             # seconds between two lines of the same resident on their own
REPLY_GAP = 4.0             # seconds between two answers of the same resident
CONVERSATION = 120.0        # a player who talked with a resident this recently is still talking with them
AMBIENT_EVERY = 240.0       # a zone with players hears a resident on their own about this often
ROOM_CHANCE = 0.7           # alone, a question to the room gets an answer this often
MAX_ANSWERS = 2             # residents answering one line
CHECK = 15.0                # the worker looks for ambient lines this often
SYNC = False                # tests: answer at once, in the caller's thread, without waiting
ROOM_WORDS = {"hola", "buenas", "alguien", "hey", "ey", "hello", "hi", "anyone", "anybody", "oye", "perdona"}
# Without the AI, a resident who is named answers like someone busy, never with the
# conversation's fallback line, which would give them away the second time it is read.
SHORT_ANSWERS = [
    "¿Mm? Perdona, estaba en otra cosa.",
    "Ni idea, la verdad.",
    "Ahora no puedo, lo siento.",
    "¿Me lo dices a mí?",
    "Puede ser. No sabría decirte.",
    "Eso tendrías que preguntárselo a otro.",
]


def ai_on() -> bool:
    import os
    return os.getenv("LAIN_LLM_ENABLED") == "1"

_jobs: queue.Queue = queue.Queue()
_worker = None
_worker_lock = threading.Lock()
_last_line: dict = {}       # resident id -> when they last spoke (monotonic)
_next_ambient: dict = {}    # location -> when a resident there may next speak on their own
_partner: dict = {}         # player id -> (resident id, when they last answered)


def first_name(name: str) -> str:
    return str(name or "").split()[0] if str(name or "").strip() else str(name or "")


def plain(text: str) -> str:
    """Lowercase without accents, to find names however they are written."""
    return "".join(ch for ch in unicodedata.normalize("NFD", str(text).casefold()) if unicodedata.category(ch) != "Mn")


def _words(text: str) -> set:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in plain(text))
    return set(cleaned.split())


def residents_at(location: str) -> list:
    """(id, full name) of the residents in a place."""
    with get_connection() as c:
        return c.execute("SELECT id, name FROM agents WHERE location=? AND controller_type='RESIDENT' ORDER BY id",
                         (location,)).fetchall()


def addressed(text: str, residents: list) -> list:
    words = _words(text)
    return [resident for resident in residents if plain(first_name(resident[1])) in words]


def to_the_room(text: str) -> bool:
    return "?" in text or bool(_words(text) & ROOM_WORDS)


def around(player_id: str, location: str) -> list:
    """The residents within earshot of a player, nearest first (the whole zone for an old client)."""
    from . import online
    residents = residents_at(location)
    near = online.near_residents(player_id)
    if near is None:
        return residents
    names = dict(residents)
    return [(actor, names[actor]) for actor in dict.fromkeys(near) if actor in names]


def on_player_chat(player_id: str, player_name: str, text: str, location: str, others_present: bool) -> list:
    """Who answers a line said aloud; returns the residents that will (for tests and the log)."""
    from . import i18n, online
    residents = around(player_id, location)
    if not residents:
        return []
    now = time.monotonic()
    targets = addressed(text, residents)
    partner, since = _partner.get(player_id, (None, -CONVERSATION))
    if not targets and not others_present and ai_on() and now - since < CONVERSATION and partner in dict(residents):
        # Still talking with them: no need to say their name every time (with people around, it is said).
        targets = [(partner, dict(residents)[partner])]
    # A line to the room is answered only by a resident who can really talk (the AI on): the nearest.
    if not targets and not others_present and ai_on() and to_the_room(text) and random.random() < ROOM_CHANCE:
        targets = [residents[0] if online.near_residents(player_id) is not None else random.choice(residents)]
    chosen = []
    for resident in targets[:MAX_ANSWERS]:
        if now - _last_line.get(resident[0], -REPLY_GAP) < REPLY_GAP:
            continue
        _last_line[resident[0]] = now
        _partner[player_id] = (resident[0], now)
        chosen.append(resident)
        _submit(("reply", resident, player_id, player_name, text, location, i18n.language(), now))
    return chosen


def say_aloud(resident_id: str, resident_name: str, text: str, location: str) -> None:
    """A resident's line in the zone chat, under their first name."""
    from . import online
    online.post_chat(resident_id, first_name(resident_name), text, location)


# --- what a resident says ------------------------------------------------------

def reply_text(resident_id: str, player_id: str, player_name: str, text: str, location: str) -> str:
    from .agent_context import AgentContextBuilder
    from .llm_dialogue import generate_dialogue_reply
    from . import online
    context = AgentContextBuilder().build(agent_id=resident_id, retrieval_query=text, player_id=player_id)
    context["situation"]["conversation_with"] = {"id": player_id, "name": player_name}
    context["situation"]["speaking"] = ("en voz alta, en el chat de la zona: todos los que están aquí lo leen. "
                                        "Contesta como una persona más, en una o dos frases.")
    # Only the lines of whoever is speaking to them and of the residents: never other players' talk.
    voices = {player_id} | {resident for resident, _name in residents_at(location)}
    context["situation"]["zone_chat"] = online.recent_lines(location, voices)
    reply = generate_dialogue_reply(context=context, choice_id="FREE_TEXT", choice_text=text)
    _remember(resident_id, player_id, player_name, text, location)
    if reply.source != "LLM_DIALOGUE":
        from . import i18n
        return i18n.t(random.choice(SHORT_ANSWERS))
    return unecho(reply.text)


ECHO_OPENINGS = ("me preguntas", "me dices", "me comentas", "preguntas si", "preguntas cómo", "preguntas que",
                 "dices que", "you ask", "you're asking", "you are asking", "you say", "you said")


def unecho(text: str) -> str:
    """Drop a first sentence that only repeats what was asked («Me preguntas si…»): nobody chats like that."""
    stripped = text.strip()
    lowered = plain(stripped)
    if not lowered.startswith(tuple(plain(opening) for opening in ECHO_OPENINGS)):
        return stripped
    for mark in (". ", "? ", "! ", ".\n"):
        cut = stripped.find(mark)
        if cut != -1 and stripped[cut + len(mark):].strip():
            rest = stripped[cut + len(mark):].strip()
            return rest[:1].upper() + rest[1:]
    return stripped


def _remember(resident_id: str, player_id: str, player_name: str, text: str, location: str) -> None:
    from .episodic_memory import save_episodic_memory
    from .database import load_simulation_minute
    with get_connection() as c:
        save_episodic_memory(c, resident_id, f"En voz alta, en {location}, {player_name} me dijo: {text}",
                             source_kind="PLAYER_TESTIMONY", source_actor_id=player_id,
                             minute=load_simulation_minute() or 0, shareable=False)


def ambient_text(resident_id: str, location: str) -> str | None:
    """Something a resident says on their own: only with the AI on (a scripted line would sound like one)."""
    if not ai_on():
        return None
    from .agent_context import AgentContextBuilder
    from .llm_dialogue import generate_dialogue_reply
    from . import online
    context = AgentContextBuilder().build(agent_id=resident_id)
    context["situation"]["speaking"] = ("en voz alta, en el chat de la zona, sin que nadie te haya preguntado: "
                                        "una frase corta y natural sobre lo que haces, ves o te preocupa ahora.")
    context["situation"]["zone_chat"] = online.recent_lines(location, {r for r, _name in residents_at(location)})
    reply = generate_dialogue_reply(context=context, choice_id="FREE_TEXT",
                                    choice_text="(Di algo en voz alta, en una frase corta.)")
    return reply.text if reply.source == "LLM_DIALOGUE" else None


def ambient_tick(now: float | None = None) -> list:
    """Now and then, in a zone with people, a resident says something. Returns (location, resident) said."""
    from . import online
    now = time.monotonic() if now is None else now
    said = []
    for location in online.zones_with_players():
        # The first time a zone has people, its first line comes after a while, not at once.
        if now < _next_ambient.setdefault(location, now + AMBIENT_EVERY * random.uniform(0.3, 0.8)):
            continue
        _next_ambient[location] = now + AMBIENT_EVERY * random.uniform(0.75, 1.25)
        near = online.residents_near_players(location)  # someone must be there to hear it
        residents = [r for r in residents_at(location) if now - _last_line.get(r[0], -COOLDOWN) >= COOLDOWN
                     and (near is None or r[0] in near)]
        if not residents:
            continue
        resident = random.choice(residents)
        text = ambient_text(resident[0], location)
        if text:
            _last_line[resident[0]] = now
            say_aloud(resident[0], resident[1], text, location)
            said.append((location, resident[0]))
    return said


# --- the worker: answers arrive after typing, never in the request ----------------

def _typing_delay(text: str) -> float:
    return min(MAX_DELAY, max(MIN_DELAY, len(text) / TYPING_PER_SECOND + random.uniform(0.4, 1.4)))


def _run(job) -> None:
    from . import i18n
    _kind, resident, player_id, player_name, text, location, language, heard = job
    token = i18n.set_language(language)
    try:
        answer = reply_text(resident[0], player_id, player_name, text, location)
    finally:
        i18n.reset(token)
    if not answer:
        return
    if not SYNC:
        wait = _typing_delay(answer) - (time.monotonic() - heard)
        if wait > 0:
            time.sleep(wait)
    say_aloud(resident[0], resident[1], answer, location)


def _submit(job) -> None:
    if SYNC:
        _run(job)
        return
    _start()
    _jobs.put(job)


def _start() -> None:
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_loop, name="lain-zone-chat", daemon=True)
            _worker.start()


def _loop() -> None:
    while True:
        try:
            job = _jobs.get(timeout=CHECK)
        except queue.Empty:
            try:
                ambient_tick()
            except Exception:  # noqa: BLE001 - an ambient line must never take the chat down
                pass
            continue
        try:
            _run(job)
        except Exception:  # noqa: BLE001 - one failed answer is simply never said
            pass


def start_ambient() -> None:
    """The online server starts the worker so residents can speak even before anyone names them."""
    import os
    if not os.getenv("PYTEST_CURRENT_TEST"):
        _start()
