from fastapi import (
    FastAPI,
    HTTPException,
)

from pydantic import (
    BaseModel,
)

from server.world_core.action_queue import (
    queue_action,
)

from server.world_core.player_view import (
    PLAYER_ID,
    build_player_snapshot,
)

from server.world_core.wired import (
    process_wired_message_acknowledgement,
)

from server.world_core.simulation import (
    Simulation,
)

from server.world_core.player_conversation import (
    start_player_conversation,
    reply_to_player_conversation,
    pause_player_conversation,
)


app = FastAPI(
    title="LAIN World API",
    version="0.1.0",
)

_runtime: Simulation | None = None


def get_runtime() -> Simulation:

    global _runtime

    if _runtime is None:

        _runtime = Simulation()

    return _runtime


class PlayerStepRequest(
    BaseModel
):

    action: str
    target: str


class PlayerConversationReply(BaseModel):
    choice_id: str
    after_turn_id: int


class PlayerConversationPause(BaseModel):
    interaction_id: str


def perform_player_step(
    action: str,
    target: str,
    simulation: Simulation | None = None,
):

    runtime = (
        simulation
        if simulation is not None
        else get_runtime()
    )

    action_id = queue_action(
        actor_id=PLAYER_ID,
        action=action,
        target=target,
        source="GODOT_CLIENT",
    )

    action_results = runtime.tick()

    action_result = action_results.get(
        action_id,
        {
            "accepted": False,
            "action": action,
            "target": target,
            "reason": "ACTION_NOT_RESOLVED",
        },
    )

    return {
        "action_id": action_id,
        "action_result": action_result,
        "state": build_player_snapshot(
            PLAYER_ID
        ),
    }


def acknowledge_player_message(
    message_id: str,
):

    runtime = get_runtime()

    result = process_wired_message_acknowledgement(
        message_id=message_id,
        player_id=PLAYER_ID,
        minute=runtime.minute,
    )

    return {
        "effect": result,
        "state": build_player_snapshot(
            PLAYER_ID
        ),
    }


@app.get(
    "/health"
)
def health():

    return {
        "status": "ok",
    }


@app.get(
    "/api/v1/player/state"
)
def player_state():

    get_runtime()

    return build_player_snapshot(
        PLAYER_ID
    )


@app.post(
    "/api/v1/player/step"
)
def player_step(
    request: PlayerStepRequest,
):

    try:

        return perform_player_step(
            action=request.action,
            target=request.target,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post(
    "/api/v1/player/messages/{message_id}/ack"
)
def player_message_ack(
    message_id: str,
):

    try:
        return acknowledge_player_message(
            message_id
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )


@app.post(
    "/api/v1/player/conversations/{actor_id}/start"
)
def player_conversation_start(
    actor_id: str,
):
    runtime = get_runtime()

    try:
        return start_player_conversation(
            actor_id=actor_id,
            minute=runtime.minute,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )


@app.post(
    "/api/v1/player/conversations/{actor_id}/reply"
)
def player_conversation_reply(
    actor_id: str,
    request: PlayerConversationReply,
):
    runtime = get_runtime()

    try:
        return reply_to_player_conversation(
            actor_id=actor_id,
            choice_id=request.choice_id,
            after_turn_id=request.after_turn_id,
            minute=runtime.minute,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )


@app.post("/api/v1/player/conversations/{actor_id}/pause")
def player_conversation_pause(
    actor_id: str,
    request: PlayerConversationPause,
):
    runtime = get_runtime()
    try:
        return pause_player_conversation(
            actor_id=actor_id,
            interaction_id=request.interaction_id,
            minute=runtime.minute,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
