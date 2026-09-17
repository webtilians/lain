from .database import load_world_state, save_world_state
from .models import WorldState


class WorldCore:

    def __init__(self):
        self.state = load_world_state()

    def get_state(self) -> WorldState:
        return self.state

    def apply_event(
        self,
        signal_delta: float = 0.0,
        stability_delta: float = 0.0,
        connection_delta: float = 0.0,
    ) -> WorldState:

        self.state.signal += signal_delta
        self.state.stability += stability_delta
        self.state.connection += connection_delta

        self.state.clamp()

        save_world_state(self.state)

        return self.state