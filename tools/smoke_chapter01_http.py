"""Exercise the real HTTP boundary in a disposable server/world/port."""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="lain-chapter-http-") as scratch:
        db = Path(scratch)/"test.db"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, LAIN_WORLD_DB=str(db), LAIN_LLM_ENABLED="0",
                   LAIN_WORLD_CLOCK="0", LAIN_MEMORY_SEMANTIC="0",
                   LAIN_CHAPTER_ONE="1", LAIN_PROLOGUE_ENABLED="0",
                   LAIN_CITY_RESIDENTS_ENABLED="1", LAIN_REALITY_GENERATION="0")
        with (Path(scratch)/"server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.api:app",
                "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
            try:
                def request(path, payload=None):
                    req=Request(f"http://127.0.0.1:{port}"+path,
                        data=json.dumps(payload).encode() if payload is not None else None,
                        headers={"Content-Type":"application/json"})
                    with urlopen(req, timeout=30) as response:
                        return json.load(response)
                for _ in range(100):
                    try:
                        request("/health")
                        break
                    except (URLError, TimeoutError):
                        if process.poll() is not None:
                            raise RuntimeError("Disposable server failed to start")
                        time.sleep(.1)
                state=request("/api/v1/player/state")
                assert not state["chapter_one"]["active"]
                request("/api/v1/player/messages/MSG_BOOTSTRAP_001/ack", {})
                state=request("/api/v1/player/state")
                assert state["chapter_one"]["active"]
                command={"action":"WIRED", "target":"REPLY", "data":{}, "request_id":"http_reply_0001"}
                response=request("/api/v1/chapter-one/action", command)
                assert "UNKNOWN_REPLY" in {e["id"] for e in response["state"]["chapter_one"]["evidence"]}
                with sqlite3.connect(db) as conn:
                    before=list(conn.iterdump())
                conn.close()
                assert request("/api/v1/chapter-one/action", command)["result"]==response["result"]
                request("/api/v1/player/state")
                for changed, status in [
                    ({**command, "target":"SEARCH"}, 409),
                    ({**command, "request_id":"http_invalid_01", "data":{"choice":{}}},422),
                    ({**command, "request_id":"http_remote_001", "action":"TALK", "target":"PROFESSOR"},409),
                ]:
                    try:
                        request("/api/v1/chapter-one/action",changed)
                        raise AssertionError("Invalid request accepted")
                    except HTTPError as error:
                        assert error.code==status, error.code
                with sqlite3.connect(db) as conn:
                    assert list(conn.iterdump())==before
                conn.close()
                print("CHAPTER01_HTTP_OK activation=true retries=idempotent errors=409,422 polling=read_only")
            finally:
                if os.name=="nt":
                    # The Windows venv launcher spawns a child interpreter.
                    # Stop only this disposable process tree, not other servers.
                    subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],
                                   capture_output=True, check=True)
                else:
                    process.terminate()
                process.wait(timeout=20)


if __name__=="__main__":
    main()
