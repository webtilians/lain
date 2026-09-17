import pytest

from server.world_core.actor_locations import (
    decay_actor_location_beliefs,
    list_actor_location_beliefs,
    save_actor_location_belief,
    update_actor_location_intelligence,
)

from server.world_core.database import (
    load_or_create_agent,
    record_event,
)

from server.world_core.dialogue import (
    process_dialogue_responses,
)

from server.world_core.evidence import (
    discover_unauthorized_manipulation_evidence,
    list_actor_beliefs,
    save_actor_belief,
)

from server.world_core.goal_engine import (
    select_goal,
)

from server.world_core.interactions import (
    create_or_get_interaction,
    find_open_interaction,
    get_interaction,
    queue_interaction_response,
)

from server.world_core.models import (
    ActorBelief,
    ActorLocationBelief,
    Agent,
    SituationBelief,
)


def create_k():

    return load_or_create_agent(
        Agent(
            id="AGENT_K",
            name="K",
            faction="PROTOCOL",
            location="STATION",
            goal="IDLE",
            controller_type="AI",
        )
    )


def create_nora():

    return load_or_create_agent(
        Agent(
            id="AGENT_NORA",
            name="Nora",
            faction="WIRED",
            location="STATION",
            goal="IDLE",
            controller_type="AI",
        )
    )


def create_player(
    location="APARTMENT",
):

    return load_or_create_agent(
        Agent(
            id="PLAYER_1",
            name="Player",
            faction="UNALIGNED",
            location=location,
            goal="UNKNOWN",
            controller_type="HUMAN",
        )
    )


# ======================================================
# 1. SAME SITUATION, DIFFERENT FACTION GOALS
# ======================================================

def test_same_situation_creates_opposed_goals():

    k = Agent(
        id="AGENT_K",
        name="K",
        faction="PROTOCOL",
        location="STATION",
        goal="IDLE",
    )

    nora = Agent(
        id="AGENT_NORA",
        name="Nora",
        faction="WIRED",
        location="STATION",
        goal="IDLE",
    )

    k_belief = SituationBelief(
        agent_id=k.id,

        situation_id=(
            "SIGNAL_SURGE_NODE_07"
        ),

        believed_type="SIGNAL_SURGE",
        believed_location="STATION",

        believed_subject_id=(
            "NODE_07"
        ),

        believed_status="OPEN",

        believed_severity=0.70,
        confidence=0.95,

        source=(
            "DIRECT_SITUATION_PERCEPTION"
        ),

        updated_minute=100,
    )

    nora_belief = SituationBelief(
        agent_id=nora.id,

        situation_id=(
            "SIGNAL_SURGE_NODE_07"
        ),

        believed_type="SIGNAL_SURGE",
        believed_location="STATION",

        believed_subject_id=(
            "NODE_07"
        ),

        believed_status="OPEN",

        believed_severity=0.70,
        confidence=0.95,

        source=(
            "DIRECT_SITUATION_PERCEPTION"
        ),

        updated_minute=100,
    )

    k_goal = select_goal(
        agent=k,

        situation_beliefs=[
            k_belief
        ],

        actor_beliefs=[],

        actor_location_beliefs=[],

        minute=100,
    )

    nora_goal = select_goal(
        agent=nora,

        situation_beliefs=[
            nora_belief
        ],

        actor_beliefs=[],

        actor_location_beliefs=[],

        minute=100,
    )

    assert k_goal is not None
    assert nora_goal is not None

    assert (
        k_goal.goal_type
        == "REDUCE_SIGNAL_SURGE"
    )

    assert (
        nora_goal.goal_type
        == "EXPAND_SIGNAL_SURGE"
    )

    assert (
        k_goal.target_id
        == "NODE_07"
    )

    assert (
        nora_goal.target_id
        == "NODE_07"
    )


# ======================================================
# 2. DIRECT ACTOR PERCEPTION
# ======================================================

def test_colocated_actor_is_directly_perceived():

    k = create_k()

    create_player(
        location="STATION"
    )

    suspicion = ActorBelief(
        observer_id=k.id,

        subject_actor_id=(
            "PLAYER_1"
        ),

        belief_type=(
            "LIKELY_UNAUTHORIZED_MANIPULATOR"
        ),

        confidence=0.82,

        source_evidence_id="TRACE_TEST",

        updated_minute=100,
    )

    update_actor_location_intelligence(
        observer=k,

        actor_beliefs=[
            suspicion
        ],

        current_minute=100,
    )

    beliefs = (
        list_actor_location_beliefs(
            k.id
        )
    )

    player_belief = next(
        belief
        for belief in beliefs

        if (
            belief.subject_actor_id
            == "PLAYER_1"
        )
    )

    assert (
        player_belief.believed_location
        == "STATION"
    )

    assert (
        player_belief.source
        == "DIRECT_ACTOR_PERCEPTION"
    )

    assert (
        player_belief.confidence
        == pytest.approx(
            0.99
        )
    )


# ======================================================
# 3. LOCATION INFORMATION AGES
# ======================================================

