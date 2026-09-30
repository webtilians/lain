from contextlib import asynccontextmanager, contextmanager, nullcontext
from typing import Annotated
import json
import re
from threading import Lock
import os
from threading import RLock
import time

from fastapi import (
    FastAPI,
    HTTPException,
    Header,
    Depends,
)

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictStr,
)

from server.world_core.action_queue import (
    queue_action,
    VALID_ACTIONS,
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
from server.world_core.realtime import WorldClock, world_clock_interval
from server.world_core import online
from server.world_core.database import get_connection
from server.world_core.models import ActionIntent
from server.world_core.messages import initial_message_id
from server.world_core.locations import LOCATION_GRAPH
from server.world_core.prologue import (
    talk_to_prologue_npc,
    submit_terminal_command,
)

from server.world_core.player_conversation import (
    start_player_conversation,
    reply_to_player_conversation,
    pause_player_conversation,
)
from server.world_core.free_conversation import (
    say_to_player_conversation,
)


_runtime: Simulation | None = None
_world_lock = RLock()
_clock: WorldClock | None = None


def get_runtime() -> Simulation:
    global _runtime
    with _world_lock:
        if _runtime is None:
            _runtime = Simulation()
        if online.enabled():
            _runtime.refresh_human_players()
        return _runtime


@asynccontextmanager
async def world_lifespan(_app: FastAPI):
    global _clock
    with online.world_host_lock() if online.enabled() else nullcontext():
        get_runtime()
        if online.enabled():
            online.initialize()
        # A single server-owned clock; GET /state never advances the world.
        if os.getenv("LAIN_WORLD_CLOCK", "1") == "1":
            _clock = WorldClock(get_runtime(), _world_lock, world_clock_interval())
            _clock.start()
        try:
            yield
        finally:
            if _clock is not None:
                _clock.stop()
                _clock = None


app = FastAPI(
    title="LAIN World API",
    version="0.1.0",
    lifespan=world_lifespan,
)


class PresenceRequest(BaseModel):
    model_config = {"extra": "forbid", "allow_inf_nan": False}
    location: str = Field(max_length=64)
    x: float
    y: float
    z: float
    yaw: float = 0
    dialogue: bool = False


class ChatRequest(BaseModel):
    model_config = {"extra": "forbid"}
    text: str = Field(min_length=1, max_length=240)


def authenticated_player(
    authorization: Annotated[str | None, Header()] = None,
    x_lain_client: Annotated[str | None, Header()] = None,
) -> str:
    if not online.enabled():
        return PLAYER_ID
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="PLAYER_ACCESS_REQUIRED")
    try:
        actor_id = online.authenticate(authorization[7:])
        online.connect(actor_id, x_lain_client)
        online.limit(actor_id, "api", 80, 5)
        return actor_id
    except ValueError as error:
        code = (
            429
            if str(error) == "PLEASE_WAIT"
            else 409 if str(error) == "PLAYER_ALREADY_CONNECTED" else 401
        )
        raise HTTPException(status_code=code, detail=str(error))


@app.post("/api/v1/online/presence")
def player_presence(
    request: PresenceRequest,
    player_id: Annotated[str, Depends(authenticated_player)],
    x_lain_client: Annotated[str, Header()],
):
    received_at = time.monotonic()
    if not online.enabled():
        raise HTTPException(status_code=404, detail="ONLINE_DISABLED")
    try:
        # Presence is cosmetic and never mutates the world, so it does not wait
        # behind a clock tick (which may call the LLM). A heartbeat delayed there
        # looked like a sprint and snapped the player back every tick.
        return online.heartbeat(
            player_id, x_lain_client, received_at=received_at, **request.model_dump()
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@app.post("/api/v1/online/chat")
def player_chat(
    request: ChatRequest, player_id: Annotated[str, Depends(authenticated_player)]
):
    if not online.enabled():
        raise HTTPException(status_code=404, detail="ONLINE_DISABLED")
    try:
        with _world_lock:
            return online.send_chat(player_id, request.text)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@app.post("/api/v1/online/leave")
def player_leave(
    player_id: Annotated[str, Depends(authenticated_player)],
    x_lain_client: Annotated[str, Header()],
):
    if not online.enabled():
        raise HTTPException(status_code=404, detail="ONLINE_DISABLED")
    online.disconnect(player_id, x_lain_client)
    return {"left": True}


_dialogue_locks = {}


@contextmanager
def dialogue_guard(player_id):
    if not online.enabled():
        with _world_lock:
            yield
        return
    with _world_lock:
        lock = _dialogue_locks.setdefault(player_id, Lock())
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="DIALOGUE_BUSY")
    try:
        yield
    finally:
        lock.release()


