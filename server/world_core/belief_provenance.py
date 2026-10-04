import json

from dataclasses import dataclass

from .database import get_connection

from .models import SituationBelief


MATERIAL_CONFIDENCE_CHANGE = 0.10


@dataclass
class BeliefRevision:

    id: int

    agent_id: str
    situation_id: str

    minute: int

    revision_type: str

    previous_claim: dict | None
    new_claim: dict

    previous_source: str | None
    new_source: str

    previous_confidence: float | None
    new_confidence: float

    supporting_sources: list[str]
    opposing_sources: list[str]

    reason: str


def initialize_belief_provenance():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            belief_revisions (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                agent_id TEXT NOT NULL,
                situation_id TEXT NOT NULL,

                minute INTEGER NOT NULL,

                revision_type TEXT NOT NULL,

                previous_claim TEXT,
                new_claim TEXT NOT NULL,

                previous_source TEXT,
                new_source TEXT NOT NULL,

                previous_confidence REAL,
                new_confidence REAL NOT NULL,

                supporting_sources TEXT NOT NULL,
                opposing_sources TEXT NOT NULL,

                reason TEXT NOT NULL,

                fingerprint TEXT NOT NULL UNIQUE
            )
            """
        )

        conn.commit()


def claim_payload(
    belief: SituationBelief,
) -> dict:

    return {
        "type": belief.believed_type,
        "location": belief.believed_location,
        "subject_id": belief.believed_subject_id,
        "status": belief.believed_status,
    }


def claims_match(
    left: SituationBelief,
    right: SituationBelief,
) -> bool:

    return (
        claim_payload(left)
        == claim_payload(right)
    )


def classify_revision(
    previous: SituationBelief | None,
    new: SituationBelief,
) -> str | None:

    if previous is None:
        return "INITIALIZED"

    if not claims_match(
        previous,
        new,
    ):
        return "CLAIM_CHANGED"

    if previous.source != new.source:
        return "SOURCE_CHANGED"

    confidence_delta = abs(
        new.confidence
        - previous.confidence
    )

    if confidence_delta >= MATERIAL_CONFIDENCE_CHANGE:
        return "CONFIDENCE_SHIFT"

    return None


def provenance_sources(
    new: SituationBelief,
    hypotheses: list[SituationBelief],
) -> tuple[list[str], list[str]]:

    supporting = sorted(
        {
            hypothesis.source
            for hypothesis in hypotheses
            if claims_match(
                hypothesis,
                new,
            )
        }
    )

    opposing = sorted(
        {
            hypothesis.source
            for hypothesis in hypotheses
            if not claims_match(
                hypothesis,
                new,
            )
        }
    )

    return (
        supporting,
        opposing,
    )


def build_reason(
    revision_type: str,
    previous: SituationBelief | None,
    new: SituationBelief,
    supporting_sources: list[str],
    opposing_sources: list[str],
) -> str:

    if revision_type == "INITIALIZED":

        return (
            "Working belief initialized "
            f"from {new.source} "
            f"with confidence "
            f"{new.confidence:.2f}"
        )

    if revision_type == "CLAIM_CHANGED":

        return (
            "Dominant claim changed; "
            f"{new.source} now supports "
            f"{new.believed_location}. "
            f"Support={supporting_sources}; "
            f"opposition={opposing_sources}"
        )

    if revision_type == "SOURCE_CHANGED":

        return (
            "Dominant source changed "
            f"from {previous.source} "
            f"to {new.source} "
            "without changing the claim"
        )

    direction = (
        "increased"
        if new.confidence > previous.confidence
        else "decreased"
    )

    return (
        f"Working confidence {direction} "
        f"from {previous.confidence:.2f} "
        f"to {new.confidence:.2f}. "
        f"Support={supporting_sources}; "
        f"opposition={opposing_sources}"
    )


def record_belief_revision(
    previous: SituationBelief | None,
    new: SituationBelief,
    hypotheses: list[SituationBelief],
    minute: int,
) -> bool:

    revision_type = classify_revision(
        previous=previous,
        new=new,
    )

    if revision_type is None:
        return False

    supporting_sources, opposing_sources = (
        provenance_sources(
            new=new,
            hypotheses=hypotheses,
        )
    )

    previous_claim = (
        None
        if previous is None
        else claim_payload(previous)
    )

    new_claim = claim_payload(new)

    reason = build_reason(
        revision_type=revision_type,
        previous=previous,
        new=new,
        supporting_sources=supporting_sources,
        opposing_sources=opposing_sources,
    )

    previous_claim_json = (
        None
        if previous_claim is None
        else json.dumps(
            previous_claim,
            sort_keys=True,
        )
    )

    new_claim_json = json.dumps(
        new_claim,
        sort_keys=True,
    )

    fingerprint = "|".join(
        [
            new.agent_id,
            new.situation_id,
            str(minute),
            revision_type,
            previous_claim_json or "NONE",
            new_claim_json,
            previous.source if previous else "NONE",
            new.source,
            (
                f"{previous.confidence:.6f}"
                if previous
                else "NONE"
            ),
            f"{new.confidence:.6f}",
        ]
    )

    initialize_belief_provenance()

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO belief_revisions (

                agent_id,
                situation_id,
                minute,
                revision_type,
                previous_claim,
                new_claim,
                previous_source,
                new_source,
                previous_confidence,
                new_confidence,
                supporting_sources,
                opposing_sources,
                reason,
                fingerprint
            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                new.agent_id,
                new.situation_id,
                minute,
                revision_type,
                previous_claim_json,
                new_claim_json,
                previous.source if previous else None,
                new.source,
                previous.confidence if previous else None,
                new.confidence,
                json.dumps(supporting_sources),
                json.dumps(opposing_sources),
                reason,
                fingerprint,
            ),
        )

        conn.commit()

        return cursor.rowcount > 0


def list_belief_revisions(
    agent_id: str,
    situation_id: str,
) -> list[BeliefRevision]:

    initialize_belief_provenance()

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                agent_id,
                situation_id,
                minute,
                revision_type,
                previous_claim,
                new_claim,
                previous_source,
                new_source,
                previous_confidence,
                new_confidence,
                supporting_sources,
                opposing_sources,
                reason

            FROM belief_revisions

            WHERE agent_id = ?
              AND situation_id = ?

            ORDER BY id
            """,
            (
                agent_id,
                situation_id,
            ),
        ).fetchall()

    return [
        BeliefRevision(
            id=row[0],
            agent_id=row[1],
            situation_id=row[2],
            minute=row[3],
            revision_type=row[4],
            previous_claim=(
                json.loads(row[5])
                if row[5]
                else None
            ),
            new_claim=json.loads(row[6]),
            previous_source=row[7],
            new_source=row[8],
            previous_confidence=row[9],
            new_confidence=row[10],
            supporting_sources=json.loads(row[11]),
            opposing_sources=json.loads(row[12]),
            reason=row[13],
        )
        for row in rows
    ]
