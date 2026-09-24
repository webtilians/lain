"""Reality 0.4: persistent, bounded roles and player-visible character sheets.

Identity, origin and memories remain in their existing authoritative tables.
Roles are provisional interpretations of the already persisted origin, never
new LLM-generated facts. Public cards expose no private memory, beliefs,
goals, creator IDs, or NPC positions outside the player's current location.
"""
from .database import get_connection
from .prologue import stage_for

# Label and observable inclination; NOT a claim about hidden psychology.
ROLE_RULES = {
    "ARCHIVIST": ("Archivista de la Wired", "Contrasta señales y registros.", 4),
    "SIGNAL_KEEPER": ("Vigilante de señal", "Permanece atento a las variaciones de NODE_07.", 3),
    "ORIGIN_SEEKER": ("Buscador de origen", "Explora vínculos con su aparición.", 2),
    "MONITOR": ("Observador de entidades", "Registra la conducta observable de otras presencias.", 5),
    "SCOUT": ("Explorador", "Recorre lugares buscando indicios propios.", 2),
    "INQUIRER": ("Investigador", "Contrasta testimonios antes de intervenir.", 4),
    "WITNESS": ("Testigo", "Presta atención al surgimiento de nuevas presencias.", 6),
    "OBSERVER": ("Observador", "Explora su entorno sin una especialidad definida.", 1),
}
ORIGIN_NAME_ROLES = {
    # Explicitly provisional starting points for the seven EXISTING identities.
    "the wired": "ARCHIVIST",
    "node 07": "SIGNAL_KEEPER",
    "new digital presence": "ORIGIN_SEEKER",
    "monitor entities": "MONITOR",
    "node 07 explorer": "SCOUT",
    "node 07 inquiry": "INQUIRER",
    "new entities observation": "WITNESS",
}
NPC_RULES = {
    "AGENT_K": ("Agente del Protocolo", "Investiga alteraciones de la red."),
    "AGENT_NORA": ("Habitante de la Wired", "Interpreta señales desde su propia experiencia."),
}


def infer_origin_role(name: str, premise: str, seed_goal: str) -> str:
    normalized = " ".join(name.casefold().split())
    if normalized in ORIGIN_NAME_ROLES:
        return ORIGIN_NAME_ROLES[normalized]
    description = premise.casefold()
    if "investig" in description or "pregunt" in description:
        return "INQUIRER"
    if "monitor" in description or "vigil" in description:
        return "MONITOR"
    if seed_goal == "EXPLORE":
        return "SCOUT"
    if seed_goal == "SEEK_CREATOR":
        return "ORIGIN_SEEKER"
    return "OBSERVER"


def initialize_profiles() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_actor_profiles (
                actor_id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                assignment TEXT NOT NULL,
                assigned_minute INTEGER NOT NULL
            )
        """)


def insert_origin_profile(conn, actor_id: str, name: str, premise: str,
                          seed_goal: str, minute: int) -> None:
    role = infer_origin_role(name, premise, seed_goal)
    conn.execute(
        """INSERT OR IGNORE INTO generated_actor_profiles
           (actor_id, role, assignment, assigned_minute)
           VALUES (?, ?, 'ORIGIN_PROVISIONAL', ?)""",
        (actor_id, role, minute),
    )


def synchronize_existing_profiles() -> None:
    """Add only missing sidecars for old entities; preserve ALL original rows."""
    initialize_profiles()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT g.id, a.name, g.premise, g.seed_goal, g.created_minute
               FROM generated_entities g JOIN agents a ON a.id=g.id"""
        ).fetchall()
        for actor_id, name, premise, seed_goal, minute in rows:
            insert_origin_profile(conn, actor_id, name, premise, seed_goal, minute)


def actor_role(actor_id: str) -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT role FROM generated_actor_profiles WHERE actor_id=?",
            (actor_id,),
        ).fetchone()
    return row[0] if row is not None and row[0] in ROLE_RULES else "OBSERVER"