class PlayerStepRequest(BaseModel):

    model_config = {"extra": "forbid"}
    action: str = Field(max_length=32)
    target: str = Field(max_length=96)
    request_id: str = Field(default="", max_length=80)


class PlayerConversationReply(BaseModel):
    choice_id: str
    after_turn_id: int


class PlayerConversationPause(BaseModel):
    interaction_id: str


class PlayerConversationSay(BaseModel):
    text: str
    after_turn_id: int


class PrologueTalkRequest(BaseModel):
    choice: str = "INTRO"


class PrologueCommandRequest(BaseModel):
    command: str


class WorkshopActionRequest(BaseModel):
    model_config = {"extra": "forbid"}
    action: str = Field(max_length=32)
    data: dict[str, StrictStr | StrictBool] = Field(default_factory=dict, max_length=4)
    request_id: str = Field(min_length=8, max_length=80)


@app.post("/api/v1/workshop/action")
def workshop_action(
    request: WorkshopActionRequest,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    from server.world_core.workshop import perform_workshop_action

    with _world_lock:
        get_runtime()
        try:
            result = perform_workshop_action(
                player_id, request.action, request.data, request.request_id
            )
            return {"result": result, "state": build_player_snapshot(player_id)}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))


class CircleActionRequest(BaseModel):
    model_config = {"extra": "forbid"}
    action: str = Field(max_length=32)
    data: dict[str, StrictStr | StrictBool] = Field(default_factory=dict, max_length=2)
    request_id: str = Field(min_length=8, max_length=80)


class CafeEventRequest(BaseModel):
    model_config = {"extra": "forbid"}
    action: str = Field(max_length=16)
    data: dict[str, StrictStr] = Field(max_length=2)
    request_id: str = Field(min_length=8, max_length=80)


@app.post("/api/v1/cafe-events/action")
def cafe_event_action(
    request: CafeEventRequest,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    from server.world_core.cafe_events import perform_event_action

    with _world_lock:
        get_runtime()
        try:
            result = perform_event_action(
                player_id, request.action, request.data, request.request_id
            )
            return {"result": result, "state": build_player_snapshot(player_id)}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))


class ExchangeActionRequest(BaseModel):
    model_config = {"extra": "forbid"}
    action: str = Field(max_length=16)
    data: dict[str, StrictStr] = Field(max_length=2)
    request_id: str = Field(min_length=8, max_length=80)


@app.post("/api/v1/code-exchange/action")
def code_exchange_action(
    request: ExchangeActionRequest,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    from server.world_core.code_exchange import perform_exchange_action

    with _world_lock:
        get_runtime()
        try:
            result = perform_exchange_action(
                player_id, request.action, request.data, request.request_id
            )
            return {"result": result, "state": build_player_snapshot(player_id)}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))


@app.post("/api/v1/circles/action")
def circle_action(
    request: CircleActionRequest,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    from server.world_core.circles import perform_circle_action

    with _world_lock:
        get_runtime()
        try:
            result = perform_circle_action(
                player_id, request.action, request.data, request.request_id
            )
            return {"result": result, "state": build_player_snapshot(player_id)}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))


class NetworkActionRequest(BaseModel):
    model_config = {"extra": "forbid"}
    action: str = Field(max_length=32)
    relay: str = Field(max_length=64)
    rival: str = Field(default="", max_length=64)
    faction: str = Field(default="KAGAMI", max_length=16)
    request_id: str = Field(min_length=8, max_length=80)


@app.post("/api/v1/network/action")
def network_action(
    request: NetworkActionRequest,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    from server.world_core.network_conflict import perform_network_action

    with _world_lock:
        get_runtime()
        try:
            result = perform_network_action(
                player_id,
                request.action,
                request.relay,
                request.rival,
                request.request_id,
                request.faction,
            )
            return {"result": result, "state": build_player_snapshot(player_id)}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))


