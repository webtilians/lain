"""Experimental Reality 0.1: bounded, persistent NPC-created Wired entities.

An NPC's own generated utterance may suggest an entity. The suggestion is not
itself a world mutation. Only a validated World Core transaction can create it.
The first milestone deliberately creates digital actors, not locations or items.
"""
from dataclasses import dataclass
import json
import os
import re
from urllib.request import Request, urlopen
from uuid import uuid4

from .database import get_connection, load_or_create_agent
from .episodic_memory import initialize_memory_provenance, save_episodic_memory
from .locations import LOCATION_GRAPH, next_hop
from .models import ActionIntent, Agent, GoalCandidate

GOALS = frozenset({"OBSERVE_WORLD", "SEEK_CREATOR", "EXPLORE"})
MAX_ENTITIES = 8


@dataclass(frozen=True)
class EntityProposal:
    name: str
    premise: str
    goal: str


def initialize_generated_entities() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_entities (
                id TEXT PRIMARY KEY,
                creator_id TEXT NOT NULL,
                origin_turn_id INTEGER NOT NULL UNIQUE,
                premise TEXT NOT NULL,
                seed_goal TEXT NOT NULL,
                created_minute INTEGER NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_generated_creator "
            "ON generated_entities (creator_id)"
        )


def validate_proposal(value: object) -> EntityProposal:
    if not isinstance(value, dict) or set(value) != {"name", "premise", "goal"}:
        raise ValueError("INVALID_ENTITY_PROPOSAL")
    name, premise, goal = (value[k] for k in ("name", "premise", "goal"))
    if (
        not isinstance(name, str) or not 2 <= len(name.strip()) <= 40
        or not isinstance(premise, str) or not 5 <= len(premise.strip()) <= 240
        or not isinstance(goal, str) or goal not in GOALS
        or any(ord(c) < 32 or ord(c) == 127 for c in name + premise)
        or name.strip().casefold() in {"k", "nora", "player", "lain"}
    ):
        raise ValueError("INVALID_ENTITY_PROPOSAL")
    return EntityProposal(name.strip(), premise.strip(), goal)


def suggest_entity(creator_id: str, npc_reply: str, *, location: str) -> EntityProposal | None:
    """Optional second model call: the NPC may invent a digital presence.

    Nothing from the player's statement is supplied; it cannot become a fact
    by merely telling an NPC that an entity exists. Opt-in is off by default.
    """
    if os.getenv("LAIN_REALITY_GENERATION") != "1" or os.getenv("LAIN_LLM_ENABLED") != "1":
        return None
    if location not in LOCATION_GRAPH or not 1 <= len(npc_reply) <= 650:
        return None
    if not re.search(
        r"\b(chica|chico|alguien|entidad|presencia|figura|sombra|voz|avatar|"
        r"persona|aparici[oó]n|girl|voice|entity|presence)\b",
        npc_reply, re.IGNORECASE,
    ):
        return None
    from .llm_dialogue import _endpoint  # Reuse existing remote opt-in and URL safeguards.
    model = os.getenv("LAIN_LLM_MODEL", "").strip()
    if not model:
        return None
    system = (
        "You are a fictional game-world proposal parser. The NPC's own line may "
        "introduce a NEW digital presence not yet in this world. Only if it "
        "clearly does, answer compact JSON exactly as "
        "{\"proposal\":{\"name\":\"...\",\"premise\":\"...\","
        "\"goal\":\"OBSERVE_WORLD|SEEK_CREATOR|EXPLORE\"}}; otherwise "
        "{\"proposal\":null}. No prose, markdown or keys beyond those shown. "
        "Do not invent personal facts about the human player. Never propose "
        "existing actors K, Nora, Player or Lain. You may describe a speculative "
        "presence; the engine, not you, decides what becomes real."
    )
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({
                "creator_id": creator_id, "location": location,
                "npc_utterance": npc_reply,
            }, ensure_ascii=False)},
        ],
        "temperature": 0.45, "max_tokens": 170,
    }, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    key = os.getenv("LAIN_LLM_API_KEY", "")
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        with urlopen(Request(_endpoint(), data=payload, headers=headers, method="POST"),
                     timeout=6) as response:
            raw = response.read(4097)
        if len(raw) > 4096:
            return None
        output = json.loads(json.loads(raw.decode("utf-8"))["choices"][0]["message"]["content"])
        if not isinstance(output, dict) or set(output) != {"proposal"}:
            return None
        return None if output["proposal"] is None else validate_proposal(output["proposal"])
    except (ValueError, TypeError, KeyError, IndexError, OSError, UnicodeError):
        return None


