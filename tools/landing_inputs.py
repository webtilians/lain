"""Real game text for the download page's captures (client/tools/capture_landing.gd).

    python tools/landing_inputs.py <folder>

Plays a new player through the start of the prologue in a throwaway world, with the
server's own code and no AI, and writes:
- session.json: the oscilloscope of Capa 01 in the school's cabinet, as the shell prints it;
- ryoko.json: Ryoko's first reply in the club (speaker, text, mood, choices).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    folder = Path((argv or sys.argv[1:])[0])
    folder.mkdir(parents=True, exist_ok=True)
    # SQLite may still hold the throwaway world open on Windows when the folder goes.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:
        os.environ["LAIN_WORLD_DB"] = str(Path(scratch) / "landing.db")
        for flag in ("LAIN_LAYER_ONE", "LAIN_LAYER_THREE", "LAIN_PROLOGUE_ENABLED", "LAIN_CITY_RESIDENTS_ENABLED",
                     "LAIN_CORPORATION"):
            os.environ[flag] = "1"
        os.environ["LAIN_LLM_ENABLED"] = "0"
        sys.path.insert(0, str(ROOT))
        from server.world_core import database, layer_one, layer_three
        from server.world_core.prologue import submit_terminal_command, talk_to_prologue_npc
        from server.world_core.simulation import Simulation
        from server.world_core.wired import process_wired_message_acknowledgement
        from tests.test_chapter_one import move  # the same walk through the city as the tests
        from tests.test_layer_three import PLAYER

        database.initialize_database()
        sim = Simulation()
        move(sim, "SCHOOL_LAB")
        talk_to_prologue_npc(PLAYER, "PROFESSOR", sim.minute, "ASK_STUDENT")
        move(sim, "NIGHTCLUB")
        ryoko = {"INTRO": talk_to_prologue_npc(PLAYER, "RYOKO", sim.minute, "INTRO")}
        talk_to_prologue_npc(PLAYER, "RYOKO", sim.minute, "ASK_ADDRESS")
        move(sim, "APARTMENT")
        submit_terminal_command(PLAYER, "telnet wired 23", sim.minute)
        process_wired_message_acknowledgement("MSG_BOOTSTRAP_001", PLAYER, sim.minute)
        move(sim, "SCHOOL_LAB")
        screens = []
        for pair in ("naranja", "verde"):
            result = layer_three.run_shell(PLAYER, layer_one.CABINET, "/", f"scope {pair}", sim.minute)
            screens.append({key: result[key] for key in ("output", "hostname", "cwd")} | {"command": f"scope {pair}"})
        # The pair the cut cable's signal is on: the one with a busy line.
        session = [max(screens, key=lambda screen: screen["output"].count("¯"))]
        (folder / "session.json").write_text(json.dumps(session, ensure_ascii=False, indent=1), encoding="utf-8")
        (folder / "ryoko.json").write_text(json.dumps(ryoko, ensure_ascii=False, indent=1), encoding="utf-8")
    print(folder / "session.json", folder / "ryoko.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