def generated_role_context(actor_id: str) -> dict | None:
    """Private prompt context for THIS generated agent, not a player dossier."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT p.role FROM generated_actor_profiles p
               JOIN generated_entities g ON g.id=p.actor_id
               WHERE p.actor_id=?""",
            (actor_id,),
        ).fetchone()
    if row is None:
        return None
    role = row[0] if row[0] in ROLE_RULES else "OBSERVER"
    label, focus, _cadence = ROLE_RULES[role]
    return {
        "role": role, "label": label, "focus": focus,
        "assignment": "PROVISIONAL_FROM_ORIGIN",
    }


def role_step_due(actor_id: str, role: str, minute: int) -> bool:
    cadence = ROLE_RULES.get(role, ROLE_RULES["OBSERVER"])[2]
    phase = sum((i + 1) * ord(char) for i, char in enumerate(actor_id)) % cadence
    return (minute // 10) % cadence == phase


def player_sheet(player_row: tuple, known_nodes_count: int,
                 case_status: str) -> dict:
    return {
        "id": player_row[0], "name": player_row[1], "kind": "PLAYER",
        "faction": player_row[2], "location": player_row[3],
        "energy": round(player_row[5], 3),
        "known_nodes": known_nodes_count, "case_status": case_status,
        "agency": "HUMAN_ONLY",
    }


def visible_npc_sheets(player_id: str, location: str) -> list[dict]:
    from .residents import public_residents
    residents = public_residents(location)
    initialize_profiles()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.id, a.name, a.controller_type, p.role
               FROM agents a
               LEFT JOIN generated_actor_profiles p ON p.actor_id=a.id
               WHERE a.location=? AND a.id!=?
                 AND a.controller_type!='HUMAN'
               ORDER BY a.id""",
            (location, player_id),
        ).fetchall()
    result = []
    for actor_id, name, controller, stored_role in rows:
        if actor_id in residents:
            data = residents[actor_id]
            result.append({
                "id": actor_id, "name": name, "kind": "NPC",
                "observed_location": location, "focus": data["activity"],
                **{k: data[k] for k in ("role", "role_label", "skills",
                    "public_objective", "activity", "role_assignment")},
            })
            continue
        if controller == "GENERATED":
            role = stored_role if stored_role in ROLE_RULES else "OBSERVER"
            label, focus, _cadence = ROLE_RULES[role]
            assignment = "ORIGIN_PROVISIONAL"
        else:
            role = "PROTOCOL" if actor_id == "AGENT_K" else "WIRED"
            label, focus = NPC_RULES.get(
                actor_id, ("Habitante", "Su conducta aún no está determinada.")
            )
            assignment = "EXISTING_CHARACTER"
        result.append({
            "id": actor_id, "name": name, "kind": "NPC",
            "role": role, "role_label": label, "focus": focus,
            "role_assignment": assignment, "observed_location": location,
        })
    # Authored prologue characters are physical NPCs with a limited,
    # stage-based dialogue; they are not given fictional omniscient memories
    # or silently installed as autonomous GeneratedActors.
    stage = stage_for(player_id)
    authored = {
        "SCHOOL_LAB": {
            "id": "PROFESSOR", "name": "Profesor",
            "role": "TEACHER", "role_label": "Profesor de informática",
            "focus": "Recuerda a un antiguo alumno, no conoce su paradero actual.",
        },
        "NIGHTCLUB": {
            "id": "RYOKO", "name": "Ryoko",
            "role": "FORMER_STUDENT", "role_label": "Antiguo alumno",
            "focus": "Conoce el protocolo de acceso, pero no ha revelado la orden completa.",
        },
    }
    if stage in {"FIND_TEACHER", "FIND_RYOKO", "FIND_TERMINAL", "CONNECTED"}:
        actor = authored.get(location)
        if actor is not None:
            result.append({
                **actor, "kind": "NPC", "role_assignment": "AUTHORED_PROLOGUE",
                "observed_location": location,
            })
    return result
