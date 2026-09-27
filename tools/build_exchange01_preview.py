"""Synthetic exchange views built through World Core, never from a user save."""
import gc
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def build():
    from server.world_core.simulation import Simulation
    from server.world_core.wired import process_wired_message_acknowledgement
    from server.world_core.player_view import build_player_snapshot as snapshot
    from server.world_core import code_exchange as ex, workshop as ws, network_conflict as net
    sim = Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001","PLAYER_1",sim.minute)
    def place(where):
        with net.connection() as c: c.execute("UPDATE agents SET location=? WHERE id='PLAYER_1'",(where,))
    counter = 0
    def act(action,**data):
        nonlocal counter
        counter += 1
        return ex.perform_exchange_action("PLAYER_1",action,data,f"exchange_preview_{counter:04}")
    place("APARTMENT")
    states = {"unknown":snapshot()}
    place("NIGHTCLUB")
    states["contact"] = act("CONTACT",peer="RYOKO")
    states["club"] = snapshot()
    place("CAFE")
    states["cafe"] = snapshot()
    act("CONTACT",peer="KISSA_TECH")
    place("APARTMENT")
    states["missing"] = snapshot()
    with net.connection() as c:
        c.execute("UPDATE simulation_state SET minute=1010 WHERE id=1")
        ws._grant(c,"PLAYER_1","event_KISSA_000001","CODE","buffer","Kissa · torneo 1 · primer puesto",1000)
    states["ready"] = snapshot()
    with net.connection() as c: c.execute("UPDATE workshop_players SET contract='NOEMA' WHERE actor='PLAYER_1'")
    states["blocked"] = snapshot()
    with net.connection() as c: c.execute("UPDATE workshop_players SET contract='INDEPENDENT' WHERE actor='PLAYER_1'")
    states["first"] = act("ACCEPT",offer="ryoko_scan_v1",asset="event_KISSA_000001")
    states["received"] = snapshot()
    with net.connection() as c: c.execute("UPDATE simulation_state SET minute=1030 WHERE id=1")
    act("ACCEPT",offer="kissa_shield_v1",asset="exchange_ryoko_scan_v1")
    states["history"] = snapshot()
    return states


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="lain-exchange-preview-") as scratch:
        os.environ.update(LAIN_WORLD_DB=str(Path(scratch)/"world.db"),
            LAIN_CODE_EXCHANGE="1",LAIN_CAFE_EVENTS="1",LAIN_WORKSHOP="1",
            LAIN_CORPORATION="1",LAIN_CIRCLES="1",LAIN_NOEMA="1",LAIN_CHAPTER_ONE="1",
            LAIN_LLM_ENABLED="0",LAIN_PROLOGUE_ENABLED="0",LAIN_CITY_RESIDENTS_ENABLED="1",
            LAIN_MEMORY_SEMANTIC="0",LAIN_REALITY_GENERATION="0",LAIN_ARCADE_CATALOG="1")
        (ROOT/"client/tools/fixtures/exchange01.json").write_text(json.dumps(build(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        gc.collect()
        print("EXCHANGE01_FIXTURE_OK")
