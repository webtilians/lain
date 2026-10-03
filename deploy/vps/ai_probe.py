"""Find a chat model that works with the key typed into lain-set-ai-key.

    LAIN_TEST_KEY=... python ai_probe.py groq|gemini

Prints a single line, never the key:
    OK <model> <provider options as compact JSON, or ->
    ERROR KEY|LIMIT|NETWORK|NOMODEL
Each candidate gets the same request budget as the game's dialogue (170
tokens), so a model that spends it thinking and answers nothing is skipped.
"""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROVIDERS = {
    "groq": {
        "base": "https://api.groq.com/openai/v1",
        "models": ["qwen/qwen3.8-27b"],
        "options": [{"reasoning_effort": "none", "reasoning_format": "hidden"}, {}],
        "discover": False,
    },
    "gemini": {
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        # Lite first: the free tier allows it the most requests per day.
        "models": ["gemini-flash-lite-latest", "gemini-2.5-flash-lite",
                   "gemini-flash-latest", "gemini-2.5-flash"],
        "options": [{"reasoning_effort": "none"}, {}],
        "discover": True,
    },
}
SKIP_WORDS = ("image", "tts", "audio", "live", "embedding", "vision", "preview-tts", "robotics")
MAX_TRIES = 6


def endpoint(provider: str) -> str:
    return PROVIDERS[provider]["base"] + "/chat/completions"


def _request(url: str, key: str, body: dict | None, opener):
    headers = {"Authorization": "Bearer " + key, "User-Agent": "LAIN-WorldCore/0.1"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    with opener(Request(url, data=data, headers=headers), timeout=30) as response:
        return json.loads(response.read(1_000_000))


def candidates(provider: str, listed: list[str]) -> list[str]:
    preferred = PROVIDERS[provider]["models"]
    if not PROVIDERS[provider]["discover"]:
        return preferred
    names = [name.removeprefix("models/") for name in listed]
    ordered = [name for name in preferred if name in names]
    # Newer flash models the list above does not know yet, newest first.
    extra = sorted(
        (name for name in names
         if "flash" in name and name not in ordered and not any(word in name for word in SKIP_WORDS)),
        reverse=True,
    )
    return (ordered + extra)[:MAX_TRIES] or preferred[:2]


def probe(provider: str, key: str, opener=urlopen) -> str:
    settings = PROVIDERS[provider]
    listed: list[str] = []
    if settings["discover"]:
        try:
            listed = [item["id"] for item in _request(settings["base"] + "/models", key, None, opener)["data"]]
        except HTTPError as error:
            if error.code in (401, 403):
                return "ERROR KEY"
        except (URLError, OSError, ValueError, KeyError, TypeError):
            pass
    limited = False
    for model in candidates(provider, listed):
        for options in settings["options"]:
            body = {
                "model": model,
                "max_tokens": 170,
                "temperature": 0.65,
                "messages": [
                    {"role": "system", "content": "Eres un personaje de un videojuego. Responde en una sola frase corta."},
                    {"role": "user", "content": "Hola, ¿quién eres?"},
                ],
                **options,
            }
            try:
                reply = _request(endpoint(provider), key, body, opener)
                content = reply["choices"][0]["message"]["content"]
            except HTTPError as error:
                if error.code in (401, 403):
                    return "ERROR KEY"
                limited = limited or error.code == 429
                continue
            except (URLError, OSError):
                return "ERROR NETWORK"
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if isinstance(content, str) and content.strip():
                extra = json.dumps(options, separators=(",", ":")) if options else "-"
                return f"OK {model} {extra}"
    return "ERROR LIMIT" if limited else "ERROR NOMODEL"


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name not in PROVIDERS or not os.environ.get("LAIN_TEST_KEY"):
        print("ERROR NOMODEL")
        sys.exit(2)
    print(probe(name, os.environ["LAIN_TEST_KEY"]))