class ChapterActionRequest(BaseModel):
    action: str = Field(max_length=32)
    target: str = Field(default="", max_length=64)
    data: dict[str, str] = Field(default_factory=dict)
    request_id: str = Field(min_length=8, max_length=80)


@app.post("/api/v1/chapter-one/action")
def chapter_one_action(
    request: ChapterActionRequest,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    from server.world_core.chapter_one import perform_chapter_action

    with _world_lock:
        runtime = get_runtime()
        try:
            result = perform_chapter_action(
                player_id,
                request.action,
                request.target,
                request.data,
                runtime.minute,
                request.request_id,
            )
            return {"result": result, "state": build_player_snapshot(player_id)}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))


def perform_player_step(
    action: str,
    target: str,
    simulation: Simulation | None = None,
    player_id: str = PLAYER_ID,
):

    with _world_lock:
        runtime = simulation if simulation is not None else get_runtime()

        action_id = queue_action(
            actor_id=player_id,
            action=action,
            target=target,
            source="GODOT_CLIENT",
            # Online actions are resolved synchronously under the world lock.
            # Never leave them for the clock to replay after a partial failure.
            already_claimed=online.enabled(),
        )

        if online.enabled():
            action_results = runtime.resolve_intents(
                [
                    (
                        action_id,
                        ActionIntent(
                            actor_id=player_id,
                            action=action.upper(),
                            target=target,
                            source="GODOT_CLIENT",
                        ),
                    )
                ]
            )
            if action.upper() == "MOVE" and action_results.get(action_id, {}).get(
                "accepted"
            ):
                online.clear_location(player_id)
        else:
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
            "state": build_player_snapshot(player_id),
        }


def acknowledge_player_message(
    message_id: str,
    player_id: str = PLAYER_ID,
):

    with _world_lock:
        runtime = get_runtime()

        result = process_wired_message_acknowledgement(
            message_id=message_id,
            player_id=player_id,
            minute=runtime.minute,
        )

        return {
            "effect": result,
            "state": build_player_snapshot(player_id),
        }


@app.get("/health")
def health():

    return {
        "status": "ok",
    }


@app.get("/api/v1/player/state")
def player_state(
    x_lain_dialog_active: str | None = Header(default=None),
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):

    with _world_lock:
        get_runtime()
        # Ephemeral UI heartbeat only: never alter world.db on a GET.
        # A stale OPEN conversation by itself must not freeze the world.
        if x_lain_dialog_active == "1" and _clock is not None:
            _clock.note_player_dialogue_active()
        return build_player_snapshot(player_id)


