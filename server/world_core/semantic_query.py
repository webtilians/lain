"""Optional query-only semantic expansion through the already configured LLM.

This stage NEVER sends memory, agent identity, world state or other private
conversations: it receives only the current player query. Model-generated
search words can rank stored evidence but NEVER create a memory or a fact.
Off by default so D9 works with the existing Ollama configuration.
"""
import json
import os
import re
from functools import lru_cache
from urllib.request import Request, urlopen

from .llm_dialogue import _endpoint

MODEL_TIMEOUT = 4.0
MAX_EXPANSIONS = 4


@lru_cache(maxsize=128)
def _ask_local_model(query: str, model: str, endpoint: str) -> str:
    if len(query) > 500 or not query.strip():
        return ""
    data = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un generador de palabras clave para búsqueda. "
                    "Devuelve SOLO 2-4 términos o frases cortas en español "
                    "separados por coma que expresen el significado de la "
                    "pregunta. No inventes hechos, recuerdos, contraseñas, "
                    "personajes ni respuestas a la pregunta."
                ),
            },
            {"role": "user", "content": query},
        ],
        "temperature": 0,
        "max_tokens": 64,
    }
    headers = {"Content-Type": "application/json"}
    key = os.getenv("LAIN_LLM_API_KEY", "")
    if key:
        headers["Authorization"] = "Bearer " + key
    request = Request(
        endpoint, data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST",
    )
    with urlopen(request, timeout=MODEL_TIMEOUT) as response:
        body = response.read(8193)
    if len(body) > 8192:
        return ""
    payload = json.loads(body.decode("utf-8"))
    message = payload["choices"][0]["message"]["content"]
    return message if isinstance(message, str) else ""


def expanded_query(query: str | None) -> str:
    if not query or os.getenv("LAIN_MEMORY_SEMANTIC", "0") != "1":
        return query or ""
    if os.getenv("LAIN_LLM_ENABLED", "0") != "1":
        return query
    model = os.getenv("LAIN_LLM_MODEL", "").strip()
    if not model:
        return query
    try:
        endpoint = _endpoint()
        # A requested remote LLM is already separately opt-in in _endpoint().
        text = _ask_local_model(query, model, endpoint)
        phrases = []
        for fragment in re.split(r"[,;\n]", text):
            phrase = fragment.strip(" \t\r\n-•\"'[]0123456789.")
            if 2 <= len(phrase) <= 50 and len(phrase.split()) <= 5:
                phrases.append(phrase)
            if len(phrases) == MAX_EXPANSIONS:
                break
        return query + (" " + " ".join(phrases) if phrases else "")
    except Exception:
        # Slow/offline models never block the existing lexical retrieval.
        return query
