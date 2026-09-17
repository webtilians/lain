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

    def remember(self, agent, text: str):
        agent.memory.append(text)
        add_memory(agent.id, text)

    def execute_action(self, actor, decision: dict):

        action = decision["action"]
        target = decision["target"]

        agent = actor.agent

        details = ""

        if action == "MOVE":

            agent.location = target
            save_agent(agent)

            details = f"{agent.name} moved to {target}"

        elif action == "INVESTIGATE":

            self.node.discovered = True
            save_node(self.node)

            memory = (
                f"Discovered anomalous node "
                f"{self.node.id} at {self.node.location}"
            )

            self.remember(agent, memory)
            details = memory

        elif action == "STABILIZE":

            self.node.anomaly_strength = max(
                0.0,
                self.node.anomaly_strength - 0.10,
            )

            save_node(self.node)

            self.world.apply_event(
                signal_delta=-0.01,
                stability_delta=0.02,
                connection_delta=-0.005,
            )

            memory = (
                f"Attempted to stabilize "
                f"{self.node.id}"
            )

            self.remember(agent, memory)

            details = (
                f"{self.node.id} anomaly now "
                f"{self.node.anomaly_strength:.2f}"
            )

        elif action == "AMPLIFY":

            self.node.anomaly_strength = min(
                1.0,
                self.node.anomaly_strength + 0.10,
            )

            save_node(self.node)

            self.world.apply_event(
                signal_delta=0.02,
                stability_delta=-0.015,
                connection_delta=0.015,
            )

            memory = (
                f"Amplified signal at "
                f"{self.node.id}"
            )

            self.remember(agent, memory)

            details = (
                f"{self.node.id} anomaly now "
                f"{self.node.anomaly_strength:.2f}"
            )

        else:

            details = (
                f"{agent.name} observes "
                f"{self.node.id}"
            )

        record_event(
            minute=self.minute,
            actor_id=agent.id,
            action=action,
            target=target,
            details=details,
        )

        print(
            f"[{self.minute:04}m] "
            f"{agent.name} {action} -> {target}"
        )

    def tick(self):

        self.minute += 10
        save_simulation_minute(self.minute)

        actors = [
            self.k,
            self.nora,
        ]

        for actor in actors:

            decision = actor.decide(
                world=self.world.get_state(),
                node=self.node,
            )

            self.execute_action(
                actor,
                decision,
            )

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
        print(f"Discovered: {self.node.discovered}")
        print(
            f"Anomaly:    "
            f"{self.node.anomaly_strength:.2f}"
        )

        print()
        print("----- AGENTS -----")

        for actor in [self.k, self.nora]:

            print()
            print(
                f"{actor.agent.name} "
                f"[{actor.agent.faction}]"
            )

            print(
                f"Location: "
                f"{actor.agent.location}"
            )

            print("Memory:")

            for memory in actor.agent.memory:
                print(f" - {memory}")