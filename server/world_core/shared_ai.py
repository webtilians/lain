"""Anonymous access to the owner's AI relay; never needs a provider API key.

Only an already projected NPC prompt is accepted here. This module has no
World Core/database access. Sessions are scoped to one HTTPS relay origin.
"""
import json
import os
from pathlib import Path
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Neither private context nor the anonymous bearer may follow a redirect.
        return None


_open = build_opener(_NoRedirect()).open
_lock = threading.Lock()
_sessions: dict[str, dict] = {}
_cooldowns: dict[str, float] = {}


def enabled() -> bool:
    return bool(os.getenv("LAIN_AI_GATEWAY_URL", "").strip())


def project_context(context: dict) -> dict:
    """Bound the paid/free relay prompt without dropping record attribution.

    The caller already selected THIS character's knowledge. Exact temporal
    questions are resolved by World Core before reaching this projection.
    """
    result = dict(context)
    result["beliefs"] = {name: values[-8:] for name, values in context["beliefs"].items()}
    result["memory_records"] = context.get("memory_records", [])[-4:]
    # Structured records carry the same recollections plus provenance. Avoid
    # duplicating their unstructured text, which wastes the shared token budget.
    result["memory"] = [] if result["memory_records"] else context.get("memory", [])[-4:]
    result["player_claims"] = context.get("player_claims", [])[:4]
    result["general_claims"] = context.get("general_claims", [])[:4]
    if isinstance(context.get("experiences"), dict):
        result["experiences"] = {**context["experiences"], "records": context["experiences"].get("records", [])[:4]}
    if context.get("conversation"):
        result["conversation"] = {**context["conversation"], "turns": context["conversation"]["turns"][-6:]}
    return result


def gateway_url() -> str:
    url = os.getenv("LAIN_AI_GATEWAY_URL", "").strip().rstrip("/")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or parsed.path
            or parsed.port not in (None, 443)):
        raise ValueError("INVALID_AI_GATEWAY_URL")
    return url


def _session_file():
    path = os.getenv("LAIN_AI_SESSION_FILE", "").strip()
    return Path(path) if path else None


def _valid_session(value, origin: str) -> bool:
    return (isinstance(value, dict) and value.get("origin") == origin
            and isinstance(value.get("token"), str) and 20 <= len(value["token"]) <= 2048
            and isinstance(value.get("expires_at"), (int, float))
            and value["expires_at"] > time.time() + 30)


def _post(url: str, body: dict, timeout: float, token: str = "") -> bytes:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      headers=headers, method="POST")
    with _open(request, timeout=timeout) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("AI_RESPONSE_TOO_LARGE")
    return raw


def _session(origin: str, timeout: float) -> str:
    # Serialize issuance, not completions. Concurrent NPC calls share one token.
    with _lock:
        value = _sessions.get(origin)
        path = _session_file()
        if not _valid_session(value, origin) and path:
            try:
                if path.stat().st_size <= 4096:
                    value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        if not _valid_session(value, origin):
            value = json.loads(_post(origin + "/v1/session", {}, timeout))
            value["origin"] = origin
            if not _valid_session(value, origin):
                raise ValueError("INVALID_AI_SESSION")
            if path:
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_suffix(".tmp")
                    temporary.write_text(json.dumps(value), encoding="utf-8")
                    temporary.replace(path)
                except OSError:
                    pass  # A read-only profile may still play this session.
        _sessions[origin] = value
        return value["token"]


def completion(body: dict, purpose: str, timeout: float) -> bytes:
    origin = gateway_url()
    if time.monotonic() < _cooldowns.get(origin, 0):
        raise HTTPError(origin, 429, "AI_TEMPORARILY_UNAVAILABLE", {}, None)
    started = time.monotonic()
    try:
        token = _session(origin, min(5, timeout))
        remaining = max(0.1, timeout - (time.monotonic() - started))
        return _post(origin + "/v1/chat/completions",
                     {"messages": body["messages"], "purpose": purpose}, remaining, token)
    except HTTPError as error:
        if error.code == 401:
            # Renew on the NEXT player action, never a hidden retry loop.
            with _lock:
                _sessions.pop(origin, None)
                path = _session_file()
                if path:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
        if error.code in (429, 502, 503, 504):
            try:
                delay = float(error.headers.get("Retry-After", "30"))
            except (AttributeError, ValueError):
                delay = 30
            _cooldowns[origin] = time.monotonic() + max(1, min(86400, delay))
        raise
