"""Prove that a server backup can be restored: load it into a fresh SQLite file and read it back.

    python tools/check_backup.py online-world-STAMP.sql.gz [--access access-STAMP.tar.gz] [--to world.db]

Prints one line of JSON and never a token, e.g.
    {"ok": true, "players": 4, "accounts": 4, "tables": 61, "minute": 1234, "access": 4}
Exits with 1 when the copy is damaged. vps.ps1 -Backup runs it on every copy it
downloads, and -Restore uses --to to rebuild the database it sends to the server.
"""
import argparse
import gzip
import json
import sqlite3
import sys
import tarfile
import tempfile
import zlib
from contextlib import closing
from pathlib import Path

REQUIRED = {"agents", "simulation_state"}


def restore(dump: Path, target: Path) -> dict:
    """Rebuild the world from an `sqlite3 .dump` (gzip) into target and describe it."""
    target.unlink(missing_ok=True)
    script = gzip.decompress(dump.read_bytes()).decode("utf-8")
    with closing(sqlite3.connect(target)) as conn:
        conn.executescript(script)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if integrity != "ok":
            raise ValueError("la base restaurada no pasa integrity_check")
        if not REQUIRED <= tables:
            raise ValueError("no parece un mundo de LAIN (faltan tablas)")
        players = conn.execute("SELECT COUNT(*) FROM agents WHERE controller_type='HUMAN'").fetchone()[0]
        accounts = 0
        if "online_credentials" in tables:
            accounts = conn.execute("SELECT COUNT(*) FROM online_credentials WHERE revoked=0").fetchone()[0]
        minute = conn.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()
    return {"players": players, "accounts": accounts, "tables": len(tables), "minute": minute[0] if minute else None}


def access_files(archive: Path) -> int:
    """How many complete access files the archive holds. Read in memory only, never extracted."""
    count = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if not (member.isfile() and member.name.endswith("/lain-online.json")):
                continue
            data = json.loads(tar.extractfile(member).read().decode("utf-8-sig"))
            if not (isinstance(data, dict) and data.get("server_url") and data.get("player_token")):
                raise ValueError(f"acceso incompleto: {member.name.split('/')[-2]}")
            count += 1
    return count


def check(dump: Path, access: Path | None = None, target: Path | None = None) -> dict:
    try:
        if target is None:
            with tempfile.TemporaryDirectory() as folder:
                result = restore(dump, Path(folder) / "world.db")
        else:
            result = restore(dump, target)
        if access is not None:
            result["access"] = access_files(access)
        return {"ok": True, **result}
    except (OSError, EOFError, UnicodeDecodeError, zlib.error, sqlite3.Error, tarfile.TarError, ValueError) as error:
        if target is not None:
            target.unlink(missing_ok=True)
        return {"ok": False, "error": str(error) or type(error).__name__}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Comprueba que una copia del mundo se puede restaurar.")
    parser.add_argument("dump", type=Path)
    parser.add_argument("--access", type=Path)
    parser.add_argument("--to", type=Path, help="deja aquí la base restaurada")
    args = parser.parse_args(argv)
    result = check(args.dump, args.access, args.to)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
