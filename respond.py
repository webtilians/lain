import sys

from server.world_core.interactions import (
    find_latest_open_for_recipient,
    queue_interaction_response,
)


PLAYER_ID = "PLAYER_1"


def usage():

    print(
        "Usage:"
    )

    print(
        "  python respond.py ADMIT"
    )

    print(
        "  python respond.py DENY"
    )

    print(
        "  python respond.py SILENCE"
    )

    print(
        "  python respond.py ACCUSE AGENT_NORA"
    )


if __name__ == "__main__":

    if len(sys.argv) < 2:

        usage()
        raise SystemExit(1)

    response_type = (
        sys.argv[1].upper()
    )

    subject_actor_id = None

    if response_type == "ACCUSE":

        if len(sys.argv) < 3:

            usage()
            raise SystemExit(1)

        subject_actor_id = (
            sys.argv[2]
        )

    interaction = (
        find_latest_open_for_recipient(
            PLAYER_ID
        )
    )

    if interaction is None:

        print(
            "No open interaction "
            "for PLAYER_1"
        )

        raise SystemExit(1)

    response_id = (
        queue_interaction_response(
            interaction_id=(
                interaction.id
            ),

            actor_id=PLAYER_ID,

            response_type=(
                response_type
            ),

            subject_actor_id=(
                subject_actor_id
            ),
        )
    )

    print(
        f"Queued response "
        f"{response_id}: "
        f"{response_type}"
    )

    if subject_actor_id:

        print(
            f"Subject: "
            f"{subject_actor_id}"
        )