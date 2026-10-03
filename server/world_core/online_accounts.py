"""Self-service online accounts: a name, a password and an invite code.

Registration is closed unless the owner sets LAIN_SIGNUP_CODE (players need
that code) or LAIN_SIGNUP_OPEN=1. Passwords are stored as scrypt hashes.
Logging in issues a fresh token, so a new device signs the old one out.
Accounts created by the owner before this existed have no password: their
holder (who still has the old token) can choose one from the start menu.
"""
import hashlib
import hmac
import os
import secrets
import time
import unicodedata
from collections import defaultdict, deque
from threading import Lock

from .database import get_connection
from . import online

RESERVED = {"k", "nora", "lain", "player", "jugador", "admin", "administrador", "root", "sistema",
            "wired", "noema", "kagami", "sesion cero", "sesión cero", "anfitrion", "anfitrión"}
WORDS = ["cable", "nodo", "señal", "eco", "latido", "puerto", "enlace", "espejo", "noche", "lluvia",
         "neón", "torre", "canal", "trama", "ruta", "faro", "humo", "cinta", "vapor", "reloj"]
_lock = Lock()
_attempts: dict = defaultdict(deque)


def initialize():
    online.initialize()
    with get_connection() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS online_logins (
                name_key TEXT PRIMARY KEY, actor_id TEXT NOT NULL UNIQUE,
                salt BLOB NOT NULL, pw_hash BLOB NOT NULL,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)"""
        )


def clean_name(name: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(name)).split())


def name_key(name: str) -> str:
    return clean_name(name).casefold()


def _valid_name(name: str) -> bool:
    return (3 <= len(name) <= 16 and all(ch.isalnum() or ch in " -_" for ch in name)
            and name_key(name) not in RESERVED)


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)


def _check_password(password: str) -> None:
    if not isinstance(password, str) or not 6 <= len(password) <= 128:
        raise ValueError("WEAK_PASSWORD")


def _throttle(key: tuple, count: int, seconds: float) -> None:
    with _lock:
        now = time.monotonic()
        queue = _attempts[key]
        while queue and now - queue[0] >= seconds:
            queue.popleft()
        if len(queue) >= count:
            raise ValueError("PLEASE_WAIT")
        queue.append(now)


def signup_policy() -> str:
    if os.getenv("LAIN_SIGNUP_OPEN", "0") == "1":
        return "OPEN"
    return "INVITE" if os.getenv("LAIN_SIGNUP_CODE", "").strip() else "CLOSED"


def _name_taken(conn, key: str) -> bool:
    if conn.execute("SELECT 1 FROM online_logins WHERE name_key=?", (key,)).fetchone():
        return True
    # Characters and existing owner-created players keep their names too.
    return any(name_key(row[0]) == key for row in conn.execute("SELECT name FROM agents"))


def _store(conn, key: str, actor: str, password: str) -> None:
    salt = secrets.token_bytes(16)
    now = int(time.time())
    conn.execute(
        """INSERT INTO online_logins VALUES(?,?,?,?,?,?)
        ON CONFLICT(actor_id) DO UPDATE SET salt=excluded.salt, pw_hash=excluded.pw_hash,
        updated_at=excluded.updated_at""",
        (key, actor, salt, _hash(password, salt), now, now),
    )


def _new_token(conn, actor: str) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("UPDATE online_credentials SET token_hash=?, revoked=0 WHERE actor_id=?",
                 (hashlib.sha256(token.encode("utf-8")).hexdigest(), actor))
    return token


def register(name: str, password: str, invite: str, client: str) -> dict:
    policy = signup_policy()
    if policy == "CLOSED":
        raise ValueError("REGISTRATION_CLOSED")
    _throttle(("register", client), 3, 3600)
    if policy == "INVITE":
        expected = os.getenv("LAIN_SIGNUP_CODE", "").strip().casefold()
        if not hmac.compare_digest(" ".join(str(invite).split()).casefold().encode(), expected.encode()):
            raise ValueError("INVALID_INVITE")
    name = clean_name(name)
    if not _valid_name(name):
        raise ValueError("INVALID_NAME")
    _check_password(password)
    initialize()
    key = name_key(name)
    with get_connection() as conn:
        if _name_taken(conn, key):
            raise ValueError("NAME_TAKEN")
    actor, token = online.create_player(name)
    with get_connection() as conn:
        _store(conn, key, actor, password)
    return {"token": token, "name": name, "actor_id": actor}


def login(name: str, password: str, client: str) -> dict:
    _throttle(("login", client), 10, 600)
    key = name_key(name)
    _throttle(("login-name", key), 10, 600)
    initialize()
    with get_connection() as conn:
        row = conn.execute(
            """SELECT l.actor_id, l.salt, l.pw_hash, a.name FROM online_logins l
            JOIN agents a ON a.id=l.actor_id JOIN online_credentials o ON o.actor_id=l.actor_id
            WHERE l.name_key=?""", (key,)).fetchone()
        # Same work and answer for an unknown name and a wrong password.
        salt = row[1] if row else b"\0" * 16
        digest = _hash(str(password)[:128], salt)
        if row is None or not hmac.compare_digest(digest, row[2]):
            raise ValueError("INVALID_LOGIN")
        return {"token": _new_token(conn, row[0]), "name": row[3], "actor_id": row[0]}


def me(actor: str) -> dict:
    initialize()
    with get_connection() as conn:
        name = conn.execute("SELECT name FROM agents WHERE id=?", (actor,)).fetchone()[0]
        has = conn.execute("SELECT 1 FROM online_logins WHERE actor_id=?", (actor,)).fetchone() is not None
    return {"name": name, "has_password": has, "actor_id": actor}


def set_password(actor: str, current: str, new: str, client: str) -> dict:
    _throttle(("password", client), 10, 600)
    _check_password(new)
    initialize()
    with get_connection() as conn:
        row = conn.execute("SELECT salt, pw_hash FROM online_logins WHERE actor_id=?", (actor,)).fetchone()
        if row is not None and not hmac.compare_digest(_hash(str(current)[:128], row[0]), row[1]):
            raise ValueError("INVALID_LOGIN")
        name = conn.execute("SELECT name FROM agents WHERE id=?", (actor,)).fetchone()[0]
        key = name_key(name)
        if row is None and conn.execute("SELECT 1 FROM online_logins WHERE name_key=?", (key,)).fetchone():
            raise ValueError("NAME_TAKEN")
        _store(conn, key, actor, new)
    return me(actor)


def reset_password(name: str) -> str:
    """Owner console only: a new random password for a player who forgot theirs."""
    initialize()
    key = name_key(name)
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.id, a.name FROM agents a JOIN online_credentials o ON o.actor_id=a.id
            WHERE a.controller_type='HUMAN'""").fetchall()
        match = [actor for actor, name in rows if name_key(name) == key]
        if not match:
            raise ValueError("UNKNOWN_PLAYER")
        password = "-".join(secrets.choice(WORDS) for _ in range(2)) + "-" + str(secrets.randbelow(900) + 100)
        _store(conn, key, match[0], password)
    return password


def new_invite_code() -> str:
    return "-".join(secrets.choice(WORDS) for _ in range(2)) + "-" + str(secrets.randbelow(900) + 100)
