"""Synthetic cross-runtime rule traces and playable PC views; never a user save."""
import gc
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
WIN="RRRRRDDDLLDLLDL"


def build():
    from server.world_core.simulation import Simulation
    from server.world_core.wired import process_wired_message_acknowledgement
    from server.world_core.player_view import build_player_snapshot as snapshot
    from server.world_core import signal_snake as snake, cafe_events as ev, workshop as ws, network_conflict as net
    sim=Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001","PLAYER_1",sim.minute)
    def place(where):
        with net.connection() as c: c.execute("UPDATE agents SET location=? WHERE id='PLAYER_1'",(where,))
    def clock(minute):
        with net.connection() as c: c.execute("UPDATE simulation_state SET minute=? WHERE id=1",(minute,))
        ev.advance_events(minute)
    counter=0
    def act(system,verb,**data):
        nonlocal counter
        counter+=1
        call=ws.perform_workshop_action if system=="practice" else ev.perform_event_action
        return call("PLAYER_1",verb,data,f"arcade_preview_{counter:04}")
    states={"calendar":snapshot()}
    place("CAFE")
    states["cafe"]=snapshot()
    states["practice_run"]=act("practice","ARCADE_START",game="signal_snake")
    states["practice"]=snapshot()
    states["practice_result"]=act("practice","ARCADE_FINISH",run_id=states["practice_run"]["run_id"],moves=WIN)
    states["practice_won"]=snapshot()
    clock(ev.LEAD+ev.PERIOD)
    states["event_run"]=act("event","START",event="KISSA_000002")
    states["event"]=snapshot()
    states["event_result"]=act("event","FINISH",run_id=states["event_run"]["run_id"],moves=WIN)
    clock(ev.LEAD+ev.PERIOD+ev.DURATION)
    states["closed"]=snapshot()
    states["traces"]=[]
    for variant in range(4):
        layout=snake.board(variant)
        for count in (3,4,6):
            path=snake.npc_route(variant,count)
            states["traces"].append({"board":layout,"moves":path,
                "states":[snake.replay(path[:i],layout) for i in range(len(path)+1)]})
    # The model must also allow stepping into a departing tail and skip occupied food.
    layout=snake.board()
    layout["snake"]=[[1,1],[1,2],[0,2],[0,1]]
    layout["foods"]=[[1,1],[1,2],[0,2],[0,1],[3,1]]
    states["traces"].append({"board":layout,"moves":"L",
        "states":[snake.replay("",layout),snake.replay("L",layout)]})
    return states


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="lain-arcade-preview-") as scratch:
        os.environ.update(LAIN_WORLD_DB=str(Path(scratch)/"world.db"),
            LAIN_ARCADE_CATALOG="1",LAIN_CAFE_EVENTS="1",LAIN_WORKSHOP="1",
            LAIN_CORPORATION="1",LAIN_CIRCLES="1",LAIN_NOEMA="1",LAIN_CHAPTER_ONE="1",
            LAIN_LLM_ENABLED="0",LAIN_PROLOGUE_ENABLED="0",LAIN_CITY_RESIDENTS_ENABLED="1",
            LAIN_MEMORY_SEMANTIC="0",LAIN_REALITY_GENERATION="0")
        (ROOT/"client/tools/fixtures/arcade01.json").write_text(json.dumps(build(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        gc.collect()
        print("ARCADE01_FIXTURE_OK")
