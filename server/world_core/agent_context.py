from .database import get_connection
from .evidence import list_actor_beliefs
from .situation_beliefs import list_agent_situation_beliefs


class AgentContextBuilder:
    """Build the private, persisted context available to one agent."""

    def build(
        self,
        agent_id: str,
        interaction_id: str | None = None,
    ) -> dict:
        agent = self._load_agent(agent_id)

        context = {
            "identity": {
                "id": agent[0],
                "name": agent[1],
                "faction": agent[2],
                "controller_type": agent[5],
            },
            "situation": {
                "location": agent[3],
                "conversation_with": None,
            },
            "beliefs": {
                "nodes": self._node_beliefs(agent_id),
                "actors": self._actor_beliefs(agent_id),
                "situations": self._situation_beliefs(agent_id),
            },
            "memory": self._memories(agent_id),
            "goals": {
                "current": agent[4],
            },
            "conversation": None,
        }

        if interaction_id is not None:
            conversation = self._conversation(
                agent_id,
                interaction_id,
            )
            context["conversation"] = conversation
            context["situation"]["conversation_with"] = {
                "id": conversation["initiator_id"],
            }

        return context

    def _load_agent(self, agent_id: str):
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    name,
                    faction,
                    location,
                    goal,
                    controller_type
                FROM agents
                WHERE id = ?
                """,
                (agent_id,),
            ).fetchone()

        if row is None:
            raise ValueError("AGENT_NOT_FOUND")

        return row

    def _node_beliefs(
        self,
        agent_id: str,
    ) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    node_id,
                    believed_location,
                    believed_strength,
                    confidence,
                    source,
                    updated_minute
                FROM node_beliefs
                WHERE agent_id = ?
                ORDER BY node_id
                """,
                (agent_id,),
            ).fetchall()

        return [
            {
                "node_id": row[0],
                "location": row[1],
                "strength": row[2],
                "confidence": row[3],
                "source": row[4],
                "updated_minute": row[5],
            }
            for row in rows
        ]

    def _actor_beliefs(
        self,
        agent_id: str,
    ) -> list[dict]:
        return [
            {
                "subject_actor_id": belief.subject_actor_id,
                "belief_type": belief.belief_type,
                "confidence": belief.confidence,
                "source_evidence_id": belief.source_evidence_id,
                "updated_minute": belief.updated_minute,
            }
            for belief in list_actor_beliefs(agent_id)
        ]

    def _situation_beliefs(
        self,
        agent_id: str,
    ) -> list[dict]:
        return [
            {
                "situation_id": belief.situation_id,
                "type": belief.believed_type,
                "location": belief.believed_location,
                "subject_id": belief.believed_subject_id,
                "status": belief.believed_status,
                "severity": belief.believed_severity,
                "confidence": belief.confidence,
                "source": belief.source,
                "updated_minute": belief.updated_minute,
            }
            for belief in list_agent_situation_beliefs(agent_id)
        ]

    def _memories(
        self,
        agent_id: str,
    ) -> list[str]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT memory
                FROM agent_memory
                WHERE agent_id = ?
                ORDER BY id
                """,
                (agent_id,),
            ).fetchall()

        return [row[0] for row in rows]

    def _conversation(
        self,
        agent_id: str,
        interaction_id: str,
    ) -> dict:
        with get_connection() as conn:
            interaction = conn.execute(
                """
                SELECT
                    id,
                    initiator_id,
                    recipient_id,
                    topic,
                    status
                FROM interactions
                WHERE id = ?
                """,
                (interaction_id,),
            ).fetchone()

        if interaction is None:
            raise ValueError("INTERACTION_NOT_FOUND")

        if (
            interaction[2] != agent_id
            or interaction[1] != "PLAYER_1"
        ):
            raise ValueError("INTERACTION_NOT_AVAILABLE")

        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    speaker_id,
                    text,
                    source,
                    minute
                FROM player_conversation_turns
                WHERE interaction_id = ?
                ORDER BY id
                """,
                (interaction_id,),
            ).fetchall()

        return {
            "id": interaction[0],
            "initiator_id": interaction[1],
            "recipient_id": interaction[2],
            "topic": interaction[3],
            "status": interaction[4],
            "turns": [
                {
                    "id": row[0],
                    "speaker_id": row[1],
                    "text": row[2],
                    "source": row[3],
                    "minute": row[4],
                }
                for row in rows
            ],
        }
