"""Local cafe tournaments. World minutes, replays and rewards belong to the server.

NPC opponents are explicitly synthetic. This is not public multiplayer or an
anti-bot service. Reading the board never advances time or grants a reward.
"""
from collections import deque
from functools import lru_cache
import json
import os
import re

from .network_conflict import connection, report
from . import workshop as ws

LEAD = 60
DURATION = 300
PERIOD = 600
ATTEMPTS = 3
PRIZES = (
    ("CODE", "buffer", "Amortiguación"),
    ("DEVICE", "cache", "Memoria de enlace B"),
    ("CODE", "shield", "Protección"),
    ("CODE", "scan", "Exploración"),
)


def enabled(c):
    return (os.getenv("LAIN_CAFE_EVENTS", "0") == "1" and ws.enabled(c)
            and c.execute("SELECT 1 FROM sqlite_master WHERE name='cafe_events'").fetchone() is not None)


def initialize_events():
    if os.getenv("LAIN_CAFE_EVENTS", "0") != "1":
        return
    with connection() as c:
        if not ws.enabled(c):
            return
        c.executescript("""
        CREATE TABLE IF NOT EXISTS cafe_season (
          id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS cafe_events (
          id TEXT PRIMARY KEY, edition INTEGER NOT NULL UNIQUE, opens INTEGER NOT NULL,
          closes INTEGER NOT NULL, board TEXT NOT NULL, prize_kind TEXT NOT NULL,
          prize_model TEXT NOT NULL, prize_name TEXT NOT NULL, settled INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS cafe_entries (
          event TEXT NOT NULL, actor TEXT NOT NULL, name TEXT NOT NULL, npc INTEGER NOT NULL,
          score INTEGER NOT NULL, submitted INTEGER NOT NULL, PRIMARY KEY(event,actor));
        CREATE TABLE IF NOT EXISTS cafe_runs (
          actor TEXT NOT NULL, id TEXT NOT NULL, event TEXT NOT NULL, started INTEGER NOT NULL,
          status TEXT NOT NULL, moves TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '{}',
          PRIMARY KEY(actor,id));
        CREATE TABLE IF NOT EXISTS cafe_requests (
          actor TEXT NOT NULL, id TEXT NOT NULL, command TEXT NOT NULL, result TEXT NOT NULL,
          PRIMARY KEY(actor,id));
        CREATE INDEX IF NOT EXISTS cafe_events_pending ON cafe_events(closes) WHERE settled=0;
        CREATE INDEX IF NOT EXISTS cafe_events_calendar ON cafe_events(opens);
        CREATE INDEX IF NOT EXISTS cafe_runs_event ON cafe_runs(event,actor);
        """)
        c.execute("BEGIN IMMEDIATE")
        now = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        if c.execute("SELECT 1 FROM workshop_players LIMIT 1").fetchone():
            c.execute("INSERT OR IGNORE INTO cafe_season VALUES(1,?)", (now + LEAD,))
        _advance(c, now)


def board_for(edition):
    # Four authored orientations, with the immutable layout stored in each event.
    variant = (edition - 1) % 4
    def transform(point):
        x, y = point
        return [7 - x if variant & 1 else x, 7 - y if variant & 2 else y]
    return {**ws.ARCADE, "version": 2, "variant": variant,
            **{k: [transform(p) for p in ws.ARCADE[k]] for k in ("walls", "chips")},
            **{k: transform(ws.ARCADE[k]) for k in ("start", "exit")}}


@lru_cache(maxsize=8)
def npc_route(variant, required):
    """A finite game-playing NPC; its public score uses the same replay rules."""
    board = board_for(variant + 1)
    walls = {tuple(p) for p in board["walls"]}
    chips = {tuple(p): i for i, p in enumerate(board["chips"])}
    queue = deque([(*board["start"], 0, "")])
    seen = {(*board["start"], 0)}
    while queue:
        x, y, mask, route = queue.popleft()
        if [x, y] == board["exit"]:
            if mask.bit_count() >= required:
                return route
            continue
        for direction, (dx, dy) in {"U": (0,-1), "D": (0,1), "L": (-1,0), "R": (1,0)}.items():
            nx, ny = x + dx, y + dy
            if not (0 <= nx < 8 and 0 <= ny < 8) or (nx, ny) in walls:
                continue
            next_mask = mask | (1 << chips[(nx, ny)] if (nx, ny) in chips else 0)
            key = (nx, ny, next_mask)
            if key not in seen:
                seen.add(key)
                queue.append((*key, route + direction))
    raise RuntimeError("UNSOLVABLE_CAFE_BOARD")


