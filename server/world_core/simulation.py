from server.agents.agent_k import AgentK
from server.agents.nora import Nora
from .dialogue import (
    process_dialogue_responses,
)

from .interactions import (
    create_or_get_interaction,
    find_open_interaction,
    list_open_interactions,
)
from server.situations.engine import (
    evaluate_world,
    list_open_situations,
    list_situations,
)

from .action_queue import (
    load_pending_actions,
    mark_action_processed,
)

from .actor_locations import (
    list_actor_location_beliefs,
    update_actor_location_intelligence,
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

from .evidence import (
    discover_unauthorized_manipulation_evidence,
    list_actor_beliefs,
)

from .goal_engine import (
    select_goal,
)

from .interactions import (
    create_or_get_interaction,
    list_open_interactions,
    find_open_interaction,
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

from .perception import (
    perceive_node,
)

from .situation_beliefs import (
    decay_situation_beliefs,
    list_agent_situation_beliefs,
    save_situation_belief,
)

from .situation_perception import (
    perceive_situation,
)


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
                    goal="IDLE",
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
                    goal="IDLE",
                    controller_type="AI",
                )
            )
        )

        self.player = (
            load_or_create_agent(
                Agent(
                    id="PLAYER_1",
                    name="Player",
                    faction="UNALIGNED",
                    location="APARTMENT",
                    goal="UNKNOWN",
                    controller_type="HUMAN",
                )
            )
        )

        self.ai_actors = [
            self.k,
            self.nora,
        ]

        self.all_agents = {
            self.k.agent.id:
                self.k.agent,

            self.nora.agent.id:
                self.nora.agent,

            self.player.id:
                self.player,
        }

        self.minute = (
            load_simulation_minute()
        )

        self.current_goals = {}

        self.bootstrap_existing_knowledge()
        self.seed_initial_leads()

    # ==================================================
    # BOOTSTRAP
    # ==================================================

    def bootstrap_existing_knowledge(
        self,
    ):

        for agent in (
            self.all_agents.values()
        ):

            for memory in agent.memory:

                if (
                    "Discovered anomalous "
                    "node NODE_07"
                    in memory
                ):

                    learn_node(
                        agent_id=agent.id,
                        node_id="NODE_07",
                        confidence=1.0,
                        source="EPISODIC_MEMORY",
                    )

    def seed_initial_leads(
        self,
    ):

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

                    believed_location=(
                        "STATION"
                    ),

                    believed_strength=0.50,
                    confidence=0.35,

                    source=(
                        "ANONYMOUS_SIGNAL"
                    ),

                    updated_minute=(
                        self.minute
                    ),
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

        agent.memory.append(
            text
        )

        add_memory(
            agent.id,
            text,
        )

    # ==================================================
    # NODE PERCEPTION
    # ==================================================

    def node_perception_phase(
        self,
    ):

        for agent in (
            self.all_agents.values()
        ):

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

                    confidence=(
                        perception.confidence
                    ),

                    source=(
                        "DIRECT_PERCEPTION"
                    ),
                )

                self.node.discovered = True

                save_node(
                    self.node
                )

                self.remember(
                    agent,
                    (
                        "Discovered anomalous "
                        f"node {self.node.id} "
                        f"at {self.node.location}"
                    ),
                )

    # ==================================================
    # SITUATION PERCEPTION
    # ==================================================

    def situation_perception_phase(
        self,
    ):

        situations = (
            list_situations()
        )

        for agent in (
            self.all_agents.values()
        ):

            decay_situation_beliefs(
                agent_id=agent.id,
                current_minute=self.minute,
            )

            for situation in situations:

                belief = perceive_situation(
                    agent=agent,
                    situation=situation,
                    minute=self.minute,
                )

                if belief is None:
                    continue

                save_situation_belief(
                    belief
                )

    # ==================================================
    # ACTOR INTELLIGENCE
    # ==================================================

    def actor_intelligence_phase(
        self,
    ):

        for actor in self.ai_actors:

            agent = actor.agent

            actor_beliefs = (
                list_actor_beliefs(
                    agent.id
                )
            )

            update_actor_location_intelligence(
                observer=agent,
                actor_beliefs=actor_beliefs,
                current_minute=self.minute,
            )

    # ==================================================
    # GOAL SELECTION
    # ==================================================

    def goal_selection_phase(
        self,
    ):

        self.current_goals = {}

        for actor in self.ai_actors:

            agent = actor.agent

            situation_beliefs = (
                list_agent_situation_beliefs(
                    agent.id
                )
            )

            actor_beliefs = (
                list_actor_beliefs(
                    agent.id
                )
            )

            location_beliefs = (
                list_actor_location_beliefs(
                    agent.id
                )
            )

            goal = select_goal(
                agent=agent,

                situation_beliefs=(
                    situation_beliefs
                ),

                actor_beliefs=(
                    actor_beliefs
                ),

                actor_location_beliefs=(
                    location_beliefs
                ),

                minute=self.minute,
            )

            self.current_goals[
                agent.id
            ] = goal

            if goal is None:
                agent.goal = "IDLE"

            else:
                agent.goal = (
                    goal.goal_type
                )

            save_agent(
                agent
            )

    # ==================================================
    # COGNITION
    # ==================================================

    def cognition_phase(
        self,
    ):

        intents = []

        for actor in self.ai_actors:

            agent = actor.agent

            node_belief = load_belief(
                agent.id,
                self.node.id,
            )

            goal = (
                self.current_goals.get(
                    agent.id
                )
            )

            open_interaction = False

            if (
                goal is not None
                and
                goal.goal_type
                == "CONTACT_SUSPECT"
            ):

                open_interaction = (
                    find_open_interaction(
                        initiator_id=agent.id,
                        recipient_id=goal.target_id,
                        topic=(
                            "UNAUTHORIZED_SIGNAL_"
                            "MANIPULATION"
                        ),
                    )
                    is not None
                )

            if actor is self.k:

                intent = actor.decide(
                    world=self.world.get_state(),
                    node_belief=node_belief,
                    goal=goal,

                    open_interaction=(
                        open_interaction
                    ),
                )

            else:

                intent = actor.decide(
                    world=self.world.get_state(),
                    node_belief=node_belief,
                    goal=goal,
                )

            intents.append(
                (
                    None,
                    intent,
                )
            )

        for (
            action_id,
            intent,
        ) in load_pending_actions():

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
            "CONTACT": 0.02,
        }

        required_energy = (
            costs.get(
                action,
                0.0,
            )
        )

        if (
            agent.energy
            < required_energy
        ):

            return (
                False,
                "NOT_ENOUGH_ENERGY",
            )

        if action == "MOVE":
            return True, ""

        if action == "OBSERVE_AREA":
            return True, ""

        # ==============================================
        # ACTOR CONTACT
        # ==============================================

        if action == "CONTACT":

            target_actor = (
                self.all_agents.get(
                    intent.target
                )
            )

            if target_actor is None:

                return (
                    False,
                    "UNKNOWN_ACTOR",
                )

            if (
                target_actor.id
                == agent.id
            ):

                return (
                    False,
                    "CANNOT_CONTACT_SELF",
                )

            if (
                target_actor.location
                != agent.location
            ):

                return (
                    False,
                    "ACTOR_NOT_PRESENT",
                )

            return True, ""

        # ==============================================
        # NODE ACTIONS
        # ==============================================

        node_actions = {
            "INVESTIGATE",
            "STABILIZE",
            "AMPLIFY",
            "OBSERVE",
        }

        if action in node_actions:

            if (
                intent.target
                != self.node.id
            ):

                return (
                    False,
                    "UNKNOWN_TARGET",
                )

            if (
                agent.location
                != self.node.location
            ):

                return (
                    False,
                    "TARGET_NOT_PRESENT",
                )

        if action in {
            "STABILIZE",
            "AMPLIFY",
        }:

            if not knows_node(
                agent.id,
                self.node.id,
            ):

                return (
                    False,
                    "NODE_NOT_KNOWN",
                )

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

        for (
            action_id,
            intent,
        ) in queued_intents:

            agent = (
                self.all_agents.get(
                    intent.actor_id
                )
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
                    f"DENIED "
                    f"{intent.action} "
                    f"({reason})"
                )

                record_event(
                    minute=self.minute,

                    actor_id=agent.id,

                    action=(
                        f"DENIED_"
                        f"{intent.action}"
                    ),

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

            # ==========================================
            # MOVE
            # ==========================================

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

            # ==========================================
            # CONTACT
            # ==========================================

            elif action == "CONTACT":

                agent.energy = max(
                    0.0,
                    agent.energy - 0.02,
                )

                current_goal = (
                    self.current_goals.get(
                        agent.id
                    )
                )

                source_goal = (
                    current_goal.goal_type
                    if current_goal
                    else "UNKNOWN"
                )

                interaction, created = (
                    create_or_get_interaction(
                        initiator_id=agent.id,
                        recipient_id=target,

                        topic=(
                            "UNAUTHORIZED_SIGNAL_"
                            "MANIPULATION"
                        ),

                        source_goal=(
                            source_goal
                        ),

                        minute=self.minute,
                    )
                )

                details = (
                    f"{agent.name} contacted "
                    f"{target} about "
                    f"{interaction.topic}"
                )

                if created:

                    print(
                        f"    -> INTERACTION OPENED: "
                        f"{interaction.id}"
                    )

                else:

                    print(
                        f"    -> INTERACTION ALREADY OPEN: "
                        f"{interaction.id}"
                    )

            # ==========================================
            # INVESTIGATE
            # ==========================================

            elif action == "INVESTIGATE":

                belief = NodeBelief(
                    agent_id=agent.id,
                    node_id=self.node.id,

                    believed_location=(
                        self.node.location
                    ),

                    believed_strength=(
                        self.node.anomaly_strength
                    ),

                    confidence=0.95,

                    source=(
                        "ACTIVE_INVESTIGATION"
                    ),

                    updated_minute=(
                        self.minute
                    ),
                )

                save_belief(
                    belief
                )

                learn_node(
                    agent_id=agent.id,
                    node_id=self.node.id,
                    confidence=0.95,

                    source=(
                        "ACTIVE_INVESTIGATION"
                    ),
                )

                self.node.discovered = True

                agent.energy = max(
                    0.0,
                    agent.energy - 0.10,
                )

                self.remember(
                    agent,
                    (
                        "Investigated anomalous "
                        f"node {self.node.id} "
                        f"at {self.node.location}"
                    ),
                )

                details = (
                    f"{agent.name} "
                    f"investigated "
                    f"{self.node.id}"
                )

                current_goal = (
                    self.current_goals.get(
                        agent.id
                    )
                )

                if (
                    current_goal is not None
                    and
                    current_goal.goal_type
                    == "AUDIT_SIGNAL_MANIPULATION"
                ):

                    evidence = (
                        discover_unauthorized_manipulation_evidence(
                            discoverer_id=agent.id,
                            node_id=self.node.id,
                            current_minute=self.minute,
                        )
                    )

                    if evidence is not None:

                        self.remember(
                            agent,
                            (
                                "Recovered signal "
                                "access trace linking "
                                f"{evidence.subject_actor_id} "
                                f"to {self.node.id} "
                                f"(confidence "
                                f"{evidence.strength:.2f})"
                            ),
                        )

                        print(
                            f"    -> EVIDENCE: "
                            f"{evidence.subject_actor_id} "
                            f"confidence="
                            f"{evidence.strength:.2f}"
                        )

            # ==========================================
            # STABILIZE
            # ==========================================

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
                    f"{agent.name} "
                    f"attempted to stabilize "
                    f"{self.node.id}"
                )

            # ==========================================
            # AMPLIFY
            # ==========================================

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
                    f"{agent.name} "
                    f"attempted to amplify "
                    f"{self.node.id}"
                )

            # ==========================================
            # OBSERVE
            # ==========================================

            elif action == "OBSERVE":

                agent.energy = max(
                    0.0,
                    agent.energy - 0.02,
                )

                details = (
                    f"{agent.name} "
                    f"observes "
                    f"{self.node.id}"
                )

            # ==========================================
            # OBSERVE AREA
            # ==========================================

            elif action == "OBSERVE_AREA":

                agent.energy = max(
                    0.0,
                    agent.energy - 0.01,
                )

                details = (
                    f"{agent.name} "
                    f"observes area"
                )

            # ==========================================
            # REST
            # ==========================================

            elif action == "REST":

                agent.energy = min(
                    1.0,
                    agent.energy + 0.35,
                )

                details = (
                    f"{agent.name} rests"
                )

            save_agent(
                agent
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
                f"{agent.name} "
                f"{action} -> "
                f"{target}"
            )

            if action_id is not None:

                mark_action_processed(
                    action_id
                )

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
            or
            stability_delta != 0.0
            or
            connection_delta != 0.0
        ):

            self.world.apply_event(
                signal_delta=signal_delta,
                stability_delta=stability_delta,
                connection_delta=connection_delta,
            )

    # ==================================================
    # TICK
    # ==================================================

    def tick(
        self,
    ):

        self.minute += 10

        save_simulation_minute(
            self.minute
        )

        evaluate_world(
            world=self.world.get_state(),
            node=self.node,
            minute=self.minute,
        )

        self.node_perception_phase()

        self.situation_perception_phase()

        self.actor_intelligence_phase()

        process_dialogue_responses(
            minute=self.minute
        )

        self.goal_selection_phase()

        intents = (
            self.cognition_phase()
        )

        self.resolve_intents(
            intents
        )

        evaluate_world(
            world=self.world.get_state(),
            node=self.node,
            minute=self.minute,
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

        state = (
            self.world.get_state()
        )

        print()
        print("----- WORLD STATE -----")

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
        print("----- NODE REALITY -----")

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
        print("----- REAL SITUATIONS -----")

        situations = (
            list_open_situations()
        )

        if not situations:
            print("None")

        for situation in situations:

            print()
            print(
                situation.id
            )

            print(
                f"Type: "
                f"{situation.situation_type}"
            )

            print(
                f"Location: "
                f"{situation.location}"
            )

            print(
                f"Severity: "
                f"{situation.severity:.2f}"
            )

        print()
        print("----- ACTORS -----")

        for agent in (
            self.all_agents.values()
        ):

            print()

            print(
                f"{agent.name} "
                f"[{agent.controller_type}] "
                f"[{agent.faction}]"
            )

            print(
                f"REAL location: "
                f"{agent.location}"
            )

            print(
                f"Energy: "
                f"{agent.energy:.2f}"
            )

            print(
                f"Current goal: "
                f"{agent.goal}"
            )

            selected_goal = (
                self.current_goals.get(
                    agent.id
                )
            )

            if selected_goal is not None:

                print(
                    f"Goal target: "
                    f"{selected_goal.target_id}"
                )

                print(
                    f"Goal location belief: "
                    f"{selected_goal.believed_location}"
                )

                print(
                    f"Goal priority: "
                    f"{selected_goal.priority:.2f}"
                )

                print(
                    f"Goal source: "
                    f"{selected_goal.source_situation_id}"
                )

            actor_beliefs = (
                list_actor_beliefs(
                    agent.id
                )
            )

            print(
                "Actor beliefs:"
            )

            if not actor_beliefs:
                print(" - NONE")

            for actor_belief in actor_beliefs:

                print(
                    f" - "
                    f"{actor_belief.subject_actor_id}"
                    f": "
                    f"{actor_belief.belief_type}"
                    f" "
                    f"({actor_belief.confidence:.2f})"
                )

            location_beliefs = (
                list_actor_location_beliefs(
                    agent.id
                )
            )

            print(
                "Actor location beliefs:"
            )

            if not location_beliefs:
                print(" - NONE")

            for location_belief in location_beliefs:

                print(
                    f" - "
                    f"{location_belief.subject_actor_id}"
                    f" believed at "
                    f"{location_belief.believed_location}"
                )

                print(
                    f"   confidence: "
                    f"{location_belief.confidence:.2f}"
                )

                print(
                    f"   source: "
                    f"{location_belief.source}"
                )

        # ==================================================
        # INTERACTIONS
        # ==================================================

        print()
        print(
            "----- OPEN INTERACTIONS -----"
        )

        interactions = (
            list_open_interactions()
        )

        if not interactions:

            print("None")

        for interaction in interactions:

            print()
            print(
                interaction.id
            )

            print(
                f"Initiator: "
                f"{interaction.initiator_id}"
            )

            print(
                f"Recipient: "
                f"{interaction.recipient_id}"
            )

            print(
                f"Topic: "
                f"{interaction.topic}"
            )

            print(
                f"Status: "
                f"{interaction.status}"
            )

            print(
                f"Source goal: "
                f"{interaction.source_goal}"
            )