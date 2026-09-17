from server.world_core.models import Agent, WorldNode, WorldState


class Nora:

    def __init__(self, agent: Agent | None = None):
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
        node: WorldNode,
    ) -> dict:

        if self.agent.location != node.location:
            return {
                "action": "MOVE",
                "target": node.location,
            }

        if not node.discovered:
            return {
                "action": "INVESTIGATE",
                "target": node.id,
            }

        if node.anomaly_strength < 0.75:
            return {
                "action": "AMPLIFY",
                "target": node.id,
            }

        return {
            "action": "OBSERVE",
            "target": node.id,
        }