"""Read-only Ollama/LAIN connectivity check, using a synthetic conversation.

Run from the repository root: python -m tools.diagnose_llm
It never reads world.db or any private memory and never logs prompts or keys.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from server.world_core.llm_dialogue import _endpoint, _failure_reason, _provider_reply


def synthetic_context() -> dict:
    return {
        "identity": {
            "id": "AGENT_DIAGNOSTIC", "name": "Prueba",
            "faction": "NONE", "controller_type": "AI",
        },
        "situation": {"location": "APARTMENT", "conversation_with": None},
        "beliefs": {"nodes": [], "actors": [], "situations": []},
        "memory": [], "memory_records": [], "player_claims": [],
        "general_claims": [], "knowledge_timeline": None,
        "experiences": {"request": None, "records": []},
        "goals": {"current": "OBSERVE_WORLD"},
        "conversation": {
            "id": "SYNTHETIC_DIAGNOSTIC", "status": "OPEN", "turns": [],
        },
    }


def run() -> int:
    print("LAIN_DIAG // LLM_ENABLED =", os.getenv("LAIN_LLM_ENABLED") == "1")
    print("LAIN_DIAG // REALITY_GENERATION =", os.getenv("LAIN_REALITY_GENERATION") == "1")
    print("LAIN_DIAG // MODEL_CONFIGURED =", bool(os.getenv("LAIN_LLM_MODEL", "").strip()))
    try:
        endpoint = _endpoint()
    except ValueError as error:
        print("LAIN_DIAG // INVALID_ENDPOINT_CONFIGURATION")
        return 1
    model = os.getenv("LAIN_LLM_MODEL", "").strip()
    if not model:
        return 1

    # A minimal request distinguishes Ollama/model availability from an
    # error triggered only by LAIN's richer character/context payload.
    simple = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Responde OK."}],
        "stream": False, "max_tokens": 80,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if os.getenv("LAIN_LLM_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["LAIN_LLM_API_KEY"]
    timeout = max(1.0, min(60.0, float(os.getenv("LAIN_LLM_TIMEOUT", "30"))))
    try:
        with urlopen(Request(endpoint, data=simple, headers=headers, method="POST"),
                     timeout=timeout) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("TOO_LARGE")
        message = json.loads(raw.decode("utf-8"))["choices"][0]["message"]
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            print("LAIN_DIAG // SIMPLE_EMPTY_CONTENT")
            return 1
        print("LAIN_DIAG // SIMPLE_OK; CHARS =", len(text.strip()))
    except Exception as error:
        print("LAIN_DIAG // SIMPLE_" + _failure_reason(error))
        return 1

    try:
        reply = _provider_reply(
            synthetic_context(), "¿Qué podría existir al otro lado de la red?",
        )
    except Exception as error:
        print("LAIN_DIAG // LAIN_CONTEXT_" + _failure_reason(error))
        return 1
    print("LAIN_DIAG // LAIN_CONTEXT_OK; CHARS =", len(reply))
    print("LAIN_DIAG // Synthetic model check succeeded; verify the RUNNING "
          "Uvicorn process has the same branch and environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
