from server.situations.engine import (
    Situation,
)

from .models import (
    Agent,
    SituationBelief,
)


SEVERITY_BIAS = {
    "AGENT_K": -0.03,
    "AGENT_NORA": 0.05,
    "PLAYER_1": 0.00,
}

# ======================================================
# INFORMATION CHANNELS
# ======================================================

FACTION_FEEDS = {

    "PROTOCOL": {

        "SIGNAL_SURGE": {
            "confidence": 0.80,
            "latency_minutes": 20,
        },
    },

    "WIRED": {

        "SIGNAL_SURGE": {
            "confidence": 0.75,
            "latency_minutes": 10,
        },
    },
}

PUBLIC_RUMOR_CONFIDENCE = 0.40
PUBLIC_RUMOR_THRESHOLD = 0.75
PUBLIC_RUMOR_LATENCY_MINUTES = 30

RESOLVED_FEED_RETENTION_MINUTES = 30


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


def information_age(
    situation: Situation,
    minute: int,
) -> int:

    changed_minute = (
        situation.status_changed_minute
    )

    if changed_minute is None:

        if situation.status == "OPEN":

            changed_minute = (
                situation.created_minute
            )

        else:

            changed_minute = (
                situation.updated_minute
            )

    return max(
        0,
        minute - changed_minute,
    )


def perceive_situation(
    agent: Agent,
    situation: Situation,
    minute: int,
) -> SituationBelief | None:

    bias = SEVERITY_BIAS.get(
        agent.id,
        0.0,
    )

    # ==================================================
    # 1. DIRECT PHYSICAL PERCEPTION
    #
    # Direct observation has no network latency.
    # ==================================================

    if (
        agent.location
        == situation.location
    ):

        return SituationBelief(
            agent_id=agent.id,
            situation_id=situation.id,

            believed_type=(
                situation.situation_type
            ),

            believed_location=(
                situation.location
            ),

            believed_subject_id=(
                situation.subject_id
            ),

            believed_status=(
                situation.status
            ),

            believed_severity=clamp(
                situation.severity
                + bias
            ),

            confidence=0.95,

            source=(
                "DIRECT_SITUATION_PERCEPTION"
            ),

            updated_minute=minute,
        )

    age = information_age(
        situation=situation,
        minute=minute,
    )

    # ==================================================
    # 2. FACTION NETWORK
    # ==================================================

    faction_feed = (
        FACTION_FEEDS.get(
            agent.faction,
            {},
        )
    )

    feed_rule = (
        faction_feed.get(
            situation.situation_type
        )
    )

    if feed_rule is not None:

        latency = (
            feed_rule[
                "latency_minutes"
            ]
        )

        information_arrived = (
            age >= latency
        )

        if information_arrived:

            visible = False

            if (
                situation.status
                == "OPEN"
            ):

                visible = True

            elif (
                situation.status
                == "RESOLVED"
            ):

                visible = (
                    age
                    <= (
                        latency
                        + RESOLVED_FEED_RETENTION_MINUTES
                    )
                )

            if visible:

                return SituationBelief(
                    agent_id=agent.id,
                    situation_id=situation.id,

                    believed_type=(
                        situation.situation_type
                    ),

                    believed_location=(
                        situation.location
                    ),

                    believed_subject_id=(
                        situation.subject_id
                    ),

                    believed_status=(
                        situation.status
                    ),

                    believed_severity=clamp(
                        situation.severity
                        + (bias * 0.5)
                    ),

                    confidence=(
                        feed_rule[
                            "confidence"
                        ]
                    ),

                    source=(
                        f"{agent.faction}_NETWORK"
                    ),

                    updated_minute=minute,
                )

    # ==================================================
    # 3. PUBLIC RUMOR
    # ==================================================

    if (
        situation.status == "OPEN"

        and

        situation.severity
        >= PUBLIC_RUMOR_THRESHOLD

        and

        age
        >= PUBLIC_RUMOR_LATENCY_MINUTES
    ):

        return SituationBelief(
            agent_id=agent.id,
            situation_id=situation.id,

            believed_type=(
                situation.situation_type
            ),

            believed_location=(
                situation.location
            ),

            believed_subject_id=None,

            believed_status="OPEN",

            believed_severity=clamp(
                situation.severity
                + bias
            ),

            confidence=(
                PUBLIC_RUMOR_CONFIDENCE
            ),

            source="PUBLIC_RUMOR",

            updated_minute=minute,
        )

    return None
