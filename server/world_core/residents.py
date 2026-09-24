"""Authored civilian population. Only Simulation initializes/advances this state.

Public objectives are deliberately authored for these residents; they are not
private goals inferred from K, Nora, generated entities, or their memories.
"""
import json
import os
from pathlib import Path
from .database import get_connection, load_or_create_agent
from .models import Agent

CATALOG = Path(__file__).with_name("data") / "residents09.json"


def load_catalog() -> list[dict]:
    items = json.loads(CATALOG.read_text(encoding="utf-8"))
    ids = set()
    from .locations import is_known_location
    for item in items:
        if (item["id"] in ids or not item["id"].startswith("RESIDENT_")
                or not is_known_location(item["location"])
                or not item["name"] or not item["role"] or not item["objective"]
                or len(item["activities"]) != 4 or not all(item["activities"])
                or type(item["cadence"]) is not int or not 1 <= item["cadence"] <= 12
                or item["appearance"] not in {"worker","apron","student","elder","casual","teacher","suit"}
                or not item["skills"] or not 0 <= item["slot"] < 16
                or any(type(v) is not int or not 1 <= v <= 5 for v in item["skills"].values())):
            raise ValueError("INVALID_RESIDENT_CATALOG")
        ids.add(item["id"])
    return items


def initialize_residents() -> list[Agent]:
    from .interactions import initialize_interactions
    initialize_interactions()
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS city_residents (
            actor_id TEXT PRIMARY KEY REFERENCES agents(id),
            profile TEXT NOT NULL, waypoint INTEGER NOT NULL DEFAULT 0,
            activity TEXT NOT NULL, last_minute INTEGER NOT NULL DEFAULT -1
        )""")
        if os.getenv("LAIN_CITY_RESIDENTS_ENABLED", "0") == "1":
            for item in load_catalog():
                conn.execute("""INSERT OR IGNORE INTO agents
                    (id,name,faction,location,goal,energy,controller_type)
                    VALUES (?,?,'CIVILIAN',?,'DAILY_LIFE',1.0,'RESIDENT')""",
                    (item["id"], item["name"], item["location"]))
                # Existing saved names, skills, goals and routine progress win.
                conn.execute("""INSERT OR IGNORE INTO city_residents
                    (actor_id,profile,activity) VALUES (?,?,?)""",
                    (item["id"], json.dumps(item, ensure_ascii=False), item["activities"][0]))
        rows = conn.execute("""SELECT a.id,a.name,a.location FROM agents a
            JOIN city_residents r ON r.actor_id=a.id WHERE a.controller_type='RESIDENT'""").fetchall()
    return [load_or_create_agent(Agent(id=i, name=n, faction="CIVILIAN",
            location=loc, goal="DAILY_LIFE", controller_type="RESIDENT")) for i,n,loc in rows]


def advance_residents(minute: int) -> None:
    """Bounded local activity, driven by accepted world ticks, never GET /state.

    Residents keep their authored workplace/meeting place in this first pass.
    Four authored local points form a walkable circuit in each physical scene.
    OPEN/RESUMING conversations pause it; PAUSED means the player walked away.
    """
    with get_connection() as conn:
        rows = conn.execute("""SELECT r.actor_id,r.profile,r.waypoint,r.last_minute
            FROM city_residents r JOIN agents a ON a.id=r.actor_id
            WHERE a.controller_type='RESIDENT'""").fetchall()
        if not rows:
            return
        busy = {row[0] for row in conn.execute("""SELECT recipient_id FROM interactions
            WHERE status IN ('OPEN','RESUMING') UNION SELECT initiator_id
            FROM interactions WHERE status IN ('OPEN','RESUMING')""")}
        for actor_id, raw, waypoint, last_minute in rows:
            if last_minute >= minute:
                continue
            profile = json.loads(raw)
            # Stagger movements. A shop clerk works longer at each station.
            cadence = profile["cadence"]
            phase = int(actor_id.rsplit("_", 1)[1]) % cadence
            due = (minute // 10) % cadence == phase
            if actor_id not in busy and due:
                waypoint = (waypoint + 1) % 4
            conn.execute("""UPDATE city_residents SET waypoint=?,activity=?,last_minute=?
                WHERE actor_id=?""",
                (waypoint, profile["activities"][waypoint], minute, actor_id))


def public_residents(location: str) -> dict[str, dict]:
    # Read-only projection, restricted to co-location. Profiles never contain
    # autobiographical memories or private knowledge.
    with get_connection() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='city_residents'").fetchone():
            return {}
        rows = conn.execute("""SELECT r.actor_id,r.profile,r.waypoint,r.activity
            FROM city_residents r JOIN agents a ON a.id=r.actor_id
            WHERE a.location=? AND a.controller_type='RESIDENT'""", (location,)).fetchall()
    result = {}
    for actor_id, raw, waypoint, activity in rows:
        profile = json.loads(raw)
        result[actor_id] = {
            "role": profile["role"], "role_label": profile["role"],
            "skills": profile["skills"], "public_objective": profile["objective"],
            "activity": activity, "slot": profile["slot"], "patrol_step": waypoint,
            "appearance": profile["appearance"], "role_assignment": "CITY_PROVISIONAL",
        }
    return result


def resident_context(actor_id: str, location: str) -> dict | None:
    data = public_residents(location).get(actor_id)
    if data is None:
        return None
    return {key: data[key] for key in ("role", "skills", "public_objective", "activity")}


def apply_catalog_profiles() -> int:
    """Explicit authoring action, never performed by a read or normal restart."""
    items = load_catalog()
    changed = 0
    with get_connection() as conn:
        for item in items:
            row = conn.execute("""SELECT r.profile,r.waypoint FROM city_residents r
                JOIN agents a ON a.id=r.actor_id
                WHERE r.actor_id=? AND a.controller_type='RESIDENT'""", (item["id"],)).fetchone()
            if row is None:
                continue
            profile = json.loads(row[0])
            for key in ("name","role","objective","skills","activities","cadence","appearance"):
                profile[key] = item[key]
            conn.execute("UPDATE agents SET name=? WHERE id=?", (item["name"], item["id"]))
            conn.execute("UPDATE city_residents SET profile=?,activity=? WHERE actor_id=?",
                (json.dumps(profile, ensure_ascii=False), profile["activities"][row[1]], item["id"]))
            changed += 1
    return changed


if __name__ == "__main__":
    import argparse
    from . import database
    parser = argparse.ArgumentParser(description="Aplicar las fichas editadas con el servidor cerrado.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--apply-catalog", required=True, action="store_true")
    args = parser.parse_args()
    database.DB_PATH = Path(args.world).resolve(strict=True)
    print(f"Fichas actualizadas: {apply_catalog_profiles()}")
