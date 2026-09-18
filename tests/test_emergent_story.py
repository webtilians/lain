import pytest

from server.situations.engine import (
    load_situation,
)

from server.world_core.action_queue import (
    queue_action,
)

from server.world_core.actor_locations import (
    list_actor_location_beliefs,
)

from server.world_core.evidence import (
    list_actor_beliefs,
)

from server.world_core.interactions import (
    find_open_interaction,
    get_interaction,
    queue_interaction_response,
)

from server.world_core.knowledge import (
    knows_node,
)

from server.world_core.simulation import (
    Simulation,
)


PLAYER_ID = "PLAYER_1"
K_ID = "AGENT_K"
NODE_ID = "NODE_07"

CONTACT_TOPIC = (
    "UNAUTHORIZED_SIGNAL_MANIPULATION"
)


def get_k_belief_about_player():

    beliefs = list_actor_beliefs(
        K_ID
    )

    for belief in beliefs:

        if (
            belief.subject_actor_id
            == PLAYER_ID
        ):
            return belief

    return None


def get_k_location_belief_about_player():

    beliefs = (
        list_actor_location_beliefs(
            K_ID
        )
    )

    for belief in beliefs:

        if (
            belief.subject_actor_id
            == PLAYER_ID
        ):
            return belief

    return None


def get_k_player_interaction():

    return find_open_interaction(
        initiator_id=K_ID,
        recipient_id=PLAYER_ID,
        topic=CONTACT_TOPIC,
    )


def advance_until(
    simulation,
    predicate,
    description,
    max_ticks=10,
):

    if predicate():
        return

    for _ in range(max_ticks):

        simulation.tick()

        if predicate():
            return

    pytest.fail(
        f"World did not reach: "
        f"{description}"
    )


def move_player_to(
    simulation,
    destination: str,
    max_ticks: int = 10,
):

    for _ in range(
        max_ticks
    ):

        if (
            simulation.player.location
            == destination
        ):
            return

        queue_action(
            actor_id=PLAYER_ID,
            action="MOVE",
            target=destination,
            source="HUMAN",
        )

        simulation.tick()

    pytest.fail(
        f"PLAYER_1 failed to reach "
        f"{destination}"
    )