def _seed(c, index, epoch):
    edition = index + 1
    ident = f"KISSA_{edition:06d}"
    if c.execute("SELECT 1 FROM cafe_events WHERE id=?", (ident,)).fetchone():
        return
    board = board_for(edition)
    opens = epoch + index * PERIOD
    c.execute("INSERT INTO cafe_events VALUES(?,?,?,?,?,?,?,?,0)",
              (ident, edition, opens, opens + DURATION, json.dumps(board), *PRIZES[index % len(PRIZES)]))
    for actor, name, required, offset in [
        ("CAFE_NPC_AKI", "Aki", 3, 40), ("CAFE_NPC_MIKA", "Mika", 4, 120),
    ]:
        replay = ws.arcade_replay(npc_route(board["variant"], required), board)
        c.execute("INSERT INTO cafe_entries VALUES(?,?,?,?,?,?)",
                  (ident, actor, name, 1, replay["score"], opens + offset))


def _ranking(c, event, now):
    rows = c.execute("""SELECT actor,name,npc,score,submitted FROM cafe_entries
        WHERE event=? AND submitted<=? ORDER BY score DESC,submitted,actor""", (event, now)).fetchall()
    result = []
    previous = None
    rank = 0
    for index, (actor, name, npc, score, submitted) in enumerate(rows, 1):
        if score != previous:
            rank = index
        result.append(dict(actor=actor, name=name, npc=bool(npc), score=score, minute=submitted, rank=rank))
        previous = score
    return result


