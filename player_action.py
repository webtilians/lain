import sys

from server.world_core.action_queue import (
    queue_action,
)

from server.world_core.database import (
    load_or_create_agent,
)

from server.world_core.models import Agent


PLAYER_ID = "PLAYER_1"


def ensure_player():
    return load_or_create_agent(
        Agent(
            id=PLAYER_ID,
            name="Player",
            faction="UNALIGNED",
            location="APARTMENT",
            goal="UNKNOWN",
            controller_type="HUMAN",
        )
    )


if __name__ == "__main__":

    ensure_player()

    if len(sys.argv) != 3:

        print(
            "Usage:"
        )

        print(
            "python player_action.py "
            "ACTION TARGET"
        )

        print()

        print(
            "Example:"
        )

        print(
            "python player_action.py "
            "MOVE STATION"
        )

        raise SystemExit(1)

    action = sys.argv[1].upper()
    target = sys.argv[2]

    action_id = queue_action(
        actor_id=PLAYER_ID,
        action=action,
        target=target,
        source="HUMAN",
    )

    print(
        f"Queued action #{action_id}: "
        f"{PLAYER_ID} {action} {target}"
    )