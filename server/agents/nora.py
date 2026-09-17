from server.world_core.models import (
    ActionIntent,
    Agent,
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
            goal="EXPAND_THE_WIRED",
            controller_type="AI",
        )

    def decide(
        self,
        world: WorldState,
        belief: NodeBelief | None,
    ) -> ActionIntent:

        if self.agent.energy < 0.25:
            return ActionIntent(
                actor_id=self.agent.id,
                action="REST",
                target=self.agent.id,
            )

        if belief is None:
            return ActionIntent(
                actor_id=self.agent.id,
                action="OBSERVE_AREA",
                target=self.agent.location,
            )

        if (
            self.agent.location
            != belief.believed_location
        ):
            return ActionIntent(
                actor_id=self.agent.id,
                action="MOVE",
                target=belief.believed_location,
            )

        if belief.confidence < 0.50:
            return ActionIntent(
                actor_id=self.agent.id,
                action="INVESTIGATE",
                target=belief.node_id,
            )

        if belief.believed_strength < 0.75:
            return ActionIntent(
                actor_id=self.agent.id,
                action="AMPLIFY",
                target=belief.node_id,
            )

        return ActionIntent(
            actor_id=self.agent.id,
            action="OBSERVE",
            target=belief.node_id,
        )