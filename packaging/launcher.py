"""LAIN Online 0.1: double-click Windows launcher, no Python or Godot installation."""

from __future__ import annotations

import ctypes
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
from urllib.request import urlopen
from urllib.parse import urlsplit


PORT = 8000
LOCAL_API = "http://127.0.0.1:8000"
OLLAMA_API = "http://127.0.0.1:11434/api/tags"
MODEL = "lain-qwen7b"
MB_YESNO = 0x00000004
IDYES = 6
CREATE_NO_WINDOW = 0x08000000


def message(title: str, body: str, style: int = 0) -> int:
    return ctypes.windll.user32.MessageBoxW(None, body, title, style | 0x00040000)


def data_directory(online_config: dict | None = None) -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    result = Path(base) / "LAIN" / "Beta01"
    if online_config:
        identity = hashlib.sha256(
            (online_config["server_url"] + "|" + online_config["player_token"]).encode()
        ).hexdigest()[:20]
        result = Path(base) / "LAIN" / "Online" / identity
    result.mkdir(parents=True, exist_ok=True)
    return result


def acquire_lock(data: Path):
    import msvcrt

    path = data / "running.lock"
    handle = path.open("a+b")
    try:
        # Windows locks also forbid reading the byte held by another instance.
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def release_lock(handle) -> None:
    if handle is None:
        return
    import msvcrt

    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()


def is_port_busy() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.8):
            return True
    except OSError:
        return False


def local_model_available() -> bool:
    try:
        with urlopen(OLLAMA_API, timeout=0.9) as response:
            models = json.load(response).get("models", [])
        return any(
            isinstance(item, dict) and str(item.get("name", "")).split(":")[0] == MODEL
            for item in models
        )
    except (OSError, ValueError, TypeError):
        return False


def shared_ai_url(root: Path) -> str:
    path = root / "lain-ai.json"
    if not path.exists():
        return ""
    try:
        if path.stat().st_size > 2048:
            raise ValueError()
        config = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(config, dict) or set(config) != {"gateway_url"}:
            raise ValueError()
        if not isinstance(config["gateway_url"], str):
            raise ValueError()
        url = config["gateway_url"].strip().rstrip("/")
        if not url:
            return ""
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
        ):
            raise ValueError()
        return url
    except (OSError, ValueError, TypeError):
        raise ValueError(
            "Revisa lain-ai.json: solo debe contener gateway_url con la dirección HTTPS del servicio, sin claves."
        ) from None


def validate_world_url(value: str) -> str:
    url = value.strip().rstrip("/")
    parsed = urlsplit(url)
    local = parsed.hostname == "localhost"
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
        local = address.is_loopback or any(
            address in network
            for network in (
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
                ipaddress.ip_network("fc00::/7"),
            )
        )
    except ValueError:
        pass
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.port == 0
        or not (parsed.scheme == "https" or parsed.scheme == "http" and local)
    ):
        raise ValueError(
            "El servidor requiere HTTPS o una dirección HTTP de tu red local."
        )
    return url


def online_configuration(root: Path) -> dict | None:
    path = root / "lain-online.json"
    if not path.exists():
        return None
    try:
        if path.stat().st_size > 2048:
            raise ValueError()
        config = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(config, dict) or set(config) != {
            "server_url",
            "player_token",
        }:
            raise ValueError()
        if not all(isinstance(value, str) for value in config.values()):
            raise ValueError()
        if not any(config.values()):
            return None
        config["server_url"] = validate_world_url(config["server_url"])
        token = config["player_token"]
        if not 40 <= len(token) <= 128 or not all(
            ch.isascii() and (ch.isalnum() or ch in "-_") for ch in token
        ):
            raise ValueError()
        return config
    except (OSError, ValueError, TypeError):
        raise ValueError(
            "Revisa tu archivo personal lain-online.json. Necesita una dirección válida y tu acceso al mundo online."
        ) from None


