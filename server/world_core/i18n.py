"""Player-facing language. Spanish is the source: the code keeps writing Spanish
and passes text through t(), and content/i18n/<lang>.json maps each Spanish
text, or a template with {placeholders}, to its translation.

The language of the current request comes from the client's X-Lain-Language
header (set by a middleware in api.py); anything without a translation stays
in Spanish rather than failing.
"""
import contextvars
from functools import lru_cache
import json
from pathlib import Path
import re

LANGUAGES = ("es", "en")
NAMES = {"es": "español", "en": "English"}
CATALOGS = Path(__file__).resolve().parents[1] / "content" / "i18n"
_current = contextvars.ContextVar("lain_language", default="es")


def normalize(value) -> str:
    code = str(value or "").strip().lower()[:2]
    return code if code in LANGUAGES else "es"


def set_language(value):
    return _current.set(normalize(value))


def reset(token) -> None:
    _current.reset(token)


def language() -> str:
    return _current.get()


@lru_cache(maxsize=None)
def _catalog(lang: str):
    path = CATALOGS / f"{lang}.json"
    if lang == "es" or not path.exists():
        return {}, []
    data = json.loads(path.read_text(encoding="utf-8"))
    exact, templates = dict(data), []
    for source, target in data.items():
        if re.search(r"\{\w+\}", source):
            seen = set()
            def group(match):
                name = match.group(1)
                if name in seen:
                    return f"(?P={name})"
                seen.add(name)
                return f"(?P<{name}>.*?)"
            pattern = re.sub(r"\\\{(\w+)\\\}", group, re.escape(source))
            # No DOTALL: a slot never swallows the following lines of a multi-line text.
            templates.append((re.compile("^" + pattern + "$"), target))
        else:
            exact[source] = target
    # Specific sentences precede broad templates such as '{v0}: {v1}'.
    templates.sort(key=lambda item: len(item[0].pattern), reverse=True)
    return exact, templates


# Game vocabulary that may appear inside a composed sentence ("Montaje compartido
# compilado: Enrutamiento, Exploración"). Player names are never in this set,
# so a captured value is translated only when it is entirely made of these.
GAME_TERMS = frozenset({
    "Enrutamiento", "Exploración", "Protección", "Amortiguación", "Coprocesador M",
    "Interfaz R", "Técnico de Kissa", "Profesor",
    # Layer titles, captured inside hint lines.
    "Capa 01 · Física", "Capa 02 · Enlace", "Capa 03 · TTL", "Capa 04 · Transporte", "Capa 05 · Sesión",
    "Capa 06 · Presentación", "Capa 07 · Aplicación",
})


def _term(value: str, exact: dict) -> str:
    items = [item.strip() for item in value.split(",")]
    if items and all(item in GAME_TERMS and item in exact for item in items):
        return ", ".join(exact[item] for item in items)
    return value


def t(text, lang: str | None = None, **values) -> str:
    """Translate one player-facing Spanish text; unknown text is returned as is."""
    code = normalize(lang) if lang else language()
    source = str(text)
    result = source
    if code != "es":
        exact, templates = _catalog(code)
        if source in exact:
            result = exact[source]
        else:
            for pattern, target in templates:
                match = pattern.match(source)
                if match:
                    values = {key: _term(value, exact) for key, value in match.groupdict().items()}
                    result = target.format(**values)
                    break
    if result == source and code != "es" and "\n" in source:
        result = "\n".join(t(line, code) for line in source.split("\n"))
    return result.format(**values) if values else result


# Only presentation fields. Identifiers, terminal bytes/hashes, player names,
# hypotheses, programs, account data and online chat remain byte-for-byte intact.
DISPLAY_FIELDS = frozenset({
    "text", "line", "title", "description", "summary", "body", "subject",
    "label", "role_label", "focus", "activity", "public_objective", "goal",
    "hint", "condition", "motive", "reason", "notification", "rules",
    "game_name", "speaker", "detail",
})
PRIVATE_FIELDS = frozenset({
    "chat", "chat_messages", "hypothesis", "draft", "program", "source_code",
    "compiled", "life_draft", "output", "memories", "claims", "player",
})


def payload(data, field=""):
    """Copy a public response in the request language; never localize storage."""
    if language() == "es" or field in PRIVATE_FIELDS:
        return data
    if isinstance(data, dict):
        if field == "skills":
            return {t(key): value for key, value in data.items()}
        return {key: payload(value, key) for key, value in data.items()}
    if isinstance(data, list):
        return [payload(value, field) for value in data]
    if isinstance(data, str) and field in DISPLAY_FIELDS:
        return t(data)
    return data


def page(data: dict) -> dict:
    """Translate an event page (speaker, text and choice labels) in place."""
    for key in ("speaker", "text"):
        if isinstance(data.get(key), str):
            data[key] = t(data[key])
    for choice in data.get("choices") or []:
        if isinstance(choice, dict) and isinstance(choice.get("text"), str):
            choice["text"] = t(choice["text"])
    return data
