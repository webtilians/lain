"""Verify that a distributable archive has required binaries but no personal data."""
from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZipFile


REQUIRED = {
    "LAIN.exe",
    "Game/LAIN-Game.exe",
    "Game/LAIN-Game.pck",
    "Server/LainServer.exe",
    "Server/_internal/server/content/cafe_catalog.json",
    "LEEME.txt",
}
ALLOWED_PREFIXES = ("Game/", "Server/")
BLOCKED_PARTS = {
    ".git", ".godot", ".venv", "world.db", "save.db",
    "exchange01.db", ".env", "export_credentials.cfg",
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
                or any(part.lower().endswith((".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3", ".key", ".pem")) for part in parts)
                or any(part.lower().startswith(".env") for part in parts)
                or name not in {"LAIN.exe", "LEEME.txt"} and not name.startswith(ALLOWED_PREFIXES)
            ):
                raise ValueError("Unsafe entry: " + name)
            if item.file_size == 0 and name in REQUIRED - {"LEEME.txt"}:
                raise ValueError("Empty output: " + name)
        if package.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python distribution/check_zip.py path/to/LAIN-Beta-0.1-Windows.zip")
    verify(Path(sys.argv[1]))
    print("BETA01_ZIP_VERIFIED", sys.argv[1])
