"""Off-server copies: a copy only counts if it can be rebuilt into a world the game can read."""
import gzip
import io
import json
import sqlite3
import tarfile
from contextlib import closing
from pathlib import Path

from server.world_core import admin, database
from tools import check_backup
from tests.test_online_world import world  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]


def dump(path: Path, target: Path) -> Path:
    """What lain-backup writes: the SQL text of the whole database, gzipped."""
    with closing(sqlite3.connect(path)) as conn:
        script = "PRAGMA foreign_keys=OFF;\n" + "\n".join(conn.iterdump()) + "\n"
    target.write_bytes(gzip.compress(script.encode("utf-8")))
    return target


def access_archive(target: Path, players: dict) -> Path:
    with tarfile.open(target, "w:gz") as tar:
        for folder, token in players.items():
            data = json.dumps({"server_url": "https://lain.test", "player_token": token}).encode()
            info = tarfile.TarInfo(f"access/{folder}/lain-online.json")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return target


def test_a_copy_of_a_live_world_is_rebuilt_and_read_back(world, tmp_path):  # noqa: F811
    copy = dump(database.DB_PATH, tmp_path / "online-world-2026-10-04-130000.sql.gz")
    restored = tmp_path / "restored.db"
    result = check_backup.check(copy, target=restored)
    assert result["ok"] and result["accounts"] == 2 and result["players"] >= 2
    with closing(sqlite3.connect(restored)) as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM agents WHERE controller_type='HUMAN'")}
    assert {"Alice", "Bob"} <= names


def test_access_files_are_counted_without_ever_printing_a_token(world, tmp_path, capsys):  # noqa: F811
    copy = dump(database.DB_PATH, tmp_path / "online-world.sql.gz")
    secret = "s" * 43
    archive = access_archive(tmp_path / "access.tar.gz", {"Alice-1": secret, "Bob-2": "b" * 43})
    assert check_backup.main([str(copy), "--access", str(archive)]) == 0
    printed = capsys.readouterr().out
    assert json.loads(printed)["access"] == 2 and secret not in printed


def test_damaged_or_foreign_copies_are_rejected(world, tmp_path):  # noqa: F811
    good = dump(database.DB_PATH, tmp_path / "good.sql.gz").read_bytes()
    cut = tmp_path / "cut.sql.gz"
    cut.write_bytes(good[: len(good) // 2])
    restored = tmp_path / "restored.db"
    assert not check_backup.check(cut, target=restored)["ok"]
    assert not restored.exists()
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    foreign = check_backup.check(dump(empty, tmp_path / "foreign.sql.gz"))
    assert not foreign["ok"] and "LAIN" in foreign["error"]
    broken = access_archive(tmp_path / "broken.tar.gz", {"Alice-1": ""})
    assert not check_backup.check(tmp_path / "good.sql.gz", access=broken)["ok"]


def test_the_panel_shows_when_the_pc_last_verified_a_copy(tmp_path):
    mark = Path(database.DB_PATH).parent / admin.OFFSITE_MARK
    assert admin.offsite_backup() is None
    mark.write_text("1791110400\n", encoding="ascii")
    assert admin.offsite_backup() == 1791110400.0
    assert admin.overview()["server"]["offsite_backup"] == 1791110400.0
    assert "Copia en tu PC" in admin.PAGE


def test_server_script_names_every_copy_and_writes_the_panels_mark():
    script = (ROOT / "deploy" / "vps" / "bin" / "lain-backup").read_text(encoding="utf-8")
    # A later copy must never overwrite an earlier one.
    assert "stamp=$(date +%Y-%m-%d-%H%M%S)" in script
    assert f"/var/lib/lain/{admin.OFFSITE_MARK}" in script
    assert "chown lain:lain" in script
    vps = (ROOT / "vps.ps1").read_text(encoding="utf-8-sig")
    assert "lain-backup --downloaded" in vps and "tools\\check_backup.py" in vps


def test_server_copies_wait_for_a_busy_world_and_never_keep_half_a_copy():
    # 2026-10-08: a copy taken while the game was writing came out empty ("database is
    # locked", ROLLBACK) and was kept as if it were good.
    script = (ROOT / "deploy" / "vps" / "bin" / "lain-backup").read_text(encoding="utf-8")
    assert '-cmd ".timeout 30000"' in script
    assert '= "COMMIT;" ]' in script and 'rm -f "$copy.tmp"' in script
    assert script.index('= "COMMIT;" ]') < script.index('mv "$copy.tmp" "$copy"')
    assert "exit 1" in script.split("for attempt")[1]
