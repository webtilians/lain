"""Synthetic UI fixtures from the authoritative tournament implementation."""
import gc
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build():
    from server.world_core import cafe_events as ev, network_conflict as net, workshop as ws
    from server.world_core.player_view import build_player_snapshot as snapshot
    from server.world_core.simulation import Simulation
    from server.world_core.wired import process_wired_message_acknowledgement
    from tests.test_cafe_events import route
    sim = Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001","PLAYER_1",sim.minute)
    def place(where):
        with net.connection() as c: c.execute("UPDATE agents SET location=? WHERE id='PLAYER_1'", (where,))
    def clock(now):
        with net.connection() as c: c.execute("UPDATE simulation_state SET minute=? WHERE id=1", (now,))
        ev.advance_events(now)
    counter = 0
    def act(action, **data):
        nonlocal counter
        counter += 1
        return ev.perform_event_action("PLAYER_1",action,data,f"events_preview_{counter:04}")
    states = {"upcoming":snapshot()}
    place("CAFE")
    clock(ev.LEAD)
    states["open"] = snapshot()
    run = act("START",event="KISSA_000001")
    states["run"] = run
    states["playing"] = snapshot()
    states["winning_moves"] = route(run["board"])
    states["result"] = act("FINISH",run_id=run["run_id"],moves=states["winning_moves"])
    clock(ev.LEAD+120)
    states["ranking"] = snapshot()
    clock(ev.LEAD+ev.DURATION)
    states["closed"] = snapshot()
    place("APARTMENT")
    ws.perform_workshop_action("PLAYER_1","COMPILE",{"source":'use("routing")\nuse("buffer")\n'},"preview_buffer_compile")
    states["reward"] = snapshot()
    place("CAFE")
    clock(ev.LEAD+ev.PERIOD)
    states["mirrored_run"] = act("START",event="KISSA_000002")
    states["mirrored"] = snapshot()
    return states


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="lain-events-preview-") as scratch:
        os.environ.update(LAIN_WORLD_DB=str(Path(scratch)/"preview.db"),LAIN_CAFE_EVENTS="1",
            LAIN_WORKSHOP="1",LAIN_CORPORATION="1",LAIN_CIRCLES="1",LAIN_NOEMA="1",LAIN_CHAPTER_ONE="1",
            LAIN_LLM_ENABLED="0",LAIN_PROLOGUE_ENABLED="0",LAIN_CITY_RESIDENTS_ENABLED="1",
            LAIN_MEMORY_SEMANTIC="0",LAIN_REALITY_GENERATION="0")
        (ROOT/"client/tools/fixtures/events01.json").write_text(
            json.dumps(build(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        gc.collect()
        print("EVENTS01_FIXTURE_OK")
