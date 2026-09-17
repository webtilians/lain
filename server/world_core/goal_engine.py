from .models import (
    Agent,
    GoalCandidate,
    SituationBelief,
)


FACTION_RESPONSES = {
    "PROTOCOL": {
        "SIGNAL_SURGE": {
            "goal_type": "REDUCE_SIGNAL_SURGE",
            "interest": 1.00,
        },
    },

    "WIRED": {
        "SIGNAL_SURGE": {
            "goal_type": "EXPAND_SIGNAL_SURGE",
            "interest": 1.00,
        },
    },
}


def clamp(value: float) -> float:
    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def build_goal_candidate(
    agent: Agent,
    belief: SituationBelief,
    minute: int,
) -> GoalCandidate | None:

    if belief.believed_status != "OPEN":
        return None

    if belief.confidence < 0.20:
        return None

    faction_rules = FACTION_RESPONSES.get(
        agent.faction,
        {},
    )

    response = faction_rules.get(
        belief.believed_type
    )

    if response is None:
        return None

    priority = (
        belief.believed_severity
        * belief.confidence
        * response["interest"]
    )

    if (
        agent.location
        == belief.believed_location
    ):
        priority += 0.10

    priority = clamp(
        priority
    )

    if belief.believed_subject_id is None:
        target_id = belief.situation_id
    else:
        target_id = (
            belief.believed_subject_id
        )

    return GoalCandidate(
        agent_id=agent.id,
        goal_type=response["goal_type"],
        target_id=target_id,
        source_situation_id=(
            belief.situation_id
        ),
        priority=priority,
        believed_location=(
            belief.believed_location
        ),
        created_minute=minute,
    )


def select_goal(
    agent: Agent,
    beliefs: list[SituationBelief],
    minute: int,
) -> GoalCandidate | None:

    candidates = []

    for belief in beliefs:

        candidate = (
            build_goal_candidate(
                agent=agent,
                belief=belief,
                minute=minute,
            )
        )

        if candidate is not None:
            candidates.append(
                candidate
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item.priority,
        reverse=True,
    )

    return candidates[0]