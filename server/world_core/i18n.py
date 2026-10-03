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
    exact, templates = {}, []
    for source, target in data.items():
        if re.search(r"\{\w+\}", source):
            pattern = re.sub(r"\\\{(\w+)\\\}", lambda m: f"(?P<{m.group(1)}>.+?)", re.escape(source))
            templates.append((re.compile("^" + pattern + "$", re.S), target))
        else:
            exact[source] = target
    return exact, templates


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
                    result = target.format(**match.groupdict())
                    break
    return result.format(**values) if values else result


def page(data: dict) -> dict:
    """Translate an event page (speaker, text and choice labels) in place."""
    for key in ("speaker", "text"):
        if isinstance(data.get(key), str):
            data[key] = t(data[key])
    for choice in data.get("choices") or []:
        if isinstance(choice, dict) and isinstance(choice.get("text"), str):
            choice["text"] = t(choice["text"])
    return data
