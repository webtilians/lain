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
            location="APARTMENT_DISTRICT",
            goal="IDLE",
            controller_type="AI",
        )

    def decide(
        self,
        world: WorldState,
        node_belief: NodeBelief | None,
        goal: GoalCandidate | None,

        open_interaction: bool = False,
    ) -> ActionIntent:

        if self.agent.energy < 0.25:

            return ActionIntent(
                actor_id=self.agent.id,
                action="REST",
                target=self.agent.id,
            )

        if goal is None:

            return ActionIntent(
                actor_id=self.agent.id,
                action="OBSERVE_AREA",
                target=self.agent.location,
            )

        if (
            self.agent.location
            != goal.believed_location
        ):

            return ActionIntent(
                actor_id=self.agent.id,
                action="MOVE",
                target=(
                    goal.believed_location
                ),
            )

        if (
            goal.goal_type
            == "CONTACT_SUSPECT"
        ):

            # Contact already exists.
            # Do not spam CONTACT every tick.

            if open_interaction:

                return ActionIntent(
                    actor_id=self.agent.id,
                    action="OBSERVE_AREA",
                    target=self.agent.location,
                )

            return ActionIntent(
                actor_id=self.agent.id,
                action="CONTACT",
                target=goal.target_id,
            )

        if (
            goal.goal_type
            == "LOCATE_SUSPECT"
        ):

            return ActionIntent(
                actor_id=self.agent.id,
                action="OBSERVE_AREA",
                target=self.agent.location,
            )

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

        if (
            goal.goal_type
            == "AUDIT_SIGNAL_MANIPULATION"
        ):

            return ActionIntent(
                actor_id=self.agent.id,
                action="INVESTIGATE",
                target=goal.target_id,
            )

        return ActionIntent(
            actor_id=self.agent.id,
            action="OBSERVE_AREA",
            target=self.agent.location,
        )