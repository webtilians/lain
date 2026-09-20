from server.api import (
    perform_player_step,
)

from server.world_core.database import (
    get_connection,
    save_agent,
)

from server.world_core.simulation import (
    Simulation,
)


def test_investigate_is_accepted_at_station():

    simulation = Simulation()

    simulation.player.location = "STATION"
    simulation.player.energy = 1.0

    save_agent(
        simulation.player
    )

    response = perform_player_step(
        action="INVESTIGATE",
        target="NODE_07",
        simulation=simulation,
    )

    result = response["action_result"]

    assert result["accepted"] is True
    assert result["action"] == "INVESTIGATE"
    assert result["target"] == "NODE_07"
    assert response["state"]["player"]["energy"] < 1.0


def test_investigate_rejected_without_energy():

    simulation = Simulation()

    simulation.player.location = "STATION"
    simulation.player.energy = 0.0

    save_agent(
        simulation.player
    )

    response = perform_player_step(
        action="INVESTIGATE",
        target="NODE_07",
        simulation=simulation,
    )

    result = response["action_result"]

    assert result["accepted"] is False
    assert result["reason"] == "NOT_ENOUGH_ENERGY"

    with get_connection() as conn:

        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM events
            WHERE actor_id = 'PLAYER_1'
              AND action = 'INVESTIGATE'
              AND target = 'NODE_07'
            """
        ).fetchone()[0]

    assert count == 0


def test_investigate_rejected_from_apartment():

    simulation = Simulation()

    simulation.player.location = "APARTMENT"
    simulation.player.energy = 1.0

    save_agent(
        simulation.player
    )

    response = perform_player_step(
        action="INVESTIGATE",
        target="NODE_07",
        simulation=simulation,
    )

    result = response["action_result"]

    assert result["accepted"] is False
    assert result["reason"] == "TARGET_NOT_PRESENT"


def test_player_contact_uses_conversation_topic():
    simulation = Simulation()

    simulation.player.location = "STATION"
    simulation.player.energy = 1.0
    simulation.k.agent.location = "STATION"

    save_agent(simulation.player)
    save_agent(simulation.k.agent)

    response = perform_player_step(
        action="CONTACT",
        target="AGENT_K",
        simulation=simulation,
    )

    assert response["action_result"]["accepted"] is True

    with get_connection() as conn:
        topic_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM interactions
            WHERE initiator_id = 'PLAYER_1'
              AND recipient_id = 'AGENT_K'
              AND topic = 'PLAYER_INITIATED_CONVERSATION'
            """
        ).fetchone()[0]

    assert topic_count >= 1