def _advance(c, now):
    epoch = c.execute("SELECT epoch FROM cafe_season WHERE id=1").fetchone()
    if not epoch:
        return
    index = max(0, (now - epoch[0]) // PERIOD)
    # Bounded catch-up after a save migration: never manufacture thousands of missed rounds.
    for slot in (index, index + 1):
        _seed(c, slot, epoch[0])
    for ident, edition, closes, kind, model, name in c.execute("""SELECT id,edition,closes,
        prize_kind,prize_model,prize_name FROM cafe_events WHERE settled=0 AND closes<=?""", (now,)).fetchall():
        ranks = _ranking(c, ident, closes - 1)
        winners = {r["actor"] for r in ranks if r["rank"] == 1}
        for (actor,) in c.execute("SELECT DISTINCT actor FROM cafe_runs WHERE event=?", (ident,)).fetchall():
            if actor in winners:
                ws._grant(c, actor, f"event_{ident}", kind, model, f"Kissa · torneo {edition} · primer puesto", now)
                message = f"Torneo {edition} cerrado: primer puesto. {name} está en tu PC; conecta el equipo o compila el código. Las copias no suman potencia."
            else:
                message = f"Torneo {edition} cerrado: no obtuviste el primer puesto. La clasificación final está en Eventos."
            report(c, actor, now, "CAFE_EVENT", message)
        c.execute("UPDATE cafe_runs SET status='EXPIRED' WHERE event=? AND status='OPEN'", (ident,))
        c.execute("UPDATE cafe_events SET settled=1 WHERE id=?", (ident,))


def advance_events(now):
    with connection() as c:
        if enabled(c):
            c.execute("BEGIN IMMEDIATE")
            _advance(c, now)


def perform_event_action(actor, action, data, request_id):
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
        raise ValueError("INVALID_REQUEST_ID")
    fields = {"START": {"event"}, "FINISH": {"run_id", "moves"}}
    if action not in fields or not isinstance(data, dict) or set(data) != fields[action] or any(type(v) is not str or len(v) > 100 for v in data.values()):
        raise ValueError("INVALID_EVENT_DATA")
    command = json.dumps([action, data], sort_keys=True)
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        if not enabled(c):
            raise ValueError("CAFE_EVENTS_DISABLED")
        player = c.execute("""SELECT a.name,a.location FROM agents a JOIN workshop_players w
            ON w.actor=a.id WHERE a.id=? AND a.controller_type='HUMAN'""", (actor,)).fetchone()
        if not player:
            raise ValueError("WIRED_CONNECTION_REQUIRED")
        old = c.execute("SELECT command,result FROM cafe_requests WHERE actor=? AND id=?", (actor, request_id)).fetchone()
        if old:
            if old[0] != command:
                raise ValueError("REQUEST_ID_REUSED")
            return json.loads(old[1])
        if player[1] != "CAFE":
            raise ValueError("CAFE_REQUIRED")
        now = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        _advance(c, now)
        run = None
        if action == "FINISH":
            run = c.execute("SELECT event,status,moves,result FROM cafe_runs WHERE actor=? AND id=?",
                            (actor, data["run_id"])).fetchone()
            if not run:
                raise ValueError("EVENT_RUN_REQUIRED")
            if run[1] == "FINISHED":
                if run[2] != data["moves"]:
                    raise ValueError("EVENT_ALREADY_FINISHED")
                c.execute("INSERT INTO cafe_requests VALUES(?,?,?,?)", (actor, request_id, command, run[3]))
                return json.loads(run[3])
        event = data["event"] if action == "START" else run[0]
        row = c.execute("SELECT opens,closes,board,settled FROM cafe_events WHERE id=?", (event,)).fetchone()
        if not row:
            raise ValueError("EVENT_NOT_FOUND")
        if not row[0] <= now < row[1] or row[3]:
            raise ValueError("EVENT_NOT_OPEN")
        board = json.loads(row[2])
        if action == "START":
            opened = c.execute("SELECT id FROM cafe_runs WHERE actor=? AND event=? AND status='OPEN'", (actor, event)).fetchone()
            count = c.execute("SELECT count(*) FROM cafe_runs WHERE actor=? AND event=?", (actor, event)).fetchone()[0]
            if not opened and count >= ATTEMPTS:
                raise ValueError("EVENT_ATTEMPTS_USED")
            run_id = opened[0] if opened else request_id
            if not opened:
                c.execute("INSERT INTO cafe_runs(actor,id,event,started,status) VALUES(?,?,?,?,'OPEN')",
                          (actor, run_id, event, now))
                count += 1
            result = dict(text=f"Torneo · intento {count}/{ATTEMPTS}. Termina antes del minuto {row[1]}. El tiempo sigue corriendo al cerrar el terminal.",
                          board=board, run_id=run_id, event_id=event, closes=row[1])
        else:
            if run[1] != "OPEN":
                raise ValueError("EVENT_RUN_REQUIRED")
            replay = ws.arcade_replay(data["moves"], board)
            if not replay["finished"] and len(data["moves"]) < board["max_moves"]:
                raise ValueError("ARCADE_NOT_FINISHED")
            if replay["won"]:
                c.execute("""INSERT INTO cafe_entries VALUES(?,?,?,0,?,?)
                    ON CONFLICT(event,actor) DO UPDATE SET score=excluded.score,submitted=excluded.submitted
                    WHERE excluded.score>cafe_entries.score""", (event, actor, player[0], replay["score"], now))
            result = {**replay, "event_id": event, "text": f"Resultado verificado: {replay['score']} puntos. " +
                      ("Se conserva tu mejor marca; el premio se adjudica al cierre." if replay["won"] else "Necesitas al menos tres paquetes y llegar a la salida para clasificar.")}
            c.execute("UPDATE cafe_runs SET status='FINISHED',moves=?,result=? WHERE actor=? AND id=?",
                      (data["moves"], json.dumps(result, ensure_ascii=False), actor, data["run_id"]))
        c.execute("INSERT INTO cafe_requests VALUES(?,?,?,?)", (actor, request_id, command, json.dumps(result, ensure_ascii=False)))
        return result


def event_snapshot(actor="PLAYER_1"):
    with connection() as c:
        if not enabled(c) or not c.execute("SELECT 1 FROM workshop_players WHERE actor=?", (actor,)).fetchone():
            return {"active": False}
        now = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        items = []
        rows = c.execute("""SELECT id,edition,opens,closes,prize_name,settled FROM cafe_events
            ORDER BY opens DESC LIMIT 5""").fetchall()
        for ident, edition, opens, closes, prize, settled in reversed(rows):
            ranking = _ranking(c, ident, min(now, closes - 1))
            for row in ranking:
                row["mine"] = row.pop("actor") == actor
            used = c.execute("SELECT count(*) FROM cafe_runs WHERE actor=? AND event=?", (actor, ident)).fetchone()[0]
            opened = c.execute("SELECT id FROM cafe_runs WHERE actor=? AND event=? AND status='OPEN'", (actor, ident)).fetchone()
            won = c.execute("SELECT 1 FROM workshop_assets WHERE actor=? AND id=?", (actor, f"event_{ident}")).fetchone() is not None
            state = "CLOSED" if now >= closes else "UPCOMING" if now < opens else "OPEN"
            items.append(dict(id=ident, edition=edition, opens=opens, closes=closes, prize=prize,
                              status=state, settled=bool(settled), ranking=ranking, attempts=used,
                              run_id=opened[0] if opened and state == "OPEN" else "", won=won))
        return dict(active=True, minute=now, attempts_limit=ATTEMPTS, events=items,
                    rules="Clasificación local con PNJ. Tres intentos por edición; cuenta tu mejor marca válida. Empatar en primer puesto comparte el premio. El cierre usa el reloj del mundo, que no avanza con el servidor apagado.")
