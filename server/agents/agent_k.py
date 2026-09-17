from server.world_core.models import (
    ActionIntent,
    Agent,
    GoalCandidate,
    NodeBelief,
    WorldState,
)


class AgentK:

    def __init__(
        self,
        agent: Agent | None = None,
    ):

        self.agent = agent or Agent(
            id="AGENT_K",
            name="K",

            faction="PROTOCOL",

            location=(
                "APARTMENT_DISTRICT"
            ),

            goal="IDLE",

            controller_type="AI",
        )

    def decide(
        self,
        world: WorldState,
        node_belief: NodeBelief | None,
        goal: GoalCandidate | None,
    ) -> ActionIntent:

        # ==========================================
        # BASIC RESOURCE NEED
        # ==========================================

        if self.agent.energy < 0.25:

            return ActionIntent(
                actor_id=self.agent.id,
                action="REST",
                target=self.agent.id,
            )

        # ==========================================
        # NO CURRENT MOTIVATION
        # ==========================================

        if goal is None:

            return ActionIntent(
                actor_id=self.agent.id,
                action="OBSERVE_AREA",
                target=self.agent.location,
            )

        # ==========================================
        # TRAVEL TOWARDS GOAL
        # ==========================================

        if (
            self.agent.location
            != goal.believed_location
        ):

            return ActionIntent(
                actor_id=self.agent.id,
                action="MOVE",
                target=goal.believed_location,
            )

        # ==========================================
        # SIGNAL SURGE
        # ==========================================

        if (
            goal.goal_type
            == "REDUCE_SIGNAL_SURGE"
        ):

            if node_belief is None:

                return ActionIntent(
                    actor_id=self.agent.id,
                    action="INVESTIGATE",
                    target=goal.target_id,
                )

            if (
                node_belief.confidence
                < 0.50
            ):

                return ActionIntent(
                    actor_id=self.agent.id,
                    action="INVESTIGATE",
                    target=goal.target_id,
                )

            return ActionIntent(
                actor_id=self.agent.id,
                action="STABILIZE",
                target=goal.target_id,
            )

        # ==========================================
        # UNAUTHORIZED MANIPULATION
        # ==========================================

        if (
            goal.goal_type
            == "AUDIT_SIGNAL_MANIPULATION"
        ):

            # Por ahora K inspecciona el nodo
            # buscando rastros de quién lo alteró.
            #
            # Más adelante esto generará
            # evidence / actor beliefs.

            return ActionIntent(
                actor_id=self.agent.id,
                action="INVESTIGATE",
                target=goal.target_id,
            )

        # ==========================================
        # FALLBACK
        # ==========================================

        return ActionIntent(
            actor_id=self.agent.id,
            action="OBSERVE_AREA",
            target=self.agent.location,
        )