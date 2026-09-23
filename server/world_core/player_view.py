from .database import (
    get_connection,
    load_simulation_minute,
)

from .beliefs import (
    initialize_beliefs,
)

from .interactions import (
    find_latest_open_for_recipient,
    find_latest_open_for_initiator,
)

from .locations import (
    LOCATION_GRAPH,
)
from .generated_entities import list_generated_entities
from .character_sheets import player_sheet, visible_npc_sheets
from .station_echo import station_case_snapshot
from .prologue import prologue_projection

from .messages import (
    list_player_messages,
)

from .knowledge import (
    initialize_knowledge,
)

from .situation_beliefs import (
    list_agent_situation_beliefs,
)


PLAYER_ID = "PLAYER_1"


def build_wired_projection(
    known_nodes: list[dict],
    messages: list,
):

    connected = any(
        message.acknowledged
        for message in messages
        if message.id == "MSG_BOOTSTRAP_001"
    )

    signals = []

    if connected:

        for node in known_nodes:

            belief = node.get(
                "belief"
            )

            if belief is None:
                continue

            if node.get(
                "knowledge_source"
            ) != "WIRED_MESSAGE":
                continue

            current_source = belief.get(
                "source",
                "UNKNOWN",
            )

            signals.append(
                {
                    "node_id": node["id"],
                    "location": belief["location"],
                    "strength": belief["strength"],
                    "confidence": belief["confidence"],
                    "origin_source": node[
                        "knowledge_source"
                    ],
                    "current_source": current_source,
                    "verified": (
                        current_source
                        == "DIRECT_PERCEPTION"
                    ),
                    "updated_minute": belief[
                        "updated_minute"
                    ],
                }
            )

    # Digital presences broadcast only their identity to connected players.
    # The Wired projection does not disclose private memories, creator
    # identities, current goals or the authoritative locations of NPCs.
    digital_presences = (
        [{"id": entity_id, "name": name}
         for entity_id, _creator, _goal, name, _location
         in list_generated_entities()]
        if connected else []
    )
    return {
        "connected": connected,
        "signals": signals,
        "digital_presences": digital_presences,
    }


def load_player_row(
    player_id: str = PLAYER_ID,
):

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT
                id,
                name,
                faction,
                location,
                goal,
                energy

            FROM agents

            WHERE id = ?
            """,
            (player_id,),
        ).fetchone()

    if row is None:

        raise ValueError(
            f"Unknown player: {player_id}"
        )

    return row


def list_player_known_nodes(
    player_id: str = PLAYER_ID,
):

    initialize_knowledge()
    initialize_beliefs()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                k.node_id,
                k.confidence,
                k.source,
                b.believed_location,
                b.believed_strength,
                b.confidence,
                b.source,
                b.updated_minute

            FROM agent_knowledge k

            LEFT JOIN node_beliefs b
              ON b.agent_id = k.agent_id
             AND b.node_id = k.node_id

            WHERE k.agent_id = ?

            ORDER BY k.node_id
            """,
            (player_id,),
        ).fetchall()

    result = []

    for row in rows:

        result.append(
            {
                "id": row[0],
                "knowledge_confidence": row[1],
                "knowledge_source": row[2],
                "belief": (
                    None
                    if row[3] is None
                    else {
                        "location": row[3],
                        "strength": row[4],
                        "confidence": row[5],
                        "source": row[6],
                        "updated_minute": row[7],
                    }
                ),
            }
        )

    return result


def list_player_situations(
    player_id: str = PLAYER_ID,
):

    beliefs = list_agent_situation_beliefs(
        player_id
    )

    return [
        {
            "id": belief.situation_id,
            "type": belief.believed_type,
            "location": belief.believed_location,
            "subject_id": belief.believed_subject_id,
            "status": belief.believed_status,
            "severity": belief.believed_severity,
            "confidence": belief.confidence,
            "source": belief.source,
            "updated_minute": belief.updated_minute,
        }
        for belief in beliefs
    ]


