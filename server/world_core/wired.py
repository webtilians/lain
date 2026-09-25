from .beliefs import (
    save_belief,
)

from .database import (
    record_event,
)

from .knowledge import (
    knows_node,
    learn_node,
)

from .messages import (
    INITIAL_MESSAGE_ID,
    acknowledge_message,
)
from .prologue import stage_for

from .models import (
    NodeBelief,
)


INITIAL_WIRED_NODE = "NODE_07"


def grant_initial_wired_lead(
    player_id: str,
    minute: int,
) -> bool:

    if knows_node(
        player_id,
        INITIAL_WIRED_NODE,
    ):
        return False

    learn_node(
        agent_id=player_id,
        node_id=INITIAL_WIRED_NODE,
        confidence=0.35,
        source="WIRED_MESSAGE",
    )

    save_belief(
        NodeBelief(
            agent_id=player_id,
            node_id=INITIAL_WIRED_NODE,
            believed_location="STATION",
            believed_strength=0.50,
            confidence=0.35,
            source="WIRED_MESSAGE",
            updated_minute=minute,
        )
    )

    record_event(
        minute=minute,
        actor_id=player_id,
        action="WIRED_LEAD_RECEIVED",
        target=INITIAL_WIRED_NODE,
        details=(
            "Anonymous Wired connection "
            "revealed a low-confidence signal lead"
        ),
    )

    return True


def process_wired_message_acknowledgement(
    message_id: str,
    player_id: str,
    minute: int,
) -> dict:

    # The legacy CONNECT button and direct API calls cannot bypass a new
    # game's authored discovery / terminal command. Existing saves have no
    # prologue row and continue to work exactly as before.
    if (
        message_id == INITIAL_MESSAGE_ID
        and stage_for(player_id) not in (None, "CONNECTED")
    ):
        raise ValueError("PROLOGUE_TERMINAL_REQUIRED")

    newly_acknowledged = acknowledge_message(
        message_id=message_id,
        player_id=player_id,
        minute=minute,
    )

    lead_granted = False

    if (
        newly_acknowledged
        and message_id == INITIAL_MESSAGE_ID
    ):
        lead_granted = grant_initial_wired_lead(
            player_id=player_id,
            minute=minute,
        )

    from .chapter_one import activate_chapter
    activate_chapter(player_id)
    from .network_conflict import enroll_connected_players
    enroll_connected_players()
    from .workshop import enroll_workshop
    enroll_workshop()

    return {
        "newly_acknowledged": newly_acknowledged,
        "lead_granted": lead_granted,
    }
