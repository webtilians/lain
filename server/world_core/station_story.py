from .beliefs import load_belief

from .database import get_connection

from .messages import initialize_messages


FOLLOWUP_MESSAGE_ID = "MSG_STATION_001"


def ensure_station_followup(
    player_id: str,
    minute: int,
) -> bool:

    if player_id != "PLAYER_1":
        return False

    # Comprobamos que el jugador haya ejecutado
    # OBSERVE sobre NODE_07.

    with get_connection() as conn:

        observation = conn.execute(
            """
            SELECT 1
            FROM events
            WHERE actor_id = ?
              AND action = 'OBSERVE'
              AND target = 'NODE_07'
            LIMIT 1
            """,
            (player_id,),
        ).fetchone()

    if observation is None:
        return False

    # No basta con haber recibido la pista
    # del Wired: necesitamos evidencia directa.

    belief = load_belief(
        player_id,
        "NODE_07",
    )

    if belief is None:
        return False

    if belief.source != "DIRECT_PERCEPTION":
        return False

    initialize_messages()

    # Creamos un único mensaje persistente.

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO world_messages (
                id,
                recipient_id,
                sender_id,
                sender_label,
                subject,
                body,
                created_minute,
                visible_from_minute,
                read,
                acknowledged
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                FOLLOWUP_MESSAGE_ID,
                player_id,
                None,
                "unknown@wired",
                "YOU WERE SEEN",
                (
                    "HAS VISTO LA SEÑAL.\n\n"
                    "ALGUIEN HA VISTO QUE "
                    "LA HAS VISTO.\n\n"
                    "NO VUELVAS POR EL "
                    "MISMO CAMINO."
                ),
                minute,
                minute,
            ),
        )

        conn.commit()

        return cursor.rowcount == 1