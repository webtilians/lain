from server.world_core.models import (
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
        )

    def decide(
        self,
        world: WorldState,
        belief: NodeBelief | None,
    ) -> dict:

        if self.agent.energy < 0.25:
            return {
                "action": "REST",
                "target": self.agent.id,
            }

        if belief is None:
            return {
                "action": "OBSERVE_AREA",
                "target": self.agent.location,
            }

        if (
            self.agent.location
            != belief.believed_location
        ):
            return {
                "action": "MOVE",
                "target": belief.believed_location,
            }

        if belief.confidence < 0.50:
            return {
                "action": "INVESTIGATE",
                "target": belief.node_id,
            }

        if belief.believed_strength < 0.75:
            return {
                "action": "AMPLIFY",
                "target": belief.node_id,
            }

        return {
            "action": "OBSERVE",
            "target": belief.node_id,
        }