def online_environment(config: dict) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("LAIN_LLM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
        env.pop(key, None)
    env.update(
        {
            "LAIN_SERVER_URL": config["server_url"],
            "LAIN_PLAYER_TOKEN": config["player_token"],
            "LAIN_ALLOW_LAN_HTTP": (
                "1" if config["server_url"].startswith("http://") else "0"
            ),
        }
    )
    return env


def server_environment(data: Path, use_ai: bool, gateway: str = "") -> dict[str, str]:
    env = os.environ.copy()
    # Mandatory isolation: never inherit the developer's world.db or API key.
    env.update(
        {
            "LAIN_ONLINE": "0",
            "LAIN_SERVER_URL": "",
            "LAIN_PLAYER_TOKEN": "",
            "LAIN_WORLD_DB": str((data / "save.db").resolve()),
            "LAIN_LLM_ENABLED": "1" if use_ai or gateway else "0",
            "LAIN_LLM_MODEL": MODEL,
            "LAIN_LLM_ENDPOINT": "http://127.0.0.1:11434/v1/chat/completions",
            "LAIN_LLM_ALLOW_REMOTE": "0",
            "LAIN_LLM_API_KEY": "",
            "LAIN_LLM_TRACE": "0",
            "LAIN_REALITY_TRACE": "0",
            "LAIN_AI_GATEWAY_URL": gateway,
            "LAIN_AI_SESSION_FILE": (
                str((data / "ai-session.json").resolve()) if gateway else ""
            ),
            "LAIN_LLM_TIMEOUT": "25" if gateway else "60",
            "LAIN_REALITY_TIMEOUT": "25",
            "LAIN_MEMORY_SEMANTIC": "0",
            "LAIN_REALITY_GENERATION": "1",
            "LAIN_WORLD_CLOCK": "1",
            "LAIN_WORLD_TICK_SECONDS": "8",
            "LAIN_PROLOGUE_ENABLED": "1",
            "LAIN_CITY_RESIDENTS_ENABLED": "1",
            "LAIN_CHAPTER_ONE": "1",
            "LAIN_CORPORATION": "1",
            "LAIN_WORKSHOP": "1",
            "LAIN_NOEMA": "1",
            "LAIN_CIRCLES": "1",
            "LAIN_CAFE_EVENTS": "1",
            "LAIN_ARCADE_CATALOG": "1",
            "LAIN_CODE_EXCHANGE": "1",
            "LAIN_LAYER_THREE": "1",
        }
    )
    env.pop("LAIN_ARCADE_CATALOG_PATH", None)
    return env


def wait_until_ready(server: subprocess.Popen, seconds: float = 80.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("El servidor se ha cerrado durante el arranque.")
        try:
            # Checking the player state also verifies database initialization,
            # not just that a socket started listening.
            with urlopen(LOCAL_API + "/api/v1/player/state", timeout=2.0) as response:
                state = json.load(response)
            if isinstance(state.get("player"), dict) and state["player"].get(
                "location"
            ):
                return
        except (OSError, ValueError, KeyError, TypeError):
            pass
        time.sleep(0.35)
    raise TimeoutError("El servidor no ha terminado de iniciar en 80 segundos.")


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("Esta distribución solo funciona en Windows.")
    root = Path(sys.executable).resolve().parent
    server_exe = root / "Server" / "LainServer.exe"
    game_exe = root / "Game" / "LAIN-Game.exe"
    try:
        online_config = online_configuration(root)
    except ValueError as error:
        message("LAIN Online", str(error))
        return 1
    if not game_exe.is_file() or (not online_config and not server_exe.is_file()):
        message(
            "LAIN Online 0.1",
            "Faltan archivos de la distribución. Descomprime TODO el ZIP antes de abrir LAIN.exe.",
        )
        return 1

    data = data_directory(online_config)
    lock = acquire_lock(data)
    if lock is None:
        message(
            "LAIN Online 0.1", "Ya hay una instancia de LAIN abierta para este usuario."
        )
        return 1
    server = None
    log = None
    try:
        if online_config:
            game = subprocess.Popen(
                [str(game_exe)],
                cwd=str(game_exe.parent),
                env=online_environment(online_config),
            )
            return game.wait()
        if is_port_busy():
            raise RuntimeError(
                "El puerto 8000 está ocupado. Cierra el servidor anterior de LAIN "
                "antes de abrir esta versión. No se conectará a una partida ajena."
            )
        gateway = shared_ai_url(root)
        use_ai = (
            not gateway
            and local_model_available()
            and message(
                "LAIN · IA local opcional",
                "Se ha detectado lain-qwen7b en Ollama local.\n\n"
                "¿Quieres activar las conversaciones con IA?\n"
                "No se necesita IA para jugar.",
                MB_YESNO,
            )
            == IDYES
        )
        env = server_environment(data, use_ai, gateway)
        log = (data / "server.log").open("ab", buffering=0)
        server = subprocess.Popen(
            [str(server_exe)],
            cwd=str(data),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
        )
        wait_until_ready(server)
        game = subprocess.Popen([str(game_exe)], cwd=str(game_exe.parent), env=env)
        result = game.wait()
        if result != 0:
            raise RuntimeError(
                "El cliente de Godot se ha cerrado con código %s." % result
            )
        return 0
    except Exception as error:
        with (data / "launcher.log").open("a", encoding="utf-8") as handle:
            handle.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
            handle.write(traceback.format_exc() + "\n")
        message(
            "LAIN Online 0.1 · Error",
            "%s\n\nDiagnóstico: %s\nNo se ha borrado tu partida."
            % (error, data / "launcher.log"),
        )
        return 1
    finally:
        if server is not None and server.poll() is None:
            # Only terminate the child process we started, never a foreign server.
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        if log is not None:
            log.close()
        release_lock(lock)


if __name__ == "__main__":
    sys.exit(main())
