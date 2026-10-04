"""Validated data-only event catalogue. Announced boards are immutable in SQLite."""
import hashlib
import json
import os
from pathlib import Path
import re
from functools import lru_cache

from . import signal_snake

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "content" / "cafe_catalog.json"
GAMES = {"bit_courier": "Bit Courier", "signal_snake": signal_snake.NAME}


def active():
    return os.getenv("LAIN_ARCADE_CATALOG", "0") == "1"


def validate(spec):
    from .workshop import MODULES, DEVICES
    if type(spec) is not dict or set(spec) != {"revision","entries"}:
        raise ValueError("CATALOG_FIELDS")
    if type(spec["revision"]) is not int or not 1 <= spec["revision"] <= 1_000_000:
        raise ValueError("CATALOG_REVISION")
    entries = spec["entries"]
    if type(entries) is not list or not 1 <= len(entries) <= 32:
        raise ValueError("CATALOG_ENTRIES")
    ids = set()
    for entry in entries:
        if type(entry) is not dict or set(entry) != {"id","game","orientations","prize"}:
            raise ValueError("CATALOG_ENTRY_FIELDS")
        ident = entry["id"]
        if type(ident) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{2,47}",ident) or ident in ids:
            raise ValueError("CATALOG_ENTRY_ID")
        ids.add(ident)
        if type(entry["game"]) is not str or entry["game"] not in GAMES:
            raise ValueError("CATALOG_GAME")
        orientations = entry["orientations"]
        if (type(orientations) is not list or not 1 <= len(orientations) <= 4
                or any(type(v) is not int or v not in range(4) for v in orientations)
                or len(set(orientations)) != len(orientations)):
            raise ValueError("CATALOG_ORIENTATIONS")
        prize = entry["prize"]
        if type(prize) is not dict or set(prize) != {"kind","model"}:
            raise ValueError("CATALOG_PRIZE")
        if (type(prize["kind"]) is not str or type(prize["model"]) is not str
                or prize["kind"] not in {"CODE","DEVICE"}
                or prize["model"] not in (MODULES if prize["kind"] == "CODE" else DEVICES)):
            raise ValueError("CATALOG_PRIZE")
    return spec


def load(path=None):
    target = Path(path or os.getenv("LAIN_ARCADE_CATALOG_PATH") or DEFAULT_PATH)
    with target.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("CATALOG_TOO_LARGE")
    try:
        return validate(json.loads(raw))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("CATALOG_JSON") from None


@lru_cache(maxsize=1)
def current():
    return load()


def event_spec(index):
    from .workshop import MODULES, DEVICES
    from .cafe_events import board_for
    spec = current()
    entry = spec["entries"][index % len(spec["entries"])]
    variants = entry["orientations"]
    variant = variants[(index // len(spec["entries"])) % len(variants)]
    layout = signal_snake.board(variant) if entry["game"] == "signal_snake" else board_for(variant+1)
    layout.update(game_id=entry["game"], game_name=GAMES[entry["game"]],
                  catalog_entry=entry["id"], catalog_revision=spec["revision"],
                  catalog_digest=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest())
    if entry["game"] == "bit_courier":
        layout["rules"] = "Recoge al menos 3 paquetes y llega a la salida. Máximo 80 movimientos; los choques también consumen un movimiento."
    prize = entry["prize"]
    name = MODULES[prize["model"]]["name"] if prize["kind"] == "CODE" else DEVICES[prize["model"]][0]
    return layout, (prize["kind"],prize["model"],name)


def replay(moves, layout):
    from .workshop import arcade_replay
    game = layout.get("game_id","bit_courier")
    if game == "signal_snake":
        return signal_snake.replay(moves,layout)
    if game != "bit_courier":
        raise ValueError("UNSUPPORTED_ARCADE_GAME")
    return arcade_replay(moves,layout)


def initialize_practice(c):
    c.execute("""CREATE TABLE IF NOT EXISTS workshop_run_boards (
        actor TEXT NOT NULL, id TEXT NOT NULL, board TEXT NOT NULL, PRIMARY KEY(actor,id))""")


def practice_board(c, actor, run):
    from .workshop import ARCADE
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='workshop_run_boards'").fetchone():
        return ARCADE
    row = c.execute("SELECT board FROM workshop_run_boards WHERE actor=? AND id=?", (actor,run)).fetchone()
    return json.loads(row[0]) if row else ARCADE
