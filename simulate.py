from server.world_core.simulation import Simulation


if __name__ == "__main__":

    simulation = Simulation()

    simulation.run(
        ticks=10
    )