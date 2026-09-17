from server.situations.engine import Situation

from .models import (
    Agent,
    SituationBelief,
)


# Diferentes actores interpretan
# una misma crisis de forma distinta.

SEVERITY_BIAS = {
    "AGENT_K": -0.03,
    "AGENT_NORA": 0.05,
    "PLAYER_1": 0.00,
}


# Información que las facciones
# distribuyen internamente.

FACTION_FEEDS = {

    "PROTOCOL": {
        "SIGNAL_SURGE": 0.80,
    },

    "WIRED": {
        "SIGNAL_SURGE": 0.75,
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


def perceive_situation(
    agent: Agent,
    situation: Situation,
    minute: int,
) -> SituationBelief | None:

    bias = SEVERITY_BIAS.get(
        agent.id,
        0.0,
    )

    # ==========================================
    # 1. PERCEPCIÓN DIRECTA
    # ==========================================

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
                situation.severity + bias
            ),

            confidence=0.95,

            source=(
                "DIRECT_SITUATION_PERCEPTION"
            ),

            updated_minute=minute,
        )

    # ==========================================
    # 2. RED DE LA FACCIÓN
    # ==========================================

    faction_feed = (
        FACTION_FEEDS.get(
            agent.faction,
            {},
        )
    )

    feed_confidence = (
        faction_feed.get(
            situation.situation_type
        )
    )

    if feed_confidence is not None:

        # Las redes distribuyen inmediatamente
        # situaciones abiertas.
        #
        # Una resolución solo permanece
        # en el feed durante 30 min simulados.

        visible = (
            situation.status == "OPEN"
            or (
                situation.status == "RESOLVED"
                and
                minute
                - situation.updated_minute
                <= 30
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

                confidence=feed_confidence,

                source=(
                    f"{agent.faction}_NETWORK"
                ),

                updated_minute=minute,
            )

    # ==========================================
    # 3. RUMOR PÚBLICO
    # ==========================================

    # Solo situaciones muy grandes empiezan
    # a filtrarse a la población general.

    if (
        situation.status == "OPEN"
        and situation.severity >= 0.75
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

            # Un rumor no necesariamente
            # identifica con precisión
            # el objeto responsable.
            believed_subject_id=None,

            believed_status="OPEN",

            believed_severity=clamp(
                situation.severity + bias
            ),

            confidence=0.40,

            source="PUBLIC_RUMOR",

            updated_minute=minute,
        )

    return None