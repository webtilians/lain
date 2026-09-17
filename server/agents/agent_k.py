from server.world_core.models import Agent, WorldNode, WorldState


class AgentK:

    def __init__(self, agent: Agent | None = None):
        self.agent = agent or Agent(
            id="AGENT_K",
            name="K",
            faction="PROTOCOL",
            location="APARTMENT_DISTRICT",
            goal="INVESTIGATE_ANOMALIES",
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

        if node.anomaly_strength > 0.30:
            return {
                "action": "STABILIZE",
                "target": node.id,
            }

        return {
            "action": "OBSERVE",
            "target": node.id,
        }