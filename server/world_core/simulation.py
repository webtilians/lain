from server.agents.agent_k import AgentK
from server.agents.nora import Nora

from .action_queue import (
    load_pending_actions,
    mark_action_processed,
)

from .beliefs import (
    load_belief,
    save_belief,
)

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

from .models import (
    ActionIntent,
    Agent,
    NodeBelief,
    WorldNode,
)

from .perception import perceive_node


class Simulation:

    def __init__(self):

        self.world = WorldCore()

        self.node = load_or_create_node(
            WorldNode(
                id="NODE_07",
                location="STATION",
                node_type="UNKNOWN_SIGNAL",
                discovered=False,
                active=True,
                anomaly_strength=0.60,
            )
        )

        self.k = AgentK(
            load_or_create_agent(
                Agent(
                    id="AGENT_K",
                    name="K",
                    faction="PROTOCOL",
                    location="APARTMENT_DISTRICT",
                    goal="INVESTIGATE_ANOMALIES",
                    controller_type="AI",
                )
            )
        )

        self.nora = Nora(
            load_or_create_agent(
                Agent(
                    id="AGENT_NORA",
                    name="Nora",
                    faction="WIRED",
                    location="OLD_DISTRICT",
                    goal="EXPAND_THE_WIRED",
                    controller_type="AI",
                )
            )
        )

        self.player = load_or_create_agent(
            Agent(
                id="PLAYER_1",
                name="Player",
                faction="UNALIGNED",
                location="APARTMENT",
                goal="UNKNOWN",
                controller_type="HUMAN",
            )
        )

        self.ai_actors = [
            self.k,
            self.nora,
        ]

        self.all_agents = {
            self.k.agent.id: self.k.agent,
            self.nora.agent.id: self.nora.agent,
            self.player.id: self.player,
        }

        self.minute = (
            load_simulation_minute()
        )

        self.bootstrap_existing_knowledge()
        self.seed_initial_leads()

    # ==================================================
    # BOOTSTRAP
    # ==================================================

    def bootstrap_existing_knowledge(self):

        for agent in self.all_agents.values():

            for memory in agent.memory:

                if (
                    "Discovered anomalous node NODE_07"
                    in memory
                ):

                    learn_node(
                        agent_id=agent.id,
                        node_id="NODE_07",
                        confidence=1.0,
                        source="EPISODIC_MEMORY",
                    )

    def seed_initial_leads(self):

        # Solo los agentes IA reciben por ahora
        # el rumor inicial.

        for actor in self.ai_actors:

            agent = actor.agent

            existing = load_belief(
                agent.id,
                self.node.id,
            )

            if existing is not None:
                continue

            save_belief(
                NodeBelief(
                    agent_id=agent.id,
                    node_id=self.node.id,
                    believed_location="STATION",
                    believed_strength=0.50,
                    confidence=0.35,
                    source="ANONYMOUS_SIGNAL",
                    updated_minute=self.minute,
                )
            )

    # ==================================================
    # MEMORY
    # ==================================================

    def remember(
        self,
        agent: Agent,
        text: str,
    ):

        if text in agent.memory:
            return

        agent.memory.append(text)

        add_memory(
            agent.id,
            text,
        )

    # ==================================================
    # PERCEPTION
    # ==================================================

    def perception_phase(self):

        for agent in self.all_agents.values():

            perception = perceive_node(
                agent=agent,
                node=self.node,
                minute=self.minute,
            )

            if perception is None:
                continue

            save_belief(
                perception
            )

            if not knows_node(
                agent.id,
                self.node.id,
            ):

                learn_node(
                    agent_id=agent.id,
                    node_id=self.node.id,
                    confidence=perception.confidence,
                    source="DIRECT_PERCEPTION",
                )

                self.node.discovered = True
                save_node(self.node)

                self.remember(
                    agent,
                    (
                        f"Discovered anomalous node "
                        f"{self.node.id} "
                        f"at {self.node.location}"
                    ),
                )

    # ==================================================
    # COGNITION
    # ==================================================

    def cognition_phase(self):

        intents = []

        # IA

        for actor in self.ai_actors:

            belief = load_belief(
                actor.agent.id,
                self.node.id,
            )

            intents.append(
                (
                    None,
                    actor.decide(
                        world=self.world.get_state(),
                        belief=belief,
                    ),
                )
            )

        # Humanos.
        # En el futuro estas acciones llegarán
        # desde Godot por WebSocket/API.

        for action_id, intent in load_pending_actions():

            intents.append(
                (
                    action_id,
                    intent,
                )
            )

        return intents

    # ==================================================
    # VALIDATION
    # ==================================================

    def validate_intent(
        self,
        agent: Agent,
        intent: ActionIntent,
    ) -> tuple[bool, str]:

        action = intent.action

        if action == "REST":
            return True, ""

        costs = {
            "MOVE": 0.05,
            "INVESTIGATE": 0.10,
            "STABILIZE": 0.25,
            "AMPLIFY": 0.25,
            "OBSERVE": 0.02,
            "OBSERVE_AREA": 0.01,
        }

        required_energy = costs.get(
            action,
            0.0,
        )

        if agent.energy < required_energy:
            return False, "NOT_ENOUGH_ENERGY"

        if action == "MOVE":
            return True, ""

        if action == "OBSERVE_AREA":
            return True, ""

        node_actions = {
            "INVESTIGATE",
            "STABILIZE",
            "AMPLIFY",
            "OBSERVE",
        }

        if action in node_actions:

            if intent.target != self.node.id:
                return False, "UNKNOWN_TARGET"

            if agent.location != self.node.location:
                return False, "TARGET_NOT_PRESENT"

        if action in {
            "STABILIZE",
            "AMPLIFY",
        }:

            if not knows_node(
                agent.id,
                self.node.id,
            ):
                return False, "NODE_NOT_KNOWN"

        return True, ""

    # ==================================================
    # ACTION RESOLUTION
    # ==================================================

    def resolve_intents(
        self,
        queued_intents,
    ):

        node_delta = 0.0

        signal_delta = 0.0
        stability_delta = 0.0
        connection_delta = 0.0

        for action_id, intent in queued_intents:

            agent = self.all_agents.get(
                intent.actor_id
            )

            if agent is None:

                if action_id is not None:
                    mark_action_processed(
                        action_id
                    )

                continue

            allowed, reason = (
                self.validate_intent(
                    agent,
                    intent,
                )
            )

            if not allowed:

                print(
                    f"[{self.minute:04}m] "
                    f"{agent.name} "
                    f"DENIED {intent.action} "
                    f"({reason})"
                )

                record_event(
                    minute=self.minute,
                    actor_id=agent.id,
                    action=f"DENIED_{intent.action}",
                    target=intent.target,
                    details=reason,
                )

                if action_id is not None:
                    mark_action_processed(
                        action_id
                    )

                continue

            action = intent.action
            target = intent.target

            details = ""

            # MOVE

            if action == "MOVE":

                agent.location = target

                agent.energy = max(
                    0.0,
                    agent.energy - 0.05,
                )

                details = (
                    f"{agent.name} moved "
                    f"to {target}"
                )

            # INVESTIGATE

            elif action == "INVESTIGATE":

                belief = NodeBelief(
                    agent_id=agent.id,
                    node_id=self.node.id,
                    believed_location=self.node.location,
                    believed_strength=self.node.anomaly_strength,
                    confidence=0.95,
                    source="ACTIVE_INVESTIGATION",
                    updated_minute=self.minute,
                )

                save_belief(belief)

                learn_node(
                    agent_id=agent.id,
                    node_id=self.node.id,
                    confidence=0.95,
                    source="ACTIVE_INVESTIGATION",
                )

                self.node.discovered = True

                agent.energy = max(
                    0.0,
                    agent.energy - 0.10,
                )

                self.remember(
                    agent,
                    (
                        f"Investigated anomalous "
                        f"node {self.node.id} "
                        f"at {self.node.location}"
                    ),
                )

                details = (
                    f"{agent.name} investigated "
                    f"{self.node.id}"
                )

            # STABILIZE

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

            # AMPLIFY

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

            # OBSERVE

            elif action == "OBSERVE":

                agent.energy = max(
                    0.0,
                    agent.energy - 0.02,
                )

                details = (
                    f"{agent.name} observes "
                    f"{self.node.id}"
                )

            # OBSERVE AREA

            elif action == "OBSERVE_AREA":

                agent.energy = max(
                    0.0,
                    agent.energy - 0.01,
                )

                details = (
                    f"{agent.name} observes area"
                )

            # REST

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

            if action_id is not None:
                mark_action_processed(
                    action_id
                )

        # Todos los efectos simultáneos
        # se aplican después.

        self.node.anomaly_strength = max(
            0.0,
            min(
                1.0,
                self.node.anomaly_strength
                + node_delta,
            ),
        )

        save_node(
            self.node
        )

        if (
            signal_delta != 0.0
            or stability_delta != 0.0
            or connection_delta != 0.0
        ):

            self.world.apply_event(
                signal_delta=signal_delta,
                stability_delta=stability_delta,
                connection_delta=connection_delta,
            )

    # ==================================================
    # TICK
    # ==================================================

    def tick(self):

        self.minute += 10

        save_simulation_minute(
            self.minute
        )

        self.perception_phase()

        intents = (
            self.cognition_phase()
        )

        self.resolve_intents(
            intents
        )

    # ==================================================
    # OUTPUT
    # ==================================================

    def run(
        self,
        ticks: int = 10,
    ):

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
        print("----- NODE REALITY -----")
        print(f"Node:       {self.node.id}")
        print(f"Location:   {self.node.location}")
        print(
            f"Anomaly:    "
            f"{self.node.anomaly_strength:.2f}"
        )

        print()
        print("----- ACTORS -----")

        for agent in self.all_agents.values():

            print()
            print(
                f"{agent.name} "
                f"[{agent.controller_type}] "
                f"[{agent.faction}]"
            )

            print(
                f"Location: {agent.location}"
            )

            print(
                f"Energy:   {agent.energy:.2f}"
            )

            belief = load_belief(
                agent.id,
                self.node.id,
            )

            if belief is None:

                print(
                    "NODE_07 belief: NONE"
                )

            else:

                print(
                    f"Believes anomaly: "
                    f"{belief.believed_strength:.2f}"
                )

                print(
                    f"Confidence: "
                    f"{belief.confidence:.2f}"
                )

                print(
                    f"Source: "
                    f"{belief.source}"
                )