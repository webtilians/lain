from fastapi import FastAPI

from .core import WorldCore


app = FastAPI(
    title="Lain World Core",
    version="0.1.0",
)

world = WorldCore()


@app.get("/")
def root():
    return {
        "name": "Lain World Core",
        "version": "0.1.0",
        "status": "online",
    }


@app.get("/world")
def get_world():
    state = world.get_state()

    return {
        "signal": state.signal,
        "stability": state.stability,
        "connection": state.connection,
    }


@app.post("/debug/event")
def debug_event(
    signal: float = 0,
    stability: float = 0,
    connection: float = 0,
):
    state = world.apply_event(
        signal_delta=signal,
        stability_delta=stability,
        connection_delta=connection,
    )

    return {
        "signal": state.signal,
        "stability": state.stability,
        "connection": state.connection,
    }