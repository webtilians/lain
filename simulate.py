import sys

from server.situations.engine import (
    evaluate_world,
    list_open_situations,
)

from server.world_core.simulation import (
    Simulation,
)


if __name__ == "__main__":

    ticks = 10

    if len(sys.argv) > 1:
        ticks = int(
            sys.argv[1]
        )

    simulation = Simulation()

    simulation.run(
        ticks=ticks
    )

    evaluate_world(
        world=simulation.world.get_state(),
        node=simulation.node,
        minute=simulation.minute,
    )

    situations = (
        list_open_situations()
    )

    print()
    print(
        "----- OPEN SITUATIONS -----"
    )

    if not situations:

        print(
            "None"
        )

    for situation in situations:

        print()
        print(
            f"{situation.id}"
        )

        print(
            f"Type:     "
            f"{situation.situation_type}"
        )

        print(
            f"Location: "
            f"{situation.location}"
        )

        print(
            f"Subject:  "
            f"{situation.subject_id}"
        )

        print(
            f"Severity: "
            f"{situation.severity:.2f}"
        )

        print(
            f"Reason:   "
            f"{situation.reason}"
        )