def list_visible_actors(
    player_id: str,
    player_location: str,
) -> list[dict]:
    """
    Proyección provisional de personajes presentes
    en la misma localización semántica que el jugador.

    No expone ubicaciones de otros agentes,
    sus objetivos, sus recuerdos ni sus creencias.
    """

    # A legacy save may not yet contain the optional physical-motion table.
    from .generated_entities import initialize_generated_entities
    initialize_generated_entities()
    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT a.id, a.name,
                   CASE WHEN a.controller_type = 'GENERATED'
                        THEN COALESCE(m.waypoint, 0) ELSE 0 END,
                   a.controller_type
            FROM agents a
            LEFT JOIN generated_actor_motion m ON m.actor_id = a.id
            WHERE a.location = ?
              AND a.id != ?
              AND a.controller_type != 'HUMAN'
            ORDER BY a.id
            """,
            (
                player_location,
                player_id,
            ),
        ).fetchall()

    return [
        {
            "id": row[0],
            "name": row[1],
            **({"patrol_step": row[2]}
               if row[3] == "GENERATED" and row[2] != 0 else {}),
        }
        for row in rows
    ]


def build_player_snapshot(
    player_id: str = PLAYER_ID,
):

    row = load_player_row(
        player_id
    )

    location = row[3]

    reachable_locations = sorted(
        LOCATION_GRAPH.get(
            location,
            (),
        )
    )

    interaction = find_latest_open_for_recipient(
        player_id
    )

    interaction_payload = None

    if interaction is not None:

        interaction_payload = {
            "id": interaction.id,
            "type": interaction.interaction_type,
            "initiator_id": interaction.initiator_id,
            "topic": interaction.topic,
            "status": interaction.status,
            "created_minute": interaction.created_minute,
        }

    outgoing_interaction = (
        find_latest_open_for_initiator(
            player_id
        )
    )

    outgoing_payload = None

    if outgoing_interaction is not None:

        outgoing_payload = {
            "id": outgoing_interaction.id,
            "type": outgoing_interaction.interaction_type,
            "initiator_id": outgoing_interaction.initiator_id,
            "recipient_id": outgoing_interaction.recipient_id,
            "topic": outgoing_interaction.topic,
            "status": outgoing_interaction.status,
            "created_minute": outgoing_interaction.created_minute,
        }

    messages = list_player_messages(
        player_id=player_id,
        current_minute=load_simulation_minute(),
    )

    known_nodes = list_player_known_nodes(
        player_id
    )
    station_case = station_case_snapshot(player_id)
    prologue = prologue_projection(player_id)
    if prologue["enabled"] and prologue["stage"] != "CONNECTED":
        reachable_locations = [
            place for place in reachable_locations
            if place not in {"STATION", "OLD_DISTRICT"}
        ]
        # The opening letter belongs to the WIRED side of the story.
        # Keep its existing database row untouched, reveal it only AFTER
        # the player has discovered the real terminal syntax and connected.
        messages = []

    return {
        "schema_version": "0.1",
        "minute": load_simulation_minute(),
        "player": {
            "id": row[0],
            "name": row[1],
            "faction": row[2],
            "location": location,
            "goal": row[4],
            "energy": row[5],
        },
        "navigation": {
            "reachable_locations": reachable_locations,
        },
        "known_nodes": known_nodes,
        "visible_actors": list_visible_actors(
            player_id=player_id,
            player_location=location,
        ),
        "character_sheets": {
            "player": player_sheet(row, len(known_nodes), station_case["status"]),
            "visible_npcs": visible_npc_sheets(player_id, location),
        },
        "station_case": station_case,
        "prologue": prologue,
        "situations": list_player_situations(
            player_id
        ),
        "interaction": interaction_payload,
        "outgoing_interaction": outgoing_payload,
        "messages": [
            {
                "id": message.id,
                "sender": message.sender_label,
                "subject": message.subject,
                "body": message.body,
                "created_minute": message.created_minute,
                "read": message.read,
                "acknowledged": message.acknowledged,
                "acknowledged_minute": message.acknowledged_minute,
            }
            for message in messages
        ],
        "unread_messages": sum(
            1
            for message in messages
            if not message.read
        ),
        "wired": build_wired_projection(
            known_nodes=known_nodes,
            messages=messages,
        ),
    }
