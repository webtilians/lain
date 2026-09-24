"""Build public Godot fixtures by playing World Core in a disposable world.

Run from the repository root. No real save is read or modified, even when
LAIN_WORLD_DB is set. The fixed choices exercise one complete investigation.
"""
import json
import gc
import os
import sys
import tempfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build():
    from server.world_core import database
    from server.world_core import chapter_one as case
    from server.world_core.action_queue import queue_action
    from server.world_core.locations import LOCATION_GRAPH
    from server.world_core.player_view import build_player_snapshot
    from server.world_core.prologue import talk_to_prologue_npc, submit_terminal_command
    from server.world_core.simulation import Simulation
    from server.world_core.wired import process_wired_message_acknowledgement

    sim = Simulation()
    counter = 0
    views = []

    def move(destination):
        pending = deque([(sim.player.location, [])])
        seen = set()
        while pending:
            place, route = pending.popleft()
            if place == destination:
                for step in route:
                    aid = queue_action(actor_id=case.PLAYER, action="MOVE", target=step, source="GODOT_CLIENT")
                    assert sim.tick()[aid]["accepted"]
                return
            if place not in seen:
                seen.add(place)
                pending.extend((other, route+[other]) for other in LOCATION_GRAPH.get(place, ()) if other not in seen)
        raise RuntimeError("Unreachable location")

    def action(kind, target="", **data):
        nonlocal counter
        counter += 1
        return case.perform_chapter_action(case.PLAYER, kind, target, data, sim.minute, f"preview_{counter:06}")

    def view(name, at, result=None, mode="scene"):
        views.append(dict(name=name, at=at, result=result, mode=mode, state=build_player_snapshot()))

    move("SCHOOL_LAB")
    talk_to_prologue_npc(case.PLAYER, "PROFESSOR", sim.minute, "ASK_STUDENT")
    move("NIGHTCLUB")
    talk_to_prologue_npc(case.PLAYER, "RYOKO", sim.minute, "ASK_ADDRESS")
    move("APARTMENT")
    assert submit_terminal_command(case.PLAYER, "telnet wired 23", sim.minute)["accepted"]
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001", case.PLAYER, sim.minute)
    view("wired-message", [0,.91,1], action("WIRED", "OPEN"), "terminal")
    move("APARTMENT_DISTRICT")
    action("TALK", case.HARUTO)
    view("haruto", [-3,.91,2], action("TALK", case.HARUTO, choice="DETAIL"), "dialogue")
    action("TALK", case.AIKO, choice="PRIVATE")
    view("aiko", [10.5,.91,-28], action("TALK", case.AIKO, choice="CLOCK"), "dialogue")
    move("SCHOOL")
    view("school-sheet", [-5.2,.91,.7], action("EXAMINE", "CLOSURE_SHEET"))
    view("school-clock", [0,.91,-6.8], action("EXAMINE", "SCHOOL_CLOCK"))
    action("LINK", first="NIGHT_SIGHTING", second="CLOSURE_SHEET", relation="CONTRADICTS")
    action("HYPOTHESIS", text="Quizá alguien restauró una copia antigua. El nombre de una cuenta no demuestra quién entró.")
    view("journal", [0,.91,1], mode="journal")
    move("SCHOOL_LAB")
    view("computer", [-4.15,.91,.5], action("EXAMINE", "SCHOOL_PC"))
    view("identity-record", [-4.15,.91,.5], action("EXAMINE", "SCHOOL_PC", choice="RECONSTRUCT"), "dialogue")
    action("TALK", "PROFESSOR")
    view("decision", [3.2,.91,-3], action("TALK", "PROFESSOR", choice="REPORT"), "dialogue")
    view("return-to-school", [0,.91,-2], action("DECIDE", "PROFESSOR", decision="DISCLOSE"))
    move("NIGHTCLUB")
    view("ryoko", [0,.91,1], action("TALK", "RYOKO"), "dialogue")
    return views


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="lain-chapter-preview-") as scratch:
        os.environ.update(LAIN_WORLD_DB=str(Path(scratch)/"preview.db"),
                          LAIN_CHAPTER_ONE="1", LAIN_PROLOGUE_ENABLED="1",
                          LAIN_CITY_RESIDENTS_ENABLED="1", LAIN_LLM_ENABLED="0",
                          LAIN_MEMORY_SEMANTIC="0", LAIN_REALITY_GENERATION="0")
        views = build()
        destination = ROOT/"client/tools/fixtures/chapter01.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(views, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(f"CHAPTER01_FIXTURE_OK views={len(views)}")
        # sqlite context managers commit but older core helpers rely on GC
        # for closing connections. Release them before Windows removes temp DB.
        gc.collect()
