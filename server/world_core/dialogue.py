from .database import record_event

from .evidence import (
    list_actor_beliefs,
    replace_actor_belief,
    save_actor_belief,
)

from .interactions import (
    close_interaction,
    get_interaction,
    load_pending_interaction_responses,
    mark_response_processed,
)

from .models import ActorBelief


def current_confidence(
    observer_id: str,
    subject_actor_id: str,
) -> float:

    beliefs = list_actor_beliefs(
        observer_id
    )

    for belief in beliefs:

        if (
            belief.subject_actor_id
            == subject_actor_id
        ):
            return belief.confidence

    return 0.50


def process_dialogue_responses(
    minute: int,
):

    responses = (
        load_pending_interaction_responses()
    )

    for response in responses:

        interaction = get_interaction(
            response.interaction_id
        )

        if interaction is None:

            mark_response_processed(
                response.id,
                minute,
            )

            continue

        if interaction.status != "OPEN":

            mark_response_processed(
                response.id,
                minute,
            )

            continue

        if (
            interaction.recipient_id
            != response.actor_id
        ):

            mark_response_processed(
                response.id,
                minute,
            )

            continue

        observer_id = (
            interaction.initiator_id
        )

        player_id = (
            interaction.recipient_id
        )

        old_confidence = (
            current_confidence(
                observer_id=observer_id,
                subject_actor_id=player_id,
            )
        )

        source_ref = (
            f"INTERACTION:"
            f"{interaction.id}:"
            f"{response.response_type}"
        )

        # ==========================================
        # ADMIT
        # ==========================================

        if (
            response.response_type
            == "ADMIT"
        ):

            replace_actor_belief(
                ActorBelief(
                    observer_id=observer_id,

                    subject_actor_id=(
                        player_id
                    ),

                    belief_type=(
                        "CONFIRMED_UNAUTHORIZED_"
                        "MANIPULATOR"
                    ),

                    confidence=0.98,

                    source_evidence_id=(
                        source_ref
                    ),

                    updated_minute=minute,
                )
            )

            final_status = (
                "RESOLVED_ADMISSION"
            )

        # ==========================================
        # DENY
        # ==========================================

        elif (
            response.response_type
            == "DENY"
        ):

            new_confidence = max(
                0.35,
                old_confidence - 0.18,
            )

            replace_actor_belief(
                ActorBelief(
                    observer_id=observer_id,

                    subject_actor_id=(
                        player_id
                    ),

                    belief_type=(
                        "CONTESTED_UNAUTHORIZED_"
                        "MANIPULATOR"
                    ),

                    confidence=(
                        new_confidence
                    ),

                    source_evidence_id=(
                        source_ref
                    ),

                    updated_minute=minute,
                )
            )

            final_status = (
                "RESOLVED_DENIAL"
            )

        # ==========================================
        # SILENCE
        # ==========================================

        elif (
            response.response_type
            == "SILENCE"
        ):

            new_confidence = min(
                0.95,
                old_confidence + 0.05,
            )

            replace_actor_belief(
                ActorBelief(
                    observer_id=observer_id,

                    subject_actor_id=(
                        player_id
                    ),

                    belief_type=(
                        "UNCOOPERATIVE_SUSPECT"
                    ),

                    confidence=(
                        new_confidence
                    ),

                    source_evidence_id=(
                        source_ref
                    ),

                    updated_minute=minute,
                )
            )

            final_status = (
                "RESOLVED_SILENCE"
            )

        # ==========================================
        # ACCUSE
        # ==========================================

        elif (
            response.response_type
            == "ACCUSE"
        ):

            new_confidence = max(
                0.35,
                old_confidence - 0.10,
            )

            replace_actor_belief(
                ActorBelief(
                    observer_id=observer_id,

                    subject_actor_id=(
                        player_id
                    ),

                    belief_type=(
                        "CONTESTED_UNAUTHORIZED_"
                        "MANIPULATOR"
                    ),

                    confidence=(
                        new_confidence
                    ),

                    source_evidence_id=(
                        source_ref
                    ),

                    updated_minute=minute,
                )
            )

            save_actor_belief(
                ActorBelief(
                    observer_id=observer_id,

                    subject_actor_id=(
                        response.subject_actor_id
                    ),

                    belief_type=(
                        "ALLEGED_SIGNAL_INVOLVEMENT"
                    ),

                    confidence=0.35,

                    source_evidence_id=(
                        source_ref
                    ),

                    updated_minute=minute,
                )
            )

            final_status = (
                "RESOLVED_ACCUSATION"
            )

        else:

            mark_response_processed(
                response.id,
                minute,
            )

            continue

        close_interaction(
            interaction_id=(
                interaction.id
            ),

            status=final_status,

            minute=minute,
        )

        mark_response_processed(
            response.id,
            minute,
        )

        record_event(
            minute=minute,

            actor_id=(
                response.actor_id
            ),

            action=(
                f"DIALOGUE_"
                f"{response.response_type}"
            ),

            target=interaction.id,

            details=(
                response.subject_actor_id
                or interaction.topic
            ),
        )

        print()
        print(
            f"*** DIALOGUE RESPONSE: "
            f"{response.response_type} ***"
        )

        print(
            f"{observer_id} updated belief "
            f"about {player_id}"
        )

        if (
            response.response_type
            == "ACCUSE"
        ):

            print(
                f"New allegation: "
                f"{response.subject_actor_id}"
            )