import sys

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