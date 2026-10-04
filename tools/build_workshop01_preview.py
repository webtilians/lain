"""Create public Godot fixtures through real World Core actions in a temporary save."""
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
    from server.world_core import workshop as ws, network_conflict as net
    from server.world_core.code_lab import LIFE_HINT
    sim=Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001","PLAYER_1",sim.minute)
    counter=0
    def place(location):
        with net.connection() as c:
            c.execute("UPDATE agents SET location=? WHERE id='PLAYER_1'",(location,))
    def act(action,**data):
        nonlocal counter
        counter+=1
        return ws.perform_workshop_action("PLAYER_1",action,data,f"preview_workshop_{counter:04}")
    place("CAFE")
    act("TECHNICIAN")
    start=act("ARCADE_START")
    cafe=build_player_snapshot()
    result=act("ARCADE_FINISH",run_id=start["run_id"],moves="DDRDRRRRRDDDDR")
    assert result["won"]
    place("SCHOOL_LAB")
    act("LESSON")
    place("APARTMENT")
    life=act("TEST_LIFE",source=LIFE_HINT)
    assert life["passed"]
    act("DEVICE",id="life_matrix",active=True)
    act("DEVICE",id="courier_interface",active=True)
    act("COMPILE",source='use("routing")\nuse("shield")\nuse("scan")\n')
    home=build_player_snapshot()
    place("SCHOOL_LAB")
    for action in ["INSPECT","CLAIM"]:
        counter+=1
        net.perform_network_action("PLAYER_1",action,"RELAY_SCHOOL","",f"preview_network_{counter:04}")
    with net.connection() as c: c.execute("UPDATE simulation_state SET minute=10 WHERE id=1")
    protected=net.perform_network_action("PLAYER_1","PROGRAM_SHIELD","RELAY_SCHOOL","","preview_protection_01")
    lab=build_player_snapshot()
    return {"home":home,"cafe":cafe,"arcade":start,"life":life,"lab":lab,"protection":protected}


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="lain-workshop-preview-") as scratch:
        os.environ.update(LAIN_WORLD_DB=str(Path(scratch)/"preview.db"),LAIN_CORPORATION="1",
            LAIN_WORKSHOP="1",LAIN_LLM_ENABLED="0",LAIN_PROLOGUE_ENABLED="0",
            LAIN_CITY_RESIDENTS_ENABLED="1",LAIN_CHAPTER_ONE="1",
            LAIN_MEMORY_SEMANTIC="0",LAIN_REALITY_GENERATION="0")
        destination=ROOT/"client/tools/fixtures/workshop01.json"
        destination.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        gc.collect()
        print("WORKSHOP01_FIXTURE_OK")
