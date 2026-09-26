"""Public UI fixtures made by World Core in a disposable, synthetic save."""
import gc
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def build():
    from server.world_core.simulation import Simulation
    from server.world_core.wired import process_wired_message_acknowledgement
    from server.world_core.player_view import build_player_snapshot
    from server.world_core import circles as cs, workshop as ws, network_conflict as net
    from server.world_core.code_lab import LIFE_HINT
    sim = Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001","PLAYER_1",sim.minute)
    counter = 0
    def place(where):
        with net.connection() as c: c.execute("UPDATE agents SET location=? WHERE id='PLAYER_1'",(where,))
    def act(system, action, **data):
        nonlocal counter
        counter += 1
        call = cs.perform_circle_action if system=="circle" else ws.perform_workshop_action
        return call("PLAYER_1",action,data,f"preview_circle_{counter:04}")
    place("APARTMENT")
    states = {"empty":build_player_snapshot()}
    act("circle","CREATE",name="El ruido de fondo")
    for ident in ["home_navi","first_connection"]:
        act("circle","CONTRIBUTE",id=ident,active=True)
    place("SCHOOL_LAB")
    act("workshop","LESSON")
    place("APARTMENT")
    act("workshop","TEST_LIFE",source=LIFE_HINT)
    act("workshop","DEVICE",id="life_matrix",active=True)
    for ident in ["life_matrix","life_shield"]:
        act("circle","CONTRIBUTE",id=ident,active=True)
    place("NIGHTCLUB")
    contact = act("circle","CONTACT",target="RYOKO")
    states.update(club=build_player_snapshot(),contact=contact)
    place("APARTMENT")
    act("circle","INVITE",target="RYOKO")
    place("CAFE")
    states["cafe"] = build_player_snapshot()
    act("circle","CONTACT",target="KISSA_TECH")
    run = act("workshop","ARCADE_START")
    act("workshop","ARCADE_FINISH",run_id=run["run_id"],moves="DDRDRRRRRDDDDR")
    place("APARTMENT")
    act("circle","INVITE",target="KISSA_TECH")
    program = 'use("routing")\nuse("shield")\nuse("scan")\n'
    assert act("circle","COMPILE",source=program)["passed"]
    states["active"] = build_player_snapshot()
    place("SCHOOL_LAB")
    net.perform_network_action("PLAYER_1","INSPECT","RELAY_SCHOOL","","circle_preview_inspect")
    net.perform_network_action("PLAYER_1","CLAIM","RELAY_SCHOOL","","circle_preview_claim","NOEMA")
    with net.connection() as c: c.execute("UPDATE simulation_state SET minute=10 WHERE id=1")
    states["defense"] = net.perform_network_action("PLAYER_1","PROGRAM_SHIELD","RELAY_SCHOOL","","circle_preview_shield")
    states["lab"] = build_player_snapshot()
    place("APARTMENT")
    states["wired"] = build_player_snapshot()
    act("circle","REMOVE",target="RYOKO")
    states["removed"] = build_player_snapshot()
    return states


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="lain-circles-preview-") as scratch:
        os.environ.update(LAIN_WORLD_DB=str(Path(scratch)/"preview.db"),LAIN_CIRCLES="1",
            LAIN_WORKSHOP="1",LAIN_CORPORATION="1",LAIN_NOEMA="1",LAIN_CHAPTER_ONE="1",
            LAIN_LLM_ENABLED="0",LAIN_PROLOGUE_ENABLED="0",LAIN_CITY_RESIDENTS_ENABLED="1",
            LAIN_MEMORY_SEMANTIC="0",LAIN_REALITY_GENERATION="0")
        (ROOT/"client/tools/fixtures/circles01.json").write_text(
            json.dumps(build(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        gc.collect()
        print("CIRCLES01_FIXTURE_OK")
