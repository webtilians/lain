from .locations import (
    spatial_priority_factor,
)

from .models import (
    ActorBelief,
    ActorLocationBelief,
    Agent,
    GoalCandidate,
    SituationBelief,
)


FACTION_RESPONSES = {

    "PROTOCOL": {

        "SIGNAL_SURGE": {
            "goal_type": (
                "REDUCE_SIGNAL_SURGE"
            ),
            "interest": 1.00,
        },

        "UNAUTHORIZED_SIGNAL_MANIPULATION": {
            "goal_type": (
                "AUDIT_SIGNAL_MANIPULATION"
            ),
            "interest": 1.25,
        },
    },

    "WIRED": {

        "SIGNAL_SURGE": {
            "goal_type": (
                "EXPAND_SIGNAL_SURGE"
            ),
            "interest": 1.00,
        },
    },
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


def build_situation_goal_candidate(
    agent: Agent,
    belief: SituationBelief,
    minute: int,
) -> GoalCandidate | None:

    if (
        belief.believed_status
        != "OPEN"
    ):
        return None

    if belief.confidence < 0.20:
        return None

    faction_rules = (
        FACTION_RESPONSES.get(
            agent.faction,
            {},
        )
    )

    response = faction_rules.get(
        belief.believed_type
    )

    if response is None:
        return None

    # ==============================================
    # COGNITIVE RELEVANCE
    # ==============================================

    base_priority = (
        belief.believed_severity
        * belief.confidence
        * response["interest"]
    )

    # ==============================================
    # SPATIAL RELEVANCE
    # ==============================================

    spatial_factor = (
        spatial_priority_factor(
            origin=agent.location,
            destination=(
                belief.believed_location
            ),
        )
    )

    priority = (
        base_priority
        * spatial_factor
    )

    # Being physically inside the crisis
    # gives it extra salience.

    if (
        agent.location
        == belief.believed_location
    ):

        priority += 0.10

    priority = clamp(
        priority
    )

    target_id = (
        belief.believed_subject_id
        or belief.situation_id
    )

    return GoalCandidate(
        agent_id=agent.id,

        goal_type=(
            response["goal_type"]
        ),

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


def build_actor_goal_candidate(
    agent: Agent,

    actor_belief: ActorBelief,

    location_beliefs:
        list[ActorLocationBelief],

    minute: int,
) -> GoalCandidate | None:

    if agent.faction != "PROTOCOL":
        return None

    if (
        actor_belief.belief_type
        != "LIKELY_UNAUTHORIZED_MANIPULATOR"
    ):
        return None

    if (
        actor_belief.confidence
        < 0.65
    ):
        return None

    location_belief = None

    for candidate in location_beliefs:

        if (
            candidate.subject_actor_id
            == actor_belief.subject_actor_id
        ):

            location_belief = candidate
            break

    if location_belief is None:
        return None

    if (
        location_belief.confidence
        < 0.30
    ):
        return None

    current_direct_perception = (
        location_belief.source
        == "DIRECT_ACTOR_PERCEPTION"

        and

        location_belief.confidence
        >= 0.95

        and

        location_belief.updated_minute
        == minute
    )

    if current_direct_perception:

        goal_type = (
            "CONTACT_SUSPECT"
        )

        multiplier = 1.45

    else:

        goal_type = (
            "LOCATE_SUSPECT"
        )

        multiplier = 1.35

    # Actor pursuit intentionally keeps
    # the 0.9 behaviour for now.
    #
    # We will spatialize pursuit separately
    # once physical travel has multiple steps.

    priority = (
        actor_belief.confidence
        * location_belief.confidence
        * multiplier
    )

    priority = clamp(
        priority
    )

    return GoalCandidate(
        agent_id=agent.id,

        goal_type=goal_type,

        target_id=(
            actor_belief.subject_actor_id
        ),

        source_situation_id=(
            f"ACTOR_BELIEF:"
            f"{actor_belief.subject_actor_id}"
        ),

        priority=priority,

        believed_location=(
            location_belief.believed_location
        ),

        created_minute=minute,
    )


def select_goal(
    agent: Agent,

    situation_beliefs:
        list[SituationBelief],

    actor_beliefs:
        list[ActorBelief],

    actor_location_beliefs:
        list[ActorLocationBelief],

    minute: int,
) -> GoalCandidate | None:

    candidates = []

    for belief in situation_beliefs:

        candidate = (
            build_situation_goal_candidate(
                agent=agent,
                belief=belief,
                minute=minute,
            )
        )

        if candidate is not None:

            candidates.append(
                candidate
            )

    for actor_belief in actor_beliefs:

        candidate = (
            build_actor_goal_candidate(
                agent=agent,

                actor_belief=(
                    actor_belief
                ),

                location_beliefs=(
                    actor_location_beliefs
                ),

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
        key=lambda item: (
            item.priority,
            item.target_id,
        ),
        reverse=True,
    )

    return candidates[0]