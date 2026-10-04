"""Generate synthetic public snapshots via the same actions as the real client."""
import gc
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build():
    from server.world_core.simulation import Simulation
    from server.world_core.wired import process_wired_message_acknowledgement
    from server.world_core.player_view import build_player_snapshot
    from server.world_core import network_conflict as net

    sim = Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001", "PLAYER_1", sim.minute)
    count = 0

    def place(location):
        with net.connection() as c:
            c.execute("UPDATE agents SET location=? WHERE id='PLAYER_1'", (location,))

    def act(action, relay, faction="KAGAMI"):
        nonlocal count
        count += 1
        return net.perform_network_action(
            "PLAYER_1", action, relay, "", f"preview_noema_{count:04}", faction)

    views = []
    for location, relay in [("STATION", "RELAY_STATION"), ("SCHOOL_LAB", "RELAY_SCHOOL"),
                            ("VIDEO_CLUB", "RELAY_VIDEO")]:
        place(location)
        result = act("TALK", relay, "NOEMA")
        views.append(dict(name="cover-"+location.lower(), mode="physical",
                          state=build_player_snapshot(), result=result))
    place("SCHOOL_LAB")
    act("INSPECT", "RELAY_SCHOOL")
    result = act("OPEN", "RELAY_SCHOOL")
    views.append(dict(name="two-controllers", mode="cabinet",
                      state=build_player_snapshot(), result=result))
    act("CLAIM", "RELAY_SCHOOL")
    with net.connection() as c:
        c.execute("UPDATE simulation_state SET minute=10 WHERE id=1")
    act("CLAIM", "RELAY_SCHOOL", "NOEMA")
    intercepted = act("INSPECT", "RELAY_SCHOOL")
    views.append(dict(name="intercepted-orders", mode="dialogue",
                      state=build_player_snapshot(), result=intercepted))
    views.append(dict(name="two-operations", mode="journal",
                      state=build_player_snapshot(), result={}))
    result = act("TALK", "RELAY_SCHOOL", "NOEMA")
    views.append(dict(name="records-proof", mode="dialogue",
                      state=build_player_snapshot(), result=result))
    result = act("EXPOSE", "RELAY_SCHOOL", "NOEMA")
    views.append(dict(name="noema-exposed", mode="exposed",
                      state=build_player_snapshot(), result=result))
    place("APARTMENT")
    views.append(dict(name="pc-two-corporations", mode="pc",
                      state=build_player_snapshot(), result={}))
    return views


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="lain-noema-preview-") as scratch:
        os.environ.update(
            LAIN_WORLD_DB=str(Path(scratch)/"preview.db"), LAIN_NOEMA="1",
            LAIN_CORPORATION="1", LAIN_WORKSHOP="1", LAIN_LLM_ENABLED="0",
            LAIN_PROLOGUE_ENABLED="0", LAIN_CITY_RESIDENTS_ENABLED="1",
            LAIN_CHAPTER_ONE="1", LAIN_MEMORY_SEMANTIC="0", LAIN_REALITY_GENERATION="0")
        (ROOT/"client/tools/fixtures/noema01.json").write_text(
            json.dumps(build(), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        gc.collect()
        print("NOEMA01_FIXTURE_OK")
