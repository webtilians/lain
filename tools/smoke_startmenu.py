"""Start a disposable online World Core with an invite code and run the live start menu test.

    python tools/smoke_startmenu.py --godot <Godot console exe>
"""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True)
    args = parser.parse_args()
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    invite = "prueba-humo-123"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as data:
        env = dict(os.environ, LAIN_SIGNUP_CODE=invite, LAIN_WORLD_CLOCK="0", LAIN_LLM_ENABLED="0")
        env.pop("LAIN_SIGNUP_OPEN", None)
        server = subprocess.Popen(
            [sys.executable, "-m", "tools.online_server", "--data-dir", data, "serve", "--port", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(120):
                try:
                    with urlopen(url + "/health", timeout=1):
                        break
                except OSError:
                    time.sleep(0.5)
            client_env = dict(os.environ, LAIN_SERVER_URL=url, LAIN_ALLOW_LAN_HTTP="1", LAIN_TEST_INVITE=invite)
            for key in ("LAIN_PLAYER_TOKEN", "LAIN_SKIP_MENU"):
                client_env.pop(key, None)
            result = subprocess.run(
                [args.godot, "--headless", "--path", str(ROOT / "client"), "--script", "res://tools/test_startmenu_live.gd"],
                env=client_env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
            )
            output = result.stdout + result.stderr
            for line in output.splitlines():
                if "STARTMENU_LIVE" in line or "ERROR" in line:
                    print(line)
            return 0 if result.returncode == 0 and "STARTMENU_LIVE_OK" in output else 1
        finally:
            server.terminate()
            server.wait(timeout=20)


if __name__ == "__main__":
    sys.exit(main())
