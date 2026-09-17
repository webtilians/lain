from .models import (
    Agent,
    NodeBelief,
    WorldNode,
)


PERCEPTION_BIAS = {
    "AGENT_K": -0.02,
    "AGENT_NORA": 0.03,
}


def clamp(
    value: float,
) -> float:

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def perceive_node(
    agent: Agent,
    node: WorldNode,
    minute: int,
) -> NodeBelief | None:

    # El agente solamente puede percibir
    # directamente un nodo si está
    # físicamente en la misma localización.

    if agent.location != node.location:
        return None

    bias = PERCEPTION_BIAS.get(
        agent.id,
        0.0,
    )

    perceived_strength = clamp(
        node.anomaly_strength + bias
    )

    return NodeBelief(
        agent_id=agent.id,
        node_id=node.id,
        believed_location=node.location,
        believed_strength=perceived_strength,
        confidence=0.85,
        source="DIRECT_PERCEPTION",
        updated_minute=minute,
    )