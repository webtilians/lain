"""Verify that a distributable archive has required binaries but no personal data."""

from __future__ import annotations

import sys
import json
from urllib.parse import urlsplit
from pathlib import Path
from zipfile import ZipFile


REQUIRED = {
    "LAIN.exe",
    "Game/LAIN-Game.exe",
    "Game/LAIN-Game.pck",
    "Server/LainServer.exe",
    "Server/_internal/server/content/cafe_catalog.json",
    "Server/_internal/server/world_core/data/residents09.json",
    "LEEME.txt",
}
ALLOWED_PREFIXES = ("Game/", "Server/")
BLOCKED_PARTS = {
    ".git",
    ".godot",
    ".venv",
    "world.db",
    "save.db",
    "ai-session.json",
    "ai-session.tmp",
    ".dev.vars",
    "node_modules",
    ".wrangler",
    "exchange01.db",
    ".env",
    "export_credentials.cfg",
}


def verify(path: Path) -> None:
    with ZipFile(path) as package:
        entries = [item for item in package.infolist() if not item.is_dir()]
        names = {item.filename for item in entries}
        missing = REQUIRED - names
        if missing:
            raise ValueError("Missing output: " + ", ".join(sorted(missing)))
        for item in entries:
            name = item.filename.replace("\\", "/")
            parts = Path(name).parts
            if (
                name.startswith("/")
                or ".." in parts
                or any(part.lower() in BLOCKED_PARTS for part in parts)
                or any(
                    part.lower().endswith(
                        (
                            ".db",
                            ".db-wal",
                            ".db-shm",
                            ".sqlite",
                            ".sqlite3",
                            ".key",
                            ".pem",
                        )
                    )
                    for part in parts
                )
                or any(part.lower().startswith((".env", ".dev.vars")) for part in parts)
                or name
                not in {"LAIN.exe", "LEEME.txt", "lain-ai.json", "lain-online.json"}
                and not name.startswith(ALLOWED_PREFIXES)
            ):
                raise ValueError("Unsafe entry: " + name)
            if item.file_size == 0 and name in REQUIRED - {"LEEME.txt"}:
                raise ValueError("Empty output: " + name)
            if name == "lain-online.json":
                if item.file_size > 2048 or json.loads(
                    package.read(item).decode("utf-8-sig")
                ) != {"server_url": "", "player_token": ""}:
                    raise ValueError(
                        "A public ZIP must not include a player's private access"
                    )
            if name == "lain-ai.json":
                if item.file_size > 2048:
                    raise ValueError("Invalid AI configuration")
                config = json.loads(package.read(item).decode("utf-8-sig"))
                if (
                    not isinstance(config, dict)
                    or set(config) != {"gateway_url"}
                    or not isinstance(config["gateway_url"], str)
                ):
                    raise ValueError("AI configuration must contain only a public URL")
                if config["gateway_url"].strip():
                    parsed = urlsplit(config["gateway_url"].strip().rstrip("/"))
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
                        raise ValueError("Invalid public AI URL")
        if package.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: python distribution/check_zip.py path/to/LAIN-Beta-0.1-Windows.zip"
        )
    verify(Path(sys.argv[1]))
    print("BETA01_ZIP_VERIFIED", sys.argv[1])
