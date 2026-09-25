"""Public render fixtures, produced by real conflict actions in a temporary DB."""
import gc
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def build():
    from server.world_core.simulation import Simulation
    from server.world_core.wired import process_wired_message_acknowledgement
    from server.world_core.player_view import build_player_snapshot
    from server.world_core import network_conflict as net
    sim=Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001","PLAYER_1",sim.minute)
    views=[]
    counter=0

    def action(kind,relay):
        nonlocal counter
        counter+=1
        return net.perform_network_action("PLAYER_1",kind,relay,"",f"preview_{counter:06}")

    def move(location,minute):
        with net.connection() as c:
            c.execute("UPDATE agents SET location=? WHERE id='PLAYER_1'",(location,))
            c.execute("UPDATE simulation_state SET minute=? WHERE id=1",(minute,))
        net.advance_conflict(minute)

    def view(name,mode="scene",result=None):
        views.append({"name":name,"mode":mode,"result":result,"state":build_player_snapshot()})

    move("STATION",10)
    view("station-unknown","dialogue",action("OPEN","RELAY_STATION"))
    action("INSPECT","RELAY_STATION")
    view("station-claim","dialogue",action("CLAIM","RELAY_STATION"))
    view("station-intervention")
    action("INSPECT","RELAY_STATION")
    view("operative-proof","personnel",action("TALK","RELAY_STATION"))
    view("network-journal","journal")
    view("operative-exposed","personnel",action("EXPOSE","RELAY_STATION"))
    move("SCHOOL_LAB",20)
    action("INSPECT","RELAY_SCHOOL")
    action("CLAIM","RELAY_SCHOOL")
    view("school-intervention")
    move("VIDEO_CLUB",30)
    action("INSPECT","RELAY_VIDEO")
    action("CLAIM","RELAY_VIDEO")
    view("video-intervention")
    move("APARTMENT",40)
    view("home-terminal","home")
    return views


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="lain-conflict-preview-") as scratch:
        os.environ.update(LAIN_WORLD_DB=str(Path(scratch)/"preview.db"),LAIN_CORPORATION="1",
            LAIN_LLM_ENABLED="0",LAIN_PROLOGUE_ENABLED="0",LAIN_CITY_RESIDENTS_ENABLED="1",
            LAIN_CHAPTER_ONE="1",LAIN_MEMORY_SEMANTIC="0",LAIN_REALITY_GENERATION="0")
        views=build()
        destination=ROOT/"client/tools/fixtures/conflict01.json"
        destination.write_text(json.dumps(views,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"CONFLICT01_FIXTURE_OK views={len(views)}")
        gc.collect()
