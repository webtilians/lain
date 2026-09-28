"""Two real Godot clients over TCP; owns only its temporary DB and subprocesses."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot")
    parser.add_argument("--prepare-world", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--serve-world", type=int, help=argparse.SUPPRESS)
    parser.add_argument(
        "--capture",
        type=Path,
        help="Optional rendered screenshot; uses a hidden window on Windows",
    )
    args = parser.parse_args()
    if args.serve_world:
        import uvicorn

        server = uvicorn.Server(
            uvicorn.Config(
                "server.api:app",
                host="127.0.0.1",
                port=args.serve_world,
                access_log=False,
                log_level="warning",
                proxy_headers=False,
            )
        )
        worker = threading.Thread(target=server.run)
        worker.start()
        try:
            sys.stdin.readline()
        finally:
            server.should_exit = True
            worker.join(timeout=15)
        if worker.is_alive():
            raise RuntimeError("Test server did not shut down")
        return
    if args.prepare_world:
        from tools.online_server import configure

        configure(args.prepare_world)
        from server.world_core.simulation import Simulation
        from server.world_core import database, online

        with contextlib.redirect_stdout(None):
            Simulation()
            people = {name: online.create_player(name) for name in ("Alice", "Bob")}
        with database.get_connection() as conn:
            for actor, _token in people.values():
                conn.execute(
                    "UPDATE agents SET location='APARTMENT_DISTRICT' WHERE id=?",
                    (actor,),
                )
        (args.prepare_world / "test-players.json").write_text(
            json.dumps(people), encoding="utf-8"
        )
        return
    if not args.godot:
        parser.error("--godot is required")
    log_dir = ROOT / "outputs" / "online-smoke"
    log_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lain-online-test-") as temporary:
        from tools.online_server import configure

        configure(Path(temporary))
        os.environ.update(
            {
                "LAIN_WORLD_CLOCK": "0",
                "LAIN_LLM_ENABLED": "0",
                "LAIN_REALITY_GENERATION": "0",
                "LAIN_MEMORY_SEMANTIC": "0",
            }
        )
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        processes = []
        # SW_HIDE is also honored by a graphical Godot run used for capture.
        options = {}
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            options = {
                "startupinfo": startup,
                "creationflags": subprocess.CREATE_NO_WINDOW,
            }
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--prepare-world",
                temporary,
            ],
            cwd=ROOT,
            env=environment,
            check=True,
            timeout=40,
            **options,
        )
        people = json.loads(
            (Path(temporary) / "test-players.json").read_text(encoding="utf-8")
        )
        with contextlib.ExitStack() as stack:
            try:
                server_log = stack.enter_context(
                    (log_dir / "server.log").open("w", encoding="utf-8")
                )
                server = subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--serve-world",
                        str(port),
                    ],
                    cwd=ROOT,
                    env=environment,
                    stdin=subprocess.PIPE,
                    text=True,
                    stdout=server_log,
                    stderr=subprocess.STDOUT,
                    **options,
                )
                processes.append(server)
                deadline = time.monotonic() + 40
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError(
                            "Test server failed; see outputs/online-smoke/server.log"
                        )
                    try:
                        with urlopen(url + "/health", timeout=1) as response:
                            if json.load(response)["status"] == "ok":
                                break
                    except OSError:
                        time.sleep(0.15)
                else:
                    raise RuntimeError("Test server did not start")
                clients = []
                for name, (_actor, token) in people.items():
                    client_env = {
                        **environment,
                        "LAIN_SERVER_URL": url,
                        "LAIN_PLAYER_TOKEN": token,
                        "LAIN_ALLOW_LAN_HTTP": "1",
                        "LAIN_TEST_PLAYER_NAME": name,
                    }
                    command = [
                        args.godot,
                        "--path",
                        str(ROOT / "client"),
                        "--script",
                        "res://tools/test_online01.gd",
                    ]
                    if args.capture:
                        args.capture.parent.mkdir(parents=True, exist_ok=True)
                        client_env["LAIN_ONLINE_CAPTURE"] = str(args.capture.resolve())
                        command.extend(["--rendering-method", "gl_compatibility"])
                    else:
                        command.append("--headless")
                    log_path = log_dir / f"{name}.log"
                    output = stack.enter_context(log_path.open("w", encoding="utf-8"))
                    child = subprocess.Popen(
                        command,
                        cwd=ROOT,
                        env=client_env,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        **options,
                    )
                    clients.append((name, child, log_path, output))
                    processes.append(child)
                for name, child, log_path, output in clients:
                    code = child.wait(timeout=95)
                    output.flush()
                    contents = log_path.read_text(encoding="utf-8", errors="replace")
                    if (
                        code != 0
                        or "ONLINE01_CLIENT_OK" not in contents
                        or "SCRIPT ERROR:" in contents
                        or "\nERROR:" in contents
                    ):
                        raise RuntimeError(f"Godot {name} failed; see {log_path}")
                print(
                    "ONLINE01_TCP_OK clients=2 identities=2 private_world=true avatars=true chat=true separate_travel=true"
                )
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        if process is server:
                            try:
                                process.communicate(input="stop\n", timeout=20)
                                continue
                            except subprocess.TimeoutExpired:
                                pass
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


if __name__ == "__main__":
    main()