def test_player_action_creates_emergent_pursuit_and_denial():

    simulation = Simulation()

    # This regression isolates the K/player causal chain.
    #
    # Nora is tested independently elsewhere. Keeping her
    # active here can sustain SIGNAL_SURGE indefinitely and
    # legitimately prevent K from prioritizing the audit.

    simulation.ai_actors = [
        simulation.k
    ]

    # ==================================================
    # PHASE 1
    # PLAYER ENTERS STATION
    # ==================================================

    move_player_to(
        simulation,
        "STATION",
    )

    assert (
        simulation.player.location
        == "STATION"
    )

    # ==================================================
    # PHASE 2
    # PLAYER PERCEIVES NODE
    # ==================================================

    advance_until(
        simulation=simulation,

        predicate=lambda: knows_node(
            PLAYER_ID,
            NODE_ID,
        ),

        description=(
            "PLAYER_1 learns NODE_07"
        ),

        max_ticks=3,
    )

    assert knows_node(
        PLAYER_ID,
        NODE_ID,
    )

    # ==================================================
    # PHASE 3
    # PLAYER MANIPULATES NODE AND LEAVES
    # ==================================================

    queue_action(
        actor_id=PLAYER_ID,
        action="AMPLIFY",
        target=NODE_ID,
        source="HUMAN",
    )

    queue_action(
        actor_id=PLAYER_ID,
        action="MOVE",
        target="APARTMENT",
        source="HUMAN",
    )

    simulation.tick()

    # First travel step:
    #
    # STATION
    #   -> APARTMENT_DISTRICT

    assert (
        simulation.player.location
        == "APARTMENT_DISTRICT"
    )

    # Finish the escape.

    move_player_to(
        simulation,
        "APARTMENT",
    )

    assert (
        simulation.player.location
        == "APARTMENT"
    )

    # ==================================================
    # PHASE 4
    # WORLD CREATES CONSEQUENCE
    # ==================================================

    situation = load_situation(
        "UNAUTHORIZED_MANIPULATION_NODE_07"
    )

    assert situation is not None

    assert (
        situation.status
        == "OPEN"
    )

    assert (
        situation.situation_type
        == "UNAUTHORIZED_SIGNAL_MANIPULATION"
    )

    # ==================================================
    # PHASE 5
    # K INVESTIGATES AND FORMS SUSPICION
    # ==================================================

    advance_until(
        simulation=simulation,

        predicate=lambda: (
            get_k_belief_about_player()
            is not None
        ),

        description=(
            "K forms a belief about PLAYER_1"
        ),

        max_ticks=6,
    )

    suspicion = (
        get_k_belief_about_player()
    )

    assert suspicion is not None

    assert (
        suspicion.belief_type
        == "LIKELY_UNAUTHORIZED_MANIPULATOR"
    )

    assert (
        suspicion.confidence
        >= 0.65
    )

    assert (
        suspicion.source_evidence_id
        .startswith("TRACE_")
    )

    # ==================================================
    # PHASE 6
    # PROTOCOL DERIVES LAST KNOWN LOCATION
    # ==================================================

    advance_until(
        simulation=simulation,

        predicate=lambda: (
            (
                get_k_location_belief_about_player()
                is not None
            )
            and
            (
                get_k_location_belief_about_player()
                .believed_location
                == "APARTMENT"
            )
            and
            (
                get_k_location_belief_about_player()
                .source
                == "PROTOCOL_ACTIVITY_LOG"
            )
        ),

        description=(
            "Protocol derives PLAYER_1's "
            "latest logged location"
        ),

        max_ticks=3,
    )

    historical_location = (
        get_k_location_belief_about_player()
    )

    assert historical_location is not None

    assert (
        historical_location.believed_location
        == "APARTMENT"
    )

    assert (
        historical_location.source
        == "PROTOCOL_ACTIVITY_LOG"
    )

    # ==================================================
    # PHASE 7
    # K PURSUES PLAYER
    # ==================================================

    advance_until(
        simulation=simulation,

        predicate=lambda: (
            simulation.k.agent.location
            == "APARTMENT"
        ),

        description=(
            "K reaches PLAYER_1's "
            "last known location"
        ),

        max_ticks=6,
    )

    assert (
        simulation.k.agent.location
        == "APARTMENT"
    )

    # ==================================================
    # PHASE 8
    # DIRECT PERCEPTION CONFIRMS PLAYER
    # ==================================================

    advance_until(
        simulation=simulation,

        predicate=lambda: (
            (
                get_k_location_belief_about_player()
                is not None
            )
            and
            (
                get_k_location_belief_about_player()
                .source
                == "DIRECT_ACTOR_PERCEPTION"
            )
        ),

        description=(
            "K directly perceives PLAYER_1"
        ),

        max_ticks=3,
    )

    direct_location = (
        get_k_location_belief_about_player()
    )

    assert direct_location is not None

    assert (
        direct_location.source
        == "DIRECT_ACTOR_PERCEPTION"
    )

    assert (
        direct_location.confidence
        == pytest.approx(
            0.99
        )
    )

    # ==================================================
    # PHASE 9
    # K OPENS CONTACT
    # ==================================================

    advance_until(
        simulation=simulation,

        predicate=lambda: (
            get_k_player_interaction()
            is not None
        ),

        description=(
            "K opens contact with PLAYER_1"
        ),

        max_ticks=3,
    )

    interaction = (
        get_k_player_interaction()
    )

    assert interaction is not None

    assert (
        interaction.status
        == "OPEN"
    )

    assert (
        interaction.initiator_id
        == K_ID
    )

    assert (
        interaction.recipient_id
        == PLAYER_ID
    )

    assert (
        interaction.source_goal
        == "CONTACT_SUSPECT"
    )

    interaction_id = (
        interaction.id
    )

    # ==================================================
    # PHASE 10
    # PLAYER DENIES
    # ==================================================

    queue_interaction_response(
        interaction_id=interaction_id,

        actor_id=PLAYER_ID,

        response_type="DENY",
    )

    simulation.tick()

    # ==================================================
    # PHASE 11
    # K'S MIND CHANGES
    # ==================================================

    belief_after_denial = (
        get_k_belief_about_player()
    )

    assert (
        belief_after_denial
        is not None
    )

    assert (
        belief_after_denial.belief_type
        == "CONTESTED_UNAUTHORIZED_MANIPULATOR"
    )

    assert (
        belief_after_denial.confidence
        < suspicion.confidence
    )

    # ==================================================
    # PHASE 12
    # INTERACTION IS CLOSED
    # ==================================================

    assert (
        get_k_player_interaction()
        is None
    )

    closed_interaction = (
        get_interaction(
            interaction_id
        )
    )

    assert (
        closed_interaction
        is not None
    )

    assert (
        closed_interaction.status
        == "RESOLVED_DENIAL"
    )

    # ==================================================
    # PHASE 13
    # K STOPS PURSUING PLAYER
    # ==================================================

    current_goal = (
        simulation.current_goals.get(
            K_ID
        )
    )

    if current_goal is not None:

        assert (
            current_goal.goal_type
            not in {
                "LOCATE_SUSPECT",
                "CONTACT_SUSPECT",
            }
        )