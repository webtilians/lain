from .shared_experiences import record_shared_attention
from .database import get_connection
from .episodic_memory import initialize_memory_provenance, save_episodic_memory
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
    evaluate_nodes,
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
from .generated_entities import (
    GeneratedActor, advance_local_waypoint, belief_driven_goal,
    list_generated_entities,
)
from .character_sheets import actor_role, synchronize_existing_profiles
from .station_echo import (
    CASE_ID, initialize_station_case, discover_station_echo,
    validate_case_choice, resolve_station_echo, has_pending_station_response,
    record_station_response,
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

from .locations import (
    is_known_location,
    next_hop,
    shortest_hops,
)

from .messages import (
    ensure_initial_player_message,
)

from .station_story import (
    ensure_station_followup,
)
from .prologue import initialize_prologue, gate_move
from .residents import initialize_residents, advance_residents

from .models import (
    ActionIntent,
    Agent,
    NodeBelief,
    WorldNode,
)

from .perception import (
    perceive_node,
)

from .reports import (
    evaluate_accepted_reports_against_belief,
    process_information_reports,
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

        node_07 = load_or_create_node(
            WorldNode(
                id="NODE_07",
                location="STATION",
                node_type="UNKNOWN_SIGNAL",
                discovered=False,
                active=True,
                anomaly_strength=0.60,
            )
        )

        node_12 = load_or_create_node(
            WorldNode(
                id="NODE_12",
                location="OLD_DISTRICT",
                node_type="UNKNOWN_SIGNAL",
                discovered=False,
                active=True,
                anomaly_strength=0.10,
            )
        )

        self.nodes = {
            node_07.id: node_07,
            node_12.id: node_12,
        }

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

        # Rehydrate generated actors on restart; the seeded NPCs and the
        # player keep their existing identity and controller contracts.
        self.refresh_generated_actors()
        initialize_station_case()

        self.minute = (
            load_simulation_minute()
        )

        self.current_goals = {}

        self.bootstrap_existing_knowledge()
        self.seed_initial_leads()

        ensure_initial_player_message()
        initialize_prologue()
        # Seed after the legacy/new-world prologue decision. Civilians keep
        # independent private memories and do not inherit initial Wired leads.
        for resident in initialize_residents():
            self.all_agents[resident.id] = resident

        from .chapter_one import initialize_chapter
        initialize_chapter()

        ensure_station_followup(
            player_id=self.player.id,
            minute=self.minute,
        )

    def refresh_generated_actors(self):
        """Discover persistent NPC-created entities, including mid-session births."""
        existing = list_generated_entities()
        synchronize_existing_profiles()
        for entity_id, creator_id, seed_goal, name, location in existing:
            if entity_id in self.all_agents:
                continue
            agent = load_or_create_agent(
                Agent(
                    id=entity_id, name=name, faction="WIRED_ENTITY",
                    location=location, goal=seed_goal,
                    controller_type="GENERATED",
                )
            )
            self.all_agents[entity_id] = agent
            self.ai_actors.append(GeneratedActor(agent, creator_id, seed_goal))

    # ==================================================
    # BOOTSTRAP
    # ==================================================

    def bootstrap_existing_knowledge(
        self,
    ):

        for agent in (
            self.all_agents.values()
        ):

            for node in (
                self.nodes.values()
            ):

                memory_marker = (
                    "Discovered anomalous "
                    f"node {node.id} "
                    f"at {node.location}"
                )

                if (
                    memory_marker
                    not in agent.memory
                ):
                    continue

                learn_node(
                    agent_id=agent.id,
                    node_id=node.id,
                    confidence=1.0,
                    source="EPISODIC_MEMORY",
                )

    def seed_initial_leads(
        self,
    ):

        node = (
            self.nodes["NODE_07"]
        )

        # Newborn entities do not inherit K/Nora's initial signal lead.
        for actor in (self.k, self.nora):

            agent = actor.agent

            existing = load_belief(
                agent.id,
                node.id,
            )

            if existing is not None:
                continue

            save_belief(
                NodeBelief(
                    agent_id=agent.id,
                    node_id=node.id,

                    believed_location=(
                        node.location
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
        source_kind: str = "SELF_REPORTED",
    ):

        if text in agent.memory:
            return

        initialize_memory_provenance()
        with get_connection() as conn:
            save_episodic_memory(
                conn, agent.id, text, source_kind=source_kind,
                source_actor_id=agent.id, minute=self.minute,
            )
        agent.memory.append(text)

    # ==================================================
    # NODE PERCEPTION
    # ==================================================

    def node_perception_phase(
        self,
    ):

        for agent in (
            self.all_agents.values()
        ):

            for node in (
                self.nodes.values()
            ):

                if not node.active:
                    continue

                perception = perceive_node(
                    agent=agent,
                    node=node,
                    minute=self.minute,
                )

                if perception is None:
                    continue

                save_belief(
                    perception
                )

                if knows_node(
                    agent.id,
                    node.id,
                ):
                    continue

                learn_node(
                    agent_id=agent.id,
                    node_id=node.id,

                    confidence=(
                        perception.confidence
                    ),

                    source=(
                        "DIRECT_PERCEPTION"
                    ),
                )

                node.discovered = True

                save_node(
                    node
                )

                self.remember(
                    agent,
                    (
                        "Discovered anomalous "
                        f"node {node.id} "
                        f"at {node.location}"
                    ),
                    source_kind="DIRECT_PERCEPTION",
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

            # Reports arrive first.
            #
            # A real channel or direct perception
            # later in this same tick may overwrite
            # the report.

            process_information_reports(
                agent=agent,
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

                # Before replacing the current belief,
                # compare authoritative information against
                # any explicit reports the agent previously
                # accepted.

                evaluate_accepted_reports_against_belief(
                    agent=agent,
                    belief=belief,
                    current_minute=self.minute,
                )

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

            # A generated entity's own fresh direct perception can override
            # its seed goal. The regular faction planner still governs K/Nora.
            if isinstance(actor, GeneratedActor):
                generated_goal = belief_driven_goal(agent, self.minute)
                agent.goal = (
                    generated_goal.goal_type if generated_goal is not None
                    else actor.seed_goal
                )
                self.current_goals[agent.id] = generated_goal
                save_agent(agent)
                continue

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

            goal = (
                self.current_goals.get(
                    agent.id
                )
            )

            node_belief = None

            if (
                goal is not None
                and
                goal.target_id in self.nodes
            ):

                node_belief = load_belief(
                    agent.id,
                    goal.target_id,
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
            "WANDER": 0.02,
            "RESPOND_TO_TRACE": 0.02,
            "BROADCAST_TRACE": 0.02,
            "ARCHIVE_TRACE": 0.02,
            "CONTACT": 0.02,
        }

        # El movimiento entre localizaciones es gratuito
        # para el jugador humano.
        # Los agentes autónomos conservan su coste.

        if (
            agent.id == "PLAYER_1"
            and action == "MOVE"
        ):
            required_energy = 0.0

        else:
            required_energy = costs.get(
                action,
                0.0,
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
            # Only a FRESH opted-in player save is held at the boundary.
            # Existing saved games and autonomous NPCs retain their routes.
            if agent.id == self.player.id:
                allowed, reason = gate_move(agent.id, intent.target)
                if not allowed:
                    return allowed, reason
            elif intent.target in {"SCHOOL", "SCHOOL_LAB", "NIGHTCLUB"}:
                return False, "NPC_PROLOGUE_ONLY"

            if not is_known_location(
                agent.location
            ):

                return (
                    False,
                    "UNKNOWN_ORIGIN",
                )

            if not is_known_location(
                intent.target
            ):

                return (
                    False,
                    "UNKNOWN_LOCATION",
                )

            if (
                agent.location
                == intent.target
            ):

                return (
                    False,
                    "ALREADY_THERE",
                )

            distance = shortest_hops(
                origin=agent.location,
                destination=intent.target,
            )

            if distance is None:

                return (
                    False,
                    "UNREACHABLE_LOCATION",
                )

            return True, ""

        if action == "OBSERVE_AREA":
            return True, ""

        if action == "WANDER":
            # Local physical motion is private to generated agents and must
            # target their CURRENT semantic location, never a hidden location.
            if agent.controller_type != "GENERATED" or intent.target != agent.location:
                return False, "INVALID_WANDER"
            return True, ""

        if action in {"BROADCAST_TRACE", "ARCHIVE_TRACE"}:
            if agent.id != self.player.id:
                return False, "PLAYER_ONLY_CASE_CHOICE"
            return validate_case_choice(agent.id, action, agent.location, intent.target)

        if action == "RESPOND_TO_TRACE":
            if (agent.controller_type != "GENERATED"
                    or intent.target != CASE_ID
                    or not has_pending_station_response(agent.id, agent.location)):
                return False, "CASE_RESPONSE_NOT_AVAILABLE"
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

            target_node = (
                self.nodes.get(
                    intent.target
                )
            )

            if target_node is None:

                return (
                    False,
                    "UNKNOWN_TARGET",
                )

            if (
                not target_node.active
            ):

                return (
                    False,
                    "NODE_INACTIVE",
                )

            if (
                agent.location
                != target_node.location
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
                intent.target,
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

        node_deltas = {
            node_id: 0.0
            for node_id in self.nodes
        }

        signal_delta = 0.0
        stability_delta = 0.0
        connection_delta = 0.0

        # Resultados de las acciones procesadas
        # durante este tick.
        self.action_results = {}
        experienced_actions = []

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

                    self.action_results[action_id] = {
                        "accepted": False,
                        "action": intent.action,
                        "target": intent.target,
                        "reason": "UNKNOWN_ACTOR",
                    }

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

                    self.action_results[action_id] = {
                        "accepted": False,
                        "action": intent.action,
                        "target": intent.target,
                        "reason": reason,
                    }

                    mark_action_processed(
                        action_id
                    )

                continue

            action = intent.action
            target = intent.target

            target_node = (
                self.nodes.get(
                    target
                )
            )

            details = ""
            event_target = target

            # ==========================================
            # MOVE
            # ==========================================

            if action == "MOVE":

                origin = (
                    agent.location
                )

                destination = (
                    target
                )

                arrival = next_hop(
                    origin=origin,
                    destination=destination,
                )

                if arrival is None:

                    # This should already have been
                    # rejected by validate_intent().
                    continue

                agent.location = (
                    arrival
                )

                # Solo los agentes autónomos consumen
                # energía al desplazarse.

                if agent.id != "PLAYER_1":

                    agent.energy = max(
                        0.0,
                        agent.energy - 0.05,
                    )

                # Important:
                # movement intelligence must record
                # the place actually reached,
                # not the requested final destination.

                event_target = (
                    arrival
                )

                details = (
                    f"{agent.name} moved "
                    f"from {origin} "
                    f"to {arrival} "
                    f"toward {destination}"
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
                            "PLAYER_INITIATED_CONVERSATION"
                            if agent.id == self.player.id
                            else "UNAUTHORIZED_SIGNAL_MANIPULATION"
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
                    node_id=target_node.id,

                    believed_location=(
                        target_node.location
                    ),

                    believed_strength=(
                        target_node.anomaly_strength
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
                    node_id=target_node.id,
                    confidence=0.95,

                    source=(
                        "ACTIVE_INVESTIGATION"
                    ),
                )

                target_node.discovered = True

                save_node(
                    target_node
                )

                agent.energy = max(
                    0.0,
                    agent.energy - 0.10,
                )

                self.remember(
                    agent,
                    (
                        "Investigated anomalous "
                        f"node {target_node.id} "
                        f"at {target_node.location}"
                    ),
                    source_kind="ACTIVE_INVESTIGATION",
                )

                details = (
                    f"{agent.name} "
                    f"investigated "
                    f"{target_node.id}"
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
                            node_id=target_node.id,
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
                                f"to {target_node.id} "
                                f"(confidence "
                                f"{evidence.strength:.2f})"
                            ),
                            source_kind="ACTIVE_INVESTIGATION",
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

                node_deltas[
                    target_node.id
                ] -= 0.10

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
                    f"{target_node.id}"
                )

            # ==========================================
            # AMPLIFY
            # ==========================================

            elif action == "AMPLIFY":

                node_deltas[
                    target_node.id
                ] += 0.10

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
                    f"{target_node.id}"
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
                    f"{target_node.id}"
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
            # LOCAL WANDER (same semantic location)
            # ==========================================

            elif action == "WANDER":
                waypoint = advance_local_waypoint(agent.id)
                agent.energy = max(0.0, agent.energy - 0.02)
                details = f"Local waypoint {waypoint}"

            # ==========================================
            # STATION CASE: evidence-based choice / witness response
            # ==========================================

            elif action in {"BROADCAST_TRACE", "ARCHIVE_TRACE"}:
                witnesses = resolve_station_echo(agent.id, action, self.minute)
                agent.energy = max(0.0, agent.energy - 0.02)
                details = (
                    f"Shared station echo with {witnesses} present witnesses"
                    if action == "BROADCAST_TRACE"
                    else "Archived station echo without sharing it"
                )

            elif action == "RESPOND_TO_TRACE":
                details = record_station_response(
                    agent.id, actor_role(agent.id), self.minute,
                )
                agent.energy = max(0.0, agent.energy - 0.02)

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

            # An accepted direct investigation (not an OBSERVE or rumor)
            # is the only way to unlock this player's persistent case.
            if (action == "INVESTIGATE" and agent.id == self.player.id
                    and target == "NODE_07"):
                if discover_station_echo(agent.id, self.minute):
                    record_event(
                        minute=self.minute, actor_id=agent.id,
                        action="CASE_ECHO_DISCOVERED", target=CASE_ID,
                        details="A missing beat found in the observed signal",
                    )

            save_agent(
                agent
            )

            event_id = record_event(
                minute=self.minute,
                actor_id=agent.id,
                action=action,
                target=event_target,
                details=details,
                location=agent.location,
            )
            experienced_actions.append(dict(id=event_id, actor=agent.id,
                action=action, target=event_target, location=agent.location,
                minute=self.minute))

            print(
                f"[{self.minute:04}m] "
                f"{agent.name} "
                f"{action} -> "
                f"{event_target}"
            )

            if action_id is not None:

                self.action_results[action_id] = {
                    "accepted": True,
                    "action": action,
                    "target": event_target,
                    "reason": "",
                }

                mark_action_processed(
                    action_id
                )

        record_shared_attention(experienced_actions)

        for (
            node_id,
            node_delta,
        ) in node_deltas.items():

            if node_delta == 0.0:
                continue

            node = (
                self.nodes[node_id]
            )

            node.anomaly_strength = max(
                0.0,
                min(
                    1.0,
                    node.anomaly_strength
                    + node_delta,
                ),
            )

            save_node(
                node
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

        return self.action_results

    # ==================================================
    # TICK
    # ==================================================

    def tick(
        self,
    ):

        self.refresh_generated_actors()
        self.minute += 10

        save_simulation_minute(
            self.minute
        )
        advance_residents(self.minute)

        evaluate_nodes(
            world=self.world.get_state(),

            nodes=list(
                self.nodes.values()
            ),

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

        action_results = self.resolve_intents(
            intents
        )

        ensure_station_followup(
            player_id=self.player.id,
            minute=self.minute,
        )

        evaluate_nodes(
            world=self.world.get_state(),

            nodes=list(
                self.nodes.values()
            ),

            minute=self.minute,
        )

        return action_results

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

        for node in (
            self.nodes.values()
        ):

            print()
            print(
                f"Node:       "
                f"{node.id}"
            )

            print(
                f"Location:   "
                f"{node.location}"
            )

            print(
                f"Active:     "
                f"{node.active}"
            )

            print(
                f"Anomaly:    "
                f"{node.anomaly_strength:.2f}"
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