def test_direct_location_belief_decays():

    belief = ActorLocationBelief(
        observer_id="AGENT_K",

        subject_actor_id=(
            "PLAYER_1"
        ),

        believed_location="APARTMENT",

        confidence=0.99,

        source=(
            "DIRECT_ACTOR_PERCEPTION"
        ),

        source_event_id=-1,

        updated_minute=100,
    )

    save_actor_location_belief(
        belief
    )

    decay_actor_location_beliefs(
        observer_id="AGENT_K",

        current_minute=180,
    )

    beliefs = (
        list_actor_location_beliefs(
            "AGENT_K"
        )
    )

    assert len(beliefs) == 1

    # 0.99 - 80 / 800 = 0.89

    assert (
        beliefs[0].confidence
        == pytest.approx(
            0.89
        )
    )

    # Evidence timestamp must NOT move.

    assert (
        beliefs[0].updated_minute
        == 100
    )


# ======================================================
# 4. FORENSIC EVIDENCE CANNOT BE FARMED
# ======================================================

def test_same_forensic_trace_is_not_rediscovered():

    create_k()
    create_player()

    record_event(
        minute=100,

        actor_id="PLAYER_1",

        action="AMPLIFY",

        target="NODE_07",

        details=(
            "Player amplified node"
        ),
    )

    first = (
        discover_unauthorized_manipulation_evidence(
            discoverer_id="AGENT_K",

            node_id="NODE_07",

            current_minute=120,
        )
    )

    second = (
        discover_unauthorized_manipulation_evidence(
            discoverer_id="AGENT_K",

            node_id="NODE_07",

            current_minute=130,
        )
    )

    assert first is not None

    # Same event cannot create fresh evidence
    # over and over.

    assert second is None

    beliefs = (
        list_actor_beliefs(
            "AGENT_K"
        )
    )

    assert len(beliefs) == 1

    assert (
        beliefs[0].belief_type
        == "LIKELY_UNAUTHORIZED_MANIPULATOR"
    )


# ======================================================
# 5. DENIAL CHANGES K'S BELIEF
# ======================================================

def test_denial_reduces_suspicion_and_closes_dialogue():

    create_k()
    create_player()

    save_actor_belief(
        ActorBelief(
            observer_id="AGENT_K",

            subject_actor_id=(
                "PLAYER_1"
            ),

            belief_type=(
                "LIKELY_UNAUTHORIZED_MANIPULATOR"
            ),

            confidence=0.82,

            source_evidence_id=(
                "TRACE_TEST"
            ),

            updated_minute=100,
        )
    )

    interaction, created = (
        create_or_get_interaction(
            initiator_id="AGENT_K",

            recipient_id="PLAYER_1",

            topic=(
                "UNAUTHORIZED_SIGNAL_"
                "MANIPULATION"
            ),

            source_goal=(
                "CONTACT_SUSPECT"
            ),

            minute=150,
        )
    )

    assert created is True

    queue_interaction_response(
        interaction_id=(
            interaction.id
        ),

        actor_id="PLAYER_1",

        response_type="DENY",
    )

    process_dialogue_responses(
        minute=160
    )

    beliefs = (
        list_actor_beliefs(
            "AGENT_K"
        )
    )

    assert len(beliefs) == 1

    belief = beliefs[0]

    assert (
        belief.belief_type
        == "CONTESTED_UNAUTHORIZED_MANIPULATOR"
    )

    assert (
        belief.confidence
        == pytest.approx(
            0.64
        )
    )

    assert (
        find_open_interaction(
            initiator_id="AGENT_K",

            recipient_id="PLAYER_1",

            topic=(
                "UNAUTHORIZED_SIGNAL_"
                "MANIPULATION"
            ),
        )
        is None
    )

    closed = get_interaction(
        interaction.id
    )

    assert closed is not None

    assert (
        closed.status
        == "RESOLVED_DENIAL"
    )


# ======================================================
# 6. EVIDENCE + DIRECT SIGHTING => CONTACT
# ======================================================

def test_confirmed_location_generates_contact_goal():

    k = create_k()

    create_player(
        location="STATION"
    )

    suspicion = ActorBelief(
        observer_id=k.id,

        subject_actor_id=(
            "PLAYER_1"
        ),

        belief_type=(
            "LIKELY_UNAUTHORIZED_MANIPULATOR"
        ),

        confidence=0.82,

        source_evidence_id=(
            "TRACE_TEST"
        ),

        updated_minute=100,
    )

    save_actor_belief(
        suspicion
    )

    update_actor_location_intelligence(
        observer=k,

        actor_beliefs=[
            suspicion
        ],

        current_minute=120,
    )

    location_beliefs = (
        list_actor_location_beliefs(
            k.id
        )
    )

    goal = select_goal(
        agent=k,

        situation_beliefs=[],

        actor_beliefs=(
            list_actor_beliefs(
                k.id
            )
        ),

        actor_location_beliefs=(
            location_beliefs
        ),

        minute=120,
    )

    assert goal is not None

    assert (
        goal.goal_type
        == "CONTACT_SUSPECT"
    )

    assert (
        goal.target_id
        == "PLAYER_1"
    )

    assert (
        goal.believed_location
        == "STATION"
    )