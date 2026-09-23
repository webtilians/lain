"""Reality 0.3: opt-out, server-owned world clock, independent of player input.

One bounded World Core tick per interval. The API serializes world mutations
using the same RLock; the clock never accepts action payloads from clients.
Only a RECENT Godot dialogue heartbeat together with a verified OPEN
conversation pauses autonomous ticks. An old abandoned OPEN row cannot freeze
the whole world after a crash, scene change or a lost pause request.
The API lock separately prevents ticks during in-flight LLM replies.
No catch-up after a pause.
"""
import os
from threading import Event, Thread
from time import monotonic

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
        self._last_chat_heartbeat: float | None = None
        self._last_report: str | None = None

    def note_player_dialogue_active(self) -> None:
        """Called only when the game reports an actually visible NPC dialog."""
        self._last_chat_heartbeat = monotonic()

    def _report(self, status: str) -> None:
        if (os.getenv("LAIN_WORLD_TRACE") == "1"
                or os.getenv("LAIN_REALITY_TRACE") == "1"):
            # Avoid repetitive paused lines every 8 seconds.
            if status.startswith("PAUSED") and status == self._last_report:
                return
            print("WORLD CLOCK // " + status, flush=True)
            self._last_report = status

    def tick_once(self) -> bool:
        """One independent world decision cycle; returns false when paused."""
        with self.lock:
            recently_visible = (
                self._last_chat_heartbeat is not None
                and monotonic() - self._last_chat_heartbeat < 4.5
            )
            if recently_visible and player_is_in_conversation():
                self._report("PAUSED_ACTIVE_CHAT")
                return False
            if self._last_chat_heartbeat is not None and not recently_visible:
                self._report("RESUMED_AFTER_CHAT_HEARTBEAT_EXPIRED")
            self._last_chat_heartbeat = None if not recently_visible else self._last_chat_heartbeat
            self.simulation.tick()
            self._report("TICK_MINUTE_" + str(self.simulation.minute))
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
        print(f"WORLD CLOCK // STARTED interval={self.interval:g}s", flush=True)
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
            print("WORLD CLOCK // STOPPED", flush=True)


def world_clock_interval() -> float:
    # Explicit opt-out for headless development. The graphical game enables
    # autonomous advancement by default when the API server starts.
    return max(1.0, min(120.0, float(os.getenv("LAIN_WORLD_TICK_SECONDS", "8"))))
