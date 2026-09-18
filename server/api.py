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

from server.world_core.simulation import (
    Simulation,
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

    runtime.tick()

    return {
        "action_id": action_id,
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
