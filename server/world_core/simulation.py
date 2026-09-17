from server.agents.agent_k import AgentK

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

        default_agent = Agent(
            id="AGENT_K",
            name="K",
            faction="PROTOCOL",
            location="APARTMENT_DISTRICT",
            goal="INVESTIGATE_ANOMALIES",
        )

        self.node = load_or_create_node(default_node)

        persisted_agent = load_or_create_agent(default_agent)

        self.k = AgentK(persisted_agent)

        self.minute = load_simulation_minute()

    def remember(self, text: str):
        self.k.agent.memory.append(text)
        add_memory(self.k.agent.id, text)

    def execute_action(self, decision: dict):

        action = decision["action"]
        target = decision["target"]

        if action == "MOVE":

            self.k.agent.location = target
            save_agent(self.k.agent)

            details = f"K moved to {target}"

        elif action == "INVESTIGATE":

            self.node.discovered = True
            save_node(self.node)

            memory = (
                f"Discovered anomalous node "
                f"{self.node.id} at {self.node.location}"
            )

            self.remember(memory)

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

            self.remember(memory)

            details = (
                f"{self.node.id} anomaly now "
                f"{self.node.anomaly_strength:.2f}"
            )

        else:

            details = f"K observes {self.node.id}"

        record_event(
            minute=self.minute,
            actor_id=self.k.agent.id,
            action=action,
            target=target,
            details=details,
        )

        print(
            f"[{self.minute:04}m] "
            f"K {action} -> {target}"
        )

    def tick(self):

        self.minute += 10
        save_simulation_minute(self.minute)

        decision = self.k.decide(
            world=self.world.get_state(),
            node=self.node,
        )

        self.execute_action(decision)

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
        print("----- AGENT K -----")
        print(f"Location: {self.k.agent.location}")

        print("Memory:")

        for memory in self.k.agent.memory:
            print(f" - {memory}")