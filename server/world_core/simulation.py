from server.agents.agent_k import AgentK
from server.agents.nora import Nora

from .core import WorldCore
from .database import (
    add_memory,
    load_or_create_agent,
    load_or_create_node,
    load_simulation_minute,
    record_event,
    save_agent,
    save_node,
    save_simulation_minute,
)
from .knowledge import (
    knows_node,
    learn_node,
)
from .models import Agent, WorldNode


class Simulation:

    def __init__(self):

        self.world = WorldCore()

        default_node = WorldNode(
            id="NODE_07",
            location="STATION",
            node_type="UNKNOWN_SIGNAL",
            discovered=False,
            active=True,
            anomaly_strength=0.60,
        )

        self.node = load_or_create_node(default_node)

        k_default = Agent(
            id="AGENT_K",
            name="K",
            faction="PROTOCOL",
            location="APARTMENT_DISTRICT",
            goal="INVESTIGATE_ANOMALIES",
        )

        nora_default = Agent(
            id="AGENT_NORA",
            name="Nora",
            faction="WIRED",
            location="OLD_DISTRICT",
            goal="EXPAND_THE_WIRED",
        )

        self.k = AgentK(
            load_or_create_agent(k_default)
        )

        self.nora = Nora(
            load_or_create_agent(nora_default)
        )

        self.minute = load_simulation_minute()

        self.bootstrap_existing_knowledge()

    def bootstrap_existing_knowledge(self):

        for actor in [self.k, self.nora]:

            for memory in actor.agent.memory:

                if (
                    "Discovered anomalous node NODE_07"
                    in memory
                ):
                    learn_node(
                        actor.agent.id,
                        "NODE_07",
                        source="EPISODIC_MEMORY",
                    )

    def remember(self, agent, text: str):

        if text not in agent.memory:
            agent.memory.append(text)
            add_memory(agent.id, text)

    def resolve_intents(self, intents):

        node_delta = 0.0

        signal_delta = 0.0
        stability_delta = 0.0
        connection_delta = 0.0

        for actor, decision in intents:

            agent = actor.agent

            action = decision["action"]
            target = decision["target"]

            details = ""

            if action == "MOVE":

                agent.location = target
                agent.energy = max(
                    0.0,
                    agent.energy - 0.05,
                )

                details = (
                    f"{agent.name} moved to {target}"
                )

            elif action == "INVESTIGATE":

                learn_node(
                    agent.id,
                    self.node.id,
                )

                self.node.discovered = True

                agent.energy = max(
                    0.0,
                    agent.energy - 0.10,
                )

                memory = (
                    f"Discovered anomalous node "
                    f"{self.node.id} "
                    f"at {self.node.location}"
                )

                self.remember(agent, memory)

                details = memory

            elif action == "STABILIZE":

                node_delta -= 0.10

                signal_delta -= 0.01
                stability_delta += 0.02
                connection_delta -= 0.005

                agent.energy = max(
                    0.0,
                    agent.energy - 0.25,
                )

                details = (
                    f"{agent.name} attempted "
                    f"to stabilize {self.node.id}"
                )

            elif action == "AMPLIFY":

                node_delta += 0.10

                signal_delta += 0.02
                stability_delta -= 0.015
                connection_delta += 0.015

                agent.energy = max(
                    0.0,
                    agent.energy - 0.25,
                )

                details = (
                    f"{agent.name} attempted "
                    f"to amplify {self.node.id}"
                )

            elif action == "OBSERVE":

                agent.energy = max(
                    0.0,
                    agent.energy - 0.02,
                )

                details = (
                    f"{agent.name} observes "
                    f"{self.node.id}"
                )

            elif action == "REST":

                agent.energy = min(
                    1.0,
                    agent.energy + 0.35,
                )

                details = (
                    f"{agent.name} rests"
                )

            save_agent(agent)

            record_event(
                minute=self.minute,
                actor_id=agent.id,
                action=action,
                target=target,
                details=details,
            )

            print(
                f"[{self.minute:04}m] "
                f"{agent.name} "
                f"{action} -> {target}"
            )

        # Todos los efectos sobre el nodo
        # se aplican juntos.

        self.node.anomaly_strength = max(
            0.0,
            min(
                1.0,
                self.node.anomaly_strength
                + node_delta,
            ),
        )

        save_node(self.node)

        if (
            signal_delta != 0
            or stability_delta != 0
            or connection_delta != 0
        ):

            self.world.apply_event(
                signal_delta=signal_delta,
                stability_delta=stability_delta,
                connection_delta=connection_delta,
            )

    def tick(self):

        self.minute += 10
        save_simulation_minute(self.minute)

        intents = []

        for actor in [
            self.k,
            self.nora,
        ]:

            knowledge = knows_node(
                actor.agent.id,
                self.node.id,
            )

            decision = actor.decide(
                world=self.world.get_state(),
                node=self.node,
                knows_node=knowledge,
            )

            intents.append(
                (actor, decision)
            )

        self.resolve_intents(intents)

    def run(self, ticks: int = 10):

        for _ in range(ticks):
            self.tick()

        state = self.world.get_state()

        print()
        print("----- WORLD STATE -----")

        print(f"Minute:     {self.minute}")
        print(f"Signal:     {state.signal:.3f}")
        print(f"Stability:  {state.stability:.3f}")
        print(f"Connection: {state.connection:.3f}")

        print()

        print("----- NODE -----")

        print(f"Node:       {self.node.id}")

        print(
            f"Anomaly:    "
            f"{self.node.anomaly_strength:.2f}"
        )

        print()

        print("----- AGENTS -----")

        for actor in [
            self.k,
            self.nora,
        ]:

            agent = actor.agent

            print()
            print(
                f"{agent.name} "
                f"[{agent.faction}]"
            )

            print(
                f"Location: "
                f"{agent.location}"
            )

            print(
                f"Energy: "
                f"{agent.energy:.2f}"
            )

            print(
                f"Knows NODE_07: "
                f"{knows_node(agent.id, self.node.id)}"
            )

            print("Memory:")

            for memory in agent.memory:
                print(f" - {memory}")