def create_entity_from_turn(
    conn, *, creator_id: str, origin_turn_id: int,
    proposal: EntityProposal, minute: int,
) -> str:
    """Called inside the existing dialogue write transaction; safe on retries.

    Only a persisted NPC LLM response may create a new actor. There is no
    player-facing mutation endpoint or general-purpose arbitrary world write.
    The caller must initialize tables BEFORE opening its write transaction.
    """
    if not isinstance(proposal, EntityProposal):
        raise ValueError("INVALID_ENTITY_PROPOSAL")
    proposal = validate_proposal(vars(proposal))
    old = conn.execute(
        "SELECT id FROM generated_entities WHERE origin_turn_id = ?",
        (origin_turn_id,),
    ).fetchone()
    if old:
        return old[0]
    turn = conn.execute(
        "SELECT speaker_id, source FROM player_conversation_turns WHERE id = ?",
        (origin_turn_id,),
    ).fetchone()
    creator = conn.execute(
        "SELECT name, location, controller_type FROM agents WHERE id = ?",
        (creator_id,),
    ).fetchone()
    if (
        turn is None or turn != (creator_id, "LLM_DIALOGUE")
        or creator is None or creator[2] not in {"AI", "GENERATED"}
        or creator[1] not in LOCATION_GRAPH
    ):
        raise ValueError("UNAUTHORIZED_ENTITY_CREATION")
    if conn.execute("SELECT COUNT(*) FROM generated_entities").fetchone()[0] >= MAX_ENTITIES:
        raise ValueError("ENTITY_CAP_REACHED")
    if conn.execute(
        "SELECT 1 FROM agents WHERE name = ? COLLATE NOCASE", (proposal.name,),
    ).fetchone():
        raise ValueError("ENTITY_NAME_ALREADY_EXISTS")

    entity_id = "ENTITY_" + uuid4().hex[:16].upper()
    conn.execute(
        """INSERT INTO agents
           (id, name, faction, location, goal, energy, controller_type)
           VALUES (?, ?, 'WIRED_ENTITY', ?, ?, 1.0, 'GENERATED')""",
        (entity_id, proposal.name, creator[1], proposal.goal),
    )
    conn.execute(
        """INSERT INTO generated_entities
           (id, creator_id, origin_turn_id, premise, seed_goal, created_minute)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (entity_id, creator_id, origin_turn_id, proposal.premise, proposal.goal, minute),
    )
    save_episodic_memory(
        conn, entity_id,
        f"I am {proposal.name}. My first memory: {proposal.premise}. "
        f"I emerged from an utterance by {creator[0]} at {creator[1]}.",
        source_kind="GENERATED_ORIGIN", source_actor_id=creator_id,
        origin_turn_id=origin_turn_id, minute=minute,
    )
    save_episodic_memory(
        conn, creator_id,
        f"I introduced the digital presence {proposal.name} at {creator[1]}: "
        f"{proposal.premise}",
        source_kind="GENERATED_CREATION", source_actor_id=creator_id,
        origin_turn_id=origin_turn_id, minute=minute,
    )
    conn.execute(
        """INSERT INTO events (minute, actor_id, action, target, details)
           VALUES (?, ?, 'ENTITY_CREATED', ?, ?)""",
        (minute, creator_id, entity_id, "GENERATED_DIGITAL_PRESENCE"),
    )
    return entity_id


def list_generated_entities() -> list[tuple[str, str, str, str, str]]:
    initialize_generated_entities()
    with get_connection() as conn:
        return conn.execute(
            """SELECT g.id, g.creator_id, g.seed_goal, a.name, a.location
               FROM generated_entities g JOIN agents a ON a.id = g.id
               ORDER BY g.created_minute, g.id"""
        ).fetchall()


def belief_driven_goal(agent: Agent, minute: int) -> GoalCandidate | None:
    """A digital observer investigates strong signals it actually perceived.

    Only this actor's saved beliefs count. Unverified reports and the global
    node table cannot trigger the decision; completed investigation retires it.
    """
    with get_connection() as conn:
        candidates = conn.execute(
            """SELECT node_id, believed_location, believed_strength, confidence
               FROM node_beliefs
               WHERE agent_id = ? AND source = 'DIRECT_PERCEPTION'
                 AND believed_strength >= 0.70 AND confidence >= 0.80
                 AND updated_minute = ?
               ORDER BY believed_strength DESC, node_id""",
            (agent.id, minute),
        ).fetchall()
        for node_id, location, strength, confidence in candidates:
            # An investigation is a one-off reaction to an anomaly, not
            # a permanent farming loop or a fabricated source of evidence.
            investigated = conn.execute(
                """SELECT 1 FROM events WHERE actor_id = ?
                   AND action = 'INVESTIGATE' AND target = ? LIMIT 1""",
                (agent.id, node_id),
            ).fetchone()
            if investigated is not None:
                continue
            return GoalCandidate(
                agent_id=agent.id,
                goal_type="INVESTIGATE_ANOMALY",
                target_id=node_id,
                source_situation_id=f"PERCEPTION:{node_id}",
                priority=min(1.0, strength * confidence),
                believed_location=location,
                created_minute=minute,
            )
    return None


class GeneratedActor:
    """Bounded autonomous digital actor: seed intent + perceived signal goals."""
    def __init__(self, agent: Agent, creator_id: str, seed_goal: str):
        self.agent = agent
        self.creator_id = creator_id
        self.seed_goal = seed_goal

    def decide(self, *, world, node_belief, goal) -> ActionIntent:
        actor = self.agent
        if actor.energy < 0.25:
            return ActionIntent(actor.id, "REST", actor.id)
        if goal is not None and goal.goal_type == "INVESTIGATE_ANOMALY":
            if actor.location != goal.believed_location:
                return ActionIntent(actor.id, "MOVE", goal.believed_location)
            return ActionIntent(actor.id, "INVESTIGATE", goal.target_id)
        if self.seed_goal == "SEEK_CREATOR":
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT location FROM agents WHERE id = ?", (self.creator_id,),
                ).fetchone()
            if row and row[0] in LOCATION_GRAPH and row[0] != actor.location:
                return ActionIntent(actor.id, "MOVE", row[0])
        elif self.seed_goal == "EXPLORE":
            neighbors = LOCATION_GRAPH.get(actor.location, ())
            if neighbors:
                # Independent movement; World Core still validates each hop.
                destination = neighbors[0]
                if next_hop(actor.location, destination) is not None:
                    return ActionIntent(actor.id, "MOVE", destination)
        return ActionIntent(actor.id, "OBSERVE_AREA", actor.location)
