from server.agents.agent_k import AgentK
from server.agents.nora import Nora

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
    Agent,
    NodeBelief,
    WorldNode,
)

from .perception import perceive_node


class Simulation:

    def __init__(self):

        self.world = WorldCore()

        # -------------------------
        # WORLD OBJECTS
        # -------------------------

        default_node = WorldNode(
            id="NODE_07",
            location="STATION",
            node_type="UNKNOWN_SIGNAL",
            discovered=False,
            active=True,
            anomaly_strength=0.60,
        )

        self.node = load_or_create_node(
            default_node
        )

        # -------------------------
        # AGENTS
        # -------------------------

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
            load_or_create_agent(
                k_default
            )
        )

        self.nora = Nora(
            load_or_create_agent(
                nora_default
            )
        )

        self.actors = [
            self.k,
            self.nora,
        ]

        # -------------------------
        # TIME
        # -------------------------

        self.minute = (
            load_simulation_minute()
        )

        # -------------------------
        # MIGRATION / BOOTSTRAP
        # -------------------------

        self.bootstrap_existing_knowledge()
        self.seed_initial_leads()

    # =====================================================
    # BOOTSTRAP
    # =====================================================

    def bootstrap_existing_knowledge(
        self,
    ):

        """
        Migra automáticamente las memorias
        producidas por nuestras versiones
        anteriores.

        Si un agente recuerda haber descubierto
        NODE_07, World Core considera que
        conoce la existencia de NODE_07.
        """

        for actor in self.actors:

            for memory in actor.agent.memory:

                if (
                    "Discovered anomalous node NODE_07"
                    in memory
                ):
                    learn_node(
                        agent_id=actor.agent.id,
                        node_id="NODE_07",
                        confidence=1.0,
                        source="EPISODIC_MEMORY",
                    )

    def seed_initial_leads(
        self,
    ):

        """
        Si empezáramos una base de datos limpia,
        los agentes necesitan una pista inicial
        que les permita buscar la estación.

        Esto NO es conocimiento verdadero.

        Es solamente un rumor/pista de baja
        confianza.
        """

        for actor in self.actors:

            existing = load_belief(
                actor.agent.id,
                self.node.id,
            )

            if existing is not None:
                continue

            lead = NodeBelief(
                agent_id=actor.agent.id,
                node_id=self.node.id,
                believed_location="STATION",
                believed_strength=0.50,
                confidence=0.35,
                source="ANONYMOUS_SIGNAL",
                updated_minute=self.minute,
            )

            save_belief(
                lead
            )

    # =====================================================
    # MEMORY
    # =====================================================

    def remember(
        self,
        agent: Agent,
        text: str,
    ):

        if text in agent.memory:
            return

        agent.memory.append(
            text
        )

        add_memory(
            agent.id,
            text,
        )

    # =====================================================
    # PERCEPTION
    # =====================================================

    def perception_phase(
        self,
    ):

        for actor in self.actors:

            perception = perceive_node(
                agent=actor.agent,
                node=self.node,
                minute=self.minute,
            )

            if perception is None:
                continue

            save_belief(
                perception
            )

            if not knows_node(
                actor.agent.id,
                self.node.id,
            ):

                learn_node(
                    agent_id=actor.agent.id,
                    node_id=self.node.id,
                    confidence=perception.confidence,
                    source="DIRECT_PERCEPTION",
                )

                self.node.discovered = True

                save_node(
                    self.node
                )

                memory = (
                    f"Discovered anomalous node "
                    f"{self.node.id} "
                    f"at {self.node.location}"
                )

                self.remember(
                    actor.agent,
                    memory,
                )

    # =====================================================
    # COGNITION
    # =====================================================

    def cognition_phase(
        self,
    ):

        intents = []

        for actor in self.actors:

            belief = load_belief(
                actor.agent.id,
                self.node.id,
            )

            decision = actor.decide(
                world=self.world.get_state(),
                belief=belief,
            )

            intents.append(
                (
                    actor,
                    decision,
                )
            )

        return intents

    # =====================================================
    # ACTION RESOLUTION
    # =====================================================

    def resolve_intents(
        self,
        intents,
    ):

        # Todos los agentes han pensado ya.
        #
        # Ahora sus acciones se resuelven
        # conjuntamente.

        node_delta = 0.0

        signal_delta = 0.0
        stability_delta = 0.0
        connection_delta = 0.0

        for actor, decision in intents:

            agent = actor.agent

            action = decision["action"]
            target = decision["target"]

            details = ""

            # -----------------------------------------
            # MOVE
            # -----------------------------------------

            if action == "MOVE":

                agent.location = target

                agent.energy = max(
                    0.0,
                    agent.energy - 0.05,
                )

                details = (
                    f"{agent.name} "
                    f"moved to {target}"
                )

            # -----------------------------------------
            # INVESTIGATE
            # -----------------------------------------

            elif action == "INVESTIGATE":

                investigation = NodeBelief(
                    agent_id=agent.id,
                    node_id=self.node.id,
                    believed_location=(
                        self.node.location
                    ),
                    believed_strength=(
                        self.node.anomaly_strength
                    ),
                    confidence=0.95,
                    source="ACTIVE_INVESTIGATION",
                    updated_minute=self.minute,
                )

                save_belief(
                    investigation
                )

                learn_node(
                    agent_id=agent.id,
                    node_id=self.node.id,
                    confidence=0.95,
                    source="ACTIVE_INVESTIGATION",
                )

                self.node.discovered = True

                save_node(
                    self.node
                )

                agent.energy = max(
                    0.0,
                    agent.energy - 0.10,
                )

                memory = (
                    f"Investigated anomalous "
                    f"node {self.node.id} "
                    f"at {self.node.location}"
                )

                self.remember(
                    agent,
                    memory,
                )

                details = memory

            # -----------------------------------------
            # PROTOCOL ACTION
            # -----------------------------------------

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
                    f"to stabilize "
                    f"{self.node.id}"
                )

            # -----------------------------------------
            # WIRED ACTION
            # -----------------------------------------

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
                    f"to amplify "
                    f"{self.node.id}"
                )

            # -----------------------------------------
            # OBSERVE NODE
            # -----------------------------------------

            elif action == "OBSERVE":

                agent.energy = max(
                    0.0,
                    agent.energy - 0.02,
                )

                details = (
                    f"{agent.name} observes "
                    f"{self.node.id}"
                )

            # -----------------------------------------
            # OBSERVE AREA
            # -----------------------------------------

            elif action == "OBSERVE_AREA":

                agent.energy = max(
                    0.0,
                    agent.energy - 0.01,
                )

                details = (
                    f"{agent.name} observes "
                    f"the area"
                )

            # -----------------------------------------
            # REST
            # -----------------------------------------

            elif action == "REST":

                agent.energy = min(
                    1.0,
                    agent.energy + 0.35,
                )

                details = (
                    f"{agent.name} rests"
                )

            # -----------------------------------------
            # PERSIST AGENT
            # -----------------------------------------

            save_agent(
                agent
            )

            # -----------------------------------------
            # EVENT LOG
            # -----------------------------------------

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

        # =================================================
        # APPLY SHARED NODE EFFECTS
        # =================================================

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

        # =================================================
        # APPLY WORLD EFFECTS
        # =================================================

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

    # =====================================================
    # TICK
    # =====================================================

    def tick(
        self,
    ):

        self.minute += 10

        save_simulation_minute(
            self.minute
        )

        # 1. Los actores perciben.

        self.perception_phase()

        # 2. Piensan utilizando sus creencias.

        intents = (
            self.cognition_phase()
        )

        # 3. Actúan simultáneamente.

        self.resolve_intents(
            intents
        )

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
        ticks: int = 10,
    ):

        for _ in range(ticks):
            self.tick()

        state = (
            self.world.get_state()
        )

        print()
        print(
            "----- WORLD STATE -----"
        )

        print(
            f"Minute:     "
            f"{self.minute}"
        )

        print(
            f"Signal:     "
            f"{state.signal:.3f}"
        )

        print(
            f"Stability:  "
            f"{state.stability:.3f}"
        )

        print(
            f"Connection: "
            f"{state.connection:.3f}"
        )

        print()

        print(
            "----- NODE REALITY -----"
        )

        print(
            f"Node:       "
            f"{self.node.id}"
        )

        print(
            f"Location:   "
            f"{self.node.location}"
        )

        print(
            f"Anomaly:    "
            f"{self.node.anomaly_strength:.2f}"
        )

        print()

        print(
            "----- AGENTS -----"
        )

        for actor in self.actors:

            agent = actor.agent

            belief = load_belief(
                agent.id,
                self.node.id,
            )

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

            if belief is None:

                print(
                    "Belief: NONE"
                )

            else:

                print(
                    f"Believes location: "
                    f"{belief.believed_location}"
                )

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

            print(
                "Memory:"
            )

            for memory in agent.memory:

                print(
                    f" - {memory}"
                )