"""Reality 0.3: opt-out, server-owned world clock, independent of player input.

One bounded World Core tick per interval. The API serializes world mutations
using the same RLock; the clock never accepts action payloads from clients.
A player-initiated OPEN conversation pauses autonomous ticks so an actor does
not walk away during a long LLM answer or dialogue. No catch-up after a pause.
"""
import os
from threading import Event, Thread

from .database import get_connection


def player_is_in_conversation() -> bool:
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='interactions'"
        ).fetchone()
        if exists is None:
            return False
        row = conn.execute(
            """SELECT 1 FROM interactions
               WHERE initiator_id='PLAYER_1'
                 AND topic='PLAYER_INITIATED_CONVERSATION'
                 AND status='OPEN' LIMIT 1"""
        ).fetchone()
    return row is not None


class WorldClock:
    def __init__(self, simulation, lock, interval: float = 8.0):
        if not 1.0 <= interval <= 120.0:
            raise ValueError("INVALID_WORLD_CLOCK_INTERVAL")
        self.simulation = simulation
        self.lock = lock
        self.interval = interval
        self._stop = Event()
        self._thread: Thread | None = None

    def tick_once(self) -> bool:
        """One independent world decision cycle; returns false when paused."""
        with self.lock:
            if player_is_in_conversation():
                return False
            self.simulation.tick()
            return True

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.tick_once()
            except Exception as error:
                # No dialogue text, private memory or credential in logs.
                print("WORLD CLOCK // TICK_FAILED_" + type(error).__name__, flush=True)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = Thread(
            target=self._run, name="lain-world-clock", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=3.0)
            self._thread = None


def world_clock_interval() -> float:
    # Explicit opt-out for headless development. The graphical game enables
    # autonomous advancement by default when the API server starts.
    return max(1.0, min(120.0, float(os.getenv("LAIN_WORLD_TICK_SECONDS", "8"))))