@app.post("/api/v1/player/step")
def player_step(
    request: PlayerStepRequest,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):

    try:
        if online.enabled():
            return online_step(request, player_id)

        return perform_player_step(
            action=request.action, target=request.target, player_id=player_id
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


def online_step(request: PlayerStepRequest, player_id: str):
    """Do not tick the shared clock on player input; retry each action at most once."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request.request_id):
        raise HTTPException(status_code=400, detail="REQUEST_ID_REQUIRED")
    if request.action.upper() not in VALID_ACTIONS:
        raise HTTPException(status_code=400, detail="UNKNOWN_ACTION")
    command = json.dumps([request.action.upper(), request.target])
    with _world_lock:
        runtime = get_runtime()
        with get_connection() as conn:
            previous = conn.execute(
                "SELECT command,result FROM online_actions WHERE actor_id=? AND request_id=?",
                (player_id, request.request_id),
            ).fetchone()
            if previous:
                if previous[0] != command:
                    raise HTTPException(status_code=409, detail="REQUEST_ID_REUSED")
                if previous[1] is None:
                    raise HTTPException(
                        status_code=409, detail="ACTION_STATUS_UNCERTAIN_REFRESH"
                    )
                return {
                    **json.loads(previous[1]),
                    "state": build_player_snapshot(player_id),
                }
            online.limit(player_id, "step", 8, 10)
            person = runtime.all_agents[player_id]
            if (
                request.action.upper() == "MOVE"
                and request.target not in LOCATION_GRAPH.get(person.location, ())
            ):
                raise HTTPException(
                    status_code=409, detail="ADJACENT_LOCATION_REQUIRED"
                )
            if (
                request.action.upper()
                in {"REST", "INVESTIGATE", "STABILIZE", "AMPLIFY"}
                and conn.execute(
                    """SELECT 1 FROM events WHERE actor_id=? AND minute=?
                AND action IN ('REST','INVESTIGATE','STABILIZE','AMPLIFY') LIMIT 1""",
                    (player_id, runtime.minute),
                ).fetchone()
            ):
                raise HTTPException(status_code=429, detail="WAIT_WORLD_TICK")
            # An interrupted PENDING receipt is never executed again. The owner
            # can inspect the save; the player refreshes instead of duplicating effects.
            conn.execute(
                "INSERT INTO online_actions VALUES(?,?,?,NULL)",
                (player_id, request.request_id, command),
            )
        result = perform_player_step(request.action, request.target, runtime, player_id)
        receipt = {key: result[key] for key in ("action_id", "action_result")}
        with get_connection() as conn:
            conn.execute(
                "UPDATE online_actions SET result=? WHERE actor_id=? AND request_id=?",
                (json.dumps(receipt), player_id, request.request_id),
            )
        return result


@app.post("/api/v1/player/messages/{message_id}/ack")
def player_message_ack(
    message_id: str,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):

    try:
        return acknowledge_player_message(message_id, player_id=player_id)

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )


@app.post("/api/v1/player/conversations/{actor_id}/start")
def player_conversation_start(
    actor_id: str,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    with _world_lock:
        runtime = get_runtime()

        try:
            return start_player_conversation(
                actor_id=actor_id, minute=runtime.minute, player_id=player_id
            )

        except ValueError as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            )


@app.post("/api/v1/player/conversations/{actor_id}/reply")
def player_conversation_reply(
    actor_id: str,
    request: PlayerConversationReply,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    with dialogue_guard(player_id):
        runtime = get_runtime()

        try:
            return reply_to_player_conversation(
                actor_id=actor_id,
                choice_id=request.choice_id,
                after_turn_id=request.after_turn_id,
                minute=runtime.minute,
                player_id=player_id,
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
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    with _world_lock:
        runtime = get_runtime()
        try:
            return pause_player_conversation(
                actor_id=actor_id,
                interaction_id=request.interaction_id,
                minute=runtime.minute,
                player_id=player_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))


@app.post("/api/v1/player/conversations/{actor_id}/say")
def player_conversation_say(
    actor_id: str,
    request: PlayerConversationSay,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    with dialogue_guard(player_id):
        runtime = get_runtime()
        try:
            return say_to_player_conversation(
                actor_id=actor_id,
                text=request.text,
                after_turn_id=request.after_turn_id,
                minute=runtime.minute,
                player_id=player_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))


@app.post("/api/v1/prologue/talk/{npc_id}")
def prologue_talk(
    npc_id: str,
    request: PrologueTalkRequest,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    with _world_lock:
        runtime = get_runtime()
        try:
            result = talk_to_prologue_npc(
                player_id,
                npc_id,
                runtime.minute,
                request.choice,
            )
            return {"result": result, "state": build_player_snapshot(player_id)}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))


@app.post("/api/v1/prologue/terminal")
def prologue_terminal(
    request: PrologueCommandRequest,
    player_id: Annotated[str, Depends(authenticated_player)] = PLAYER_ID,
):
    with _world_lock:
        runtime = get_runtime()
        try:
            result = submit_terminal_command(
                player_id,
                request.command,
                runtime.minute,
            )
            if result["accepted"] or result.get("reason") == "ALREADY_CONNECTED":
                # A terminal connection is proven by the persisted stage.
                # If the server crashed between saving CONNECTED and the
                # initial Wired message, a replay repairs the half-finished
                # transition instead of stranding the player forever.
                result["connection"] = process_wired_message_acknowledgement(
                    message_id=initial_message_id(player_id),
                    player_id=player_id,
                    minute=runtime.minute,
                )
                result["accepted"] = True
                result["reason"] = "LINK_ESTABLISHED"
            return {"result": result, "state": build_player_snapshot(player_id)}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))
