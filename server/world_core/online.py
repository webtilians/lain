"""Small private online world: server-issued identities and ephemeral presence.

One World Core process owns SQLite. Provision/revoke credentials with the owner
CLI; clients cannot register themselves or choose which actor they control.
"""

from collections import defaultdict, deque
from contextlib import contextmanager
import hashlib
import math
import os
import secrets
import threading
import time
import uuid

from .database import get_connection, load_or_create_agent, load_simulation_minute
from .models import Agent

_lock = threading.RLock()
_presence = {}
_connections = {}
_chat = deque(maxlen=100)
_limits = defaultdict(deque)
PRESENCE_TTL = 12
# The shadow (BIBLIA_NARRATIVA.md, section 7): while a player is offline, others
# see something with their face walking the routes they used to take.
TRAIL_POINTS = 48
TRAIL_EVERY = 2.0
MAX_SHADOWS = 3
_trail_clock = {}
_trail_slot = {}
PRIVATE_ROOMS = {"APARTMENT"}


def enabled():
    return os.getenv("LAIN_ONLINE", "0") == "1"


@contextmanager
def world_host_lock():
    """OS lock: only one online World Core may own a save, even across processes."""
    from . import database

    path = database.DB_PATH.resolve().with_suffix(".host.lock")
    with path.open("a+b") as handle:
        try:
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError(
                "Este mundo ya está abierto. Detén el servidor antes de abrir otro o crear jugadores."
            ) from None
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def initialize():
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS online_credentials (
                token_hash TEXT PRIMARY KEY, actor_id TEXT NOT NULL UNIQUE,
                created_at INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS online_actions (
                actor_id TEXT NOT NULL, request_id TEXT NOT NULL,
                command TEXT NOT NULL, result TEXT,
                PRIMARY KEY(actor_id, request_id));
            CREATE TABLE IF NOT EXISTS online_trails (
                player_id TEXT NOT NULL, location TEXT NOT NULL, slot INTEGER NOT NULL,
                x REAL NOT NULL, y REAL NOT NULL, z REAL NOT NULL, yaw REAL NOT NULL,
                PRIMARY KEY(player_id, location, slot));
        """
        )


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_player(name):
    """Owner-only entry point; deliberately not an HTTP endpoint."""
    from .messages import ensure_initial_player_message
    from .prologue import initialize_prologue

    name = " ".join(name.split())
    if not 1 <= len(name) <= 24 or any(
        not (ch.isalnum() or ch in " -_") for ch in name
    ):
        raise ValueError("INVALID_PLAYER_NAME")
    initialize()
    actor_id = "PLAYER_" + uuid.uuid4().hex
    token = secrets.token_urlsafe(32)
    load_or_create_agent(
        Agent(
            id=actor_id,
            name=name,
            faction="UNALIGNED",
            location="APARTMENT",
            goal="UNKNOWN",
            controller_type="HUMAN",
        )
    )
    ensure_initial_player_message(actor_id)
    initialize_prologue()
    with get_connection() as conn:
        if os.getenv("LAIN_PROLOGUE_ENABLED", "0") == "1":
            conn.execute(
                "INSERT INTO player_prologue VALUES(?, 'FIND_TEACHER', ?)",
                (actor_id, load_simulation_minute()),
            )
        # Publish a usable identity only after its private starting state exists.
        conn.execute(
            "INSERT INTO online_credentials VALUES(?,?,?,0)",
            (_hash(token), actor_id, int(time.time())),
        )
    return actor_id, token


def authenticate(token):
    if not isinstance(token, str) or not 40 <= len(token) <= 128:
        raise ValueError("INVALID_PLAYER_ACCESS")
    with get_connection() as conn:
        row = conn.execute(
            """SELECT o.actor_id FROM online_credentials o JOIN agents a ON a.id=o.actor_id
            WHERE token_hash=? AND revoked=0 AND a.controller_type='HUMAN'""",
            (_hash(token),),
        ).fetchone()
    if row is None:
        raise ValueError("INVALID_PLAYER_ACCESS")
    return row[0]


def revoke_player(actor_id):
    with get_connection() as conn:
        conn.execute(
            "UPDATE online_credentials SET revoked=1 WHERE actor_id=?", (actor_id,)
        )
    with _lock:
        _presence.pop(actor_id, None)
        _connections.pop(actor_id, None)


def connect(actor_id, instance):
    if not instance or not 8 <= len(instance) <= 80:
        raise ValueError("CLIENT_INSTANCE_REQUIRED")
    with _lock:
        previous = _connections.get(actor_id)
        if (
            previous
            and time.monotonic() - previous[1] < PRESENCE_TTL
            and previous[0] != instance
        ):
            raise ValueError("PLAYER_ALREADY_CONNECTED")
        _connections[actor_id] = (instance, time.monotonic())


def is_active(actor_id):
    with _lock:
        connection = _connections.get(actor_id)
        return bool(connection and time.monotonic() - connection[1] < PRESENCE_TTL)


def limit(actor_id, lane, count, seconds):
    with _lock:
        now = time.monotonic()
        queue = _limits[(actor_id, lane)]
        while queue and now - queue[0] >= seconds:
            queue.popleft()
        if len(queue) >= count:
            raise ValueError("PLEASE_WAIT")
        queue.append(now)


def heartbeat(actor_id, instance, location, x, y, z, yaw, dialogue=False, received_at=None):
    """Coordinates are cosmetic, bounded and speed-checked. No world MOVE here."""
    if not 8 <= len(instance) <= 80 or any(
        not math.isfinite(v) for v in (x, y, z, yaw)
    ):
        raise ValueError("INVALID_PRESENCE")
    if not (-160 <= x <= 160 and -180 <= z <= 100 and -2 <= y <= 12):
        raise ValueError("POSITION_OUT_OF_BOUNDS")
    limit(actor_id, "presence", 12, 1)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT name,location FROM agents WHERE id=?", (actor_id,)
        ).fetchone()
    if row is None or row[1] != location:
        raise ValueError("LOCATION_CHANGED")
    with _lock:
        # Time the request by its arrival, not by when it was processed.
        now = time.monotonic() if received_at is None else received_at
        previous = _presence.get(actor_id)
        fresh = previous and now - previous["at"] < PRESENCE_TTL
        if fresh and previous["instance"] != instance:
            raise ValueError("PLAYER_ALREADY_CONNECTED")
        accepted = True
        if fresh and previous["location"] == location:
            # The Godot controller walks at 3.5 m/s. Permit a small jitter margin,
            # and gaps up to the presence TTL (slow tunnel, long clock tick).
            elapsed = max(0.0, now - previous["at"])
            distance = math.hypot(x - previous["x"], z - previous["z"])
            if distance > 5 * min(PRESENCE_TTL, elapsed) + 0.75:
                x, y, z = previous["x"], previous["y"], previous["z"]
                accepted = False
        _presence[actor_id] = dict(
            id=actor_id,
            name=row[0],
            location=location,
            x=x,
            y=y,
            z=z,
            yaw=yaw,
            at=now,
            instance=instance,
            dialogue=dialogue,
        )
        response = {
            "accepted": accepted,
            "position": {"x": x, "y": y, "z": z},
            "players": visible_players(actor_id, location),
            "chat": visible_chat(actor_id, location),
        }
        present = {item["id"] for item in _presence.values() if now - item["at"] < PRESENCE_TTL}
    if accepted:
        _record_trail(actor_id, location, x, y, z, yaw, now)
    response["players"] += shadows(actor_id, location, present)
    return response


def shadows_enabled():
    return enabled() and os.getenv("LAIN_SHADOW", "0") == "1"


def _record_trail(actor_id, location, x, y, z, yaw, now):
    """A point every few seconds, a ring of the last ones per place."""
    if not shadows_enabled() or location in PRIVATE_ROOMS:
        return
    if now - _trail_clock.get(actor_id, float("-inf")) < TRAIL_EVERY:
        return
    _trail_clock[actor_id] = now
    slot = _trail_slot.get((actor_id, location), 0)
    _trail_slot[(actor_id, location)] = (slot + 1) % TRAIL_POINTS
    with get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO online_trails VALUES(?,?,?,?,?,?,?)",
                     (actor_id, location, slot, x, y, z, yaw))


def shadows(actor_id, location, present):
    """Offline players' shadows walking their recorded route here."""
    if not shadows_enabled() or location in PRIVATE_ROOMS:
        return []
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT t.player_id, a.name, t.x, t.y, t.z, t.yaw FROM online_trails t
            JOIN agents a ON a.id=t.player_id WHERE t.location=? AND t.player_id!=?
            ORDER BY t.player_id, t.slot""", (location, actor_id)).fetchall()
    trails = {}
    for player, name, x, y, z, yaw in rows:
        if player not in present:
            trails.setdefault((player, name), []).append((x, y, z, yaw))
    tick = int(time.time() / TRAIL_EVERY)
    result = []
    for (player, name), points in sorted(trails.items())[:MAX_SHADOWS]:
        if len(points) < 4:
            continue
        x, y, z, yaw = points[tick % len(points)]
        result.append({"id": "SHADOW_" + player, "name": name, "x": x, "y": y, "z": z, "yaw": yaw, "shadow": True})
    return result


def trail_summary(actor_id):
    """{location: points} of the routes the player's shadow repeats."""
    if not shadows_enabled():
        return {}
    with get_connection() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='online_trails'").fetchone():
            return {}
        return dict(conn.execute("SELECT location, COUNT(*) FROM online_trails WHERE player_id=? GROUP BY location "
                                 "ORDER BY COUNT(*) DESC", (actor_id,)).fetchall())


def disconnect(actor_id, instance):
    with _lock:
        if _presence.get(actor_id, {}).get("instance") == instance:
            _presence.pop(actor_id, None)
        if _connections.get(actor_id, (None,))[0] == instance:
            _connections.pop(actor_id, None)


def visible_players(actor_id, location):
    if location in PRIVATE_ROOMS:
        return []
    now = time.monotonic()
    with _lock:
        return [
            {key: item[key] for key in ("id", "name", "x", "y", "z", "yaw")}
            for item in _presence.values()
            if item["id"] != actor_id
            and item["location"] == location
            and now - item["at"] < PRESENCE_TTL
        ]


def clear_location(actor_id):
    with _lock:
        _presence.pop(actor_id, None)


def busy_npcs():
    if not enabled():
        return set()
    with _lock:
        active = [
            actor
            for actor, item in _presence.items()
            if item["dialogue"] and time.monotonic() - item["at"] < PRESENCE_TTL
        ]
    if not active:
        return set()
    with get_connection() as conn:
        return {
            row[0]
            for actor in active
            for row in conn.execute(
                """SELECT i.recipient_id
            FROM interactions i JOIN agents p ON p.id=i.initiator_id JOIN agents n ON n.id=i.recipient_id
            WHERE i.initiator_id=? AND i.topic='PLAYER_INITIATED_CONVERSATION'
            AND i.status IN ('OPEN','RESUMING') AND p.location=n.location""",
                (actor,),
            )
        }


def send_chat(actor_id, text):
    text = text.strip()
    if not 1 <= len(text) <= 240 or any(ord(ch) < 32 for ch in text):
        raise ValueError("INVALID_CHAT_MESSAGE")
    limit(actor_id, "chat", 4, 10)
    with _lock:
        sender = _presence.get(actor_id)
        if not sender or time.monotonic() - sender["at"] >= PRESENCE_TTL:
            raise ValueError("PLAYER_NOT_PRESENT")
        if sender["location"] in PRIVATE_ROOMS:
            raise ValueError("PRIVATE_ROOM")
        recipients = {
            actor
            for actor, item in _presence.items()
            if item["location"] == sender["location"]
            and time.monotonic() - item["at"] < PRESENCE_TTL
        }
        _chat.append(
            dict(
                # Clients retain seen IDs while reconnecting. A restarted host
                # must not reuse IDs for different messages.
                id=uuid.uuid4().hex,
                actor_id=actor_id,
                name=sender["name"],
                text=text,
                location=sender["location"],
                recipients=recipients,
                at=time.monotonic(),
            )
        )
        return {"sent": True}


def visible_chat(actor_id, location):
    with _lock:
        return [
            {key: row[key] for key in ("id", "actor_id", "name", "text")}
            for row in _chat
            if row["location"] == location
            and actor_id in row["recipients"]
            and time.monotonic() - row["at"] < 120
        ][-20:]
