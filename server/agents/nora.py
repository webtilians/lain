from server.world_core.models import (
    ActionIntent,
    Agent,
    GoalCandidate,
    NodeBelief,
    WorldState,
)


class Nora:

    def __init__(
        self,
        agent: Agent | None = None,
    ):

        self.agent = agent or Agent(
            id="AGENT_NORA",
            name="Nora",
            faction="WIRED",
            location="OLD_DISTRICT",
            goal="IDLE",
            controller_type="AI",
        )

    def decide(
        self,
        world: WorldState,
        node_belief: NodeBelief | None,
        goal: GoalCandidate | None,
    ) -> ActionIntent:

        # --------------------------------------------
        # RESOURCE NEED
        # --------------------------------------------

        if self.agent.energy < 0.25:

            return ActionIntent(
                actor_id=self.agent.id,
                action="REST",
                target=self.agent.id,
            )

        # --------------------------------------------
        # NO RELEVANT GOAL
        # --------------------------------------------

        if goal is None:

            return ActionIntent(
                actor_id=self.agent.id,
                action="OBSERVE_AREA",
                target=self.agent.location,
            )

        # --------------------------------------------
        # MOVE TOWARDS GOAL
        # --------------------------------------------

        if (
            self.agent.location
            != goal.believed_location
        ):

            return ActionIntent(
                actor_id=self.agent.id,
                action="MOVE",
                target=goal.believed_location,
            )

        # --------------------------------------------
        # WIRED INTERPRETATION
        # --------------------------------------------

        if (
            goal.goal_type
            == "EXPAND_SIGNAL_SURGE"
        ):

            if node_belief is None:

                return ActionIntent(
                    actor_id=self.agent.id,
                    action="INVESTIGATE",
                    target=goal.target_id,
                )

            if node_belief.confidence < 0.50:

                return ActionIntent(
                    actor_id=self.agent.id,
                    action="INVESTIGATE",
                    target=goal.target_id,
                )

            return ActionIntent(
                actor_id=self.agent.id,
                action="AMPLIFY",
                target=goal.target_id,
            )

        # --------------------------------------------
        # FALLBACK
        # --------------------------------------------

        return ActionIntent(
            actor_id=self.agent.id,
            action="OBSERVE_AREA",
            target=self.agent.location,
        )