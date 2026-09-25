"""First workshop slice: actual solutions, server rewards and saved provenance."""
import json
import uuid
from collections import deque

import pytest

from server.world_core import workshop as ws, network_conflict as net
from server.world_core.code_lab import LIFE_HINT, LIFE_TEMPLATE, test_life as run_life, step_grid
from server.world_core.database import load_or_create_agent
from server.world_core.models import Agent
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement
from server.world_core.player_view import build_player_snapshot

P="PLAYER_1"
R="RELAY_SCHOOL"


@pytest.fixture
def game(monkeypatch):
    for key in ["LAIN_CORPORATION","LAIN_WORKSHOP","LAIN_CHAPTER_ONE"]:
        monkeypatch.setenv(key,"1")
    for key in ["LAIN_LLM_ENABLED","LAIN_PROLOGUE_ENABLED","LAIN_CITY_RESIDENTS_ENABLED","LAIN_WORLD_CLOCK"]:
        monkeypatch.setenv(key,"0")
    sim=Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001",P,sim.minute)
    place("APARTMENT")
    build_player_snapshot()
    return sim


def place(location, actor=P):
    with net.connection() as c: c.execute("UPDATE agents SET location=? WHERE id=?",(location,actor))


def act(action, actor=P, request_id=None, **data):
    return ws.perform_workshop_action(actor,action,data,request_id or uuid.uuid4().hex)


def learn():
    place("SCHOOL_LAB")
    act("LESSON")
    place("APARTMENT")


def solve():
    learn()
    assert act("TEST_LIFE",source=LIFE_HINT)["passed"]


def shield():
    solve()
    act("DEVICE",id="life_matrix",active=True)
    return act("COMPILE",source='use("routing")\nuse("shield")\n')


def dump():
    with net.connection() as c: return list(c.iterdump())


def winning_moves():
    """Independent BFS finds a valid full route; no hard-coded client score."""
    board=ws.ARCADE
    walls={tuple(p) for p in board["walls"]}
    chips={tuple(p):i for i,p in enumerate(board["chips"])}
    queue=deque([(0,0,0,"")])
    seen={(0,0,0)}
    while queue:
        x,y,mask,moves=queue.popleft()
        if (x,y)==tuple(board["exit"]):
            if mask.bit_count()>=3: return moves
            continue
        for direction,(dx,dy) in {"U":(0,-1),"D":(0,1),"L":(-1,0),"R":(1,0)}.items():
            nx,ny=x+dx,y+dy
            if not (0<=nx<8 and 0<=ny<8) or (nx,ny) in walls: continue
            next_mask=mask | (1<<chips[(nx,ny)] if (nx,ny) in chips else 0)
            key=(nx,ny,next_mask)
            if key not in seen:
                seen.add(key)
                queue.append((*key,moves+direction))
    raise AssertionError("Unsolvable café game")


def test_workshop_does_not_skip_prologue(monkeypatch):
    monkeypatch.setenv("LAIN_WORKSHOP","1")
    monkeypatch.setenv("LAIN_CORPORATION","1")
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED","1")
    monkeypatch.setenv("LAIN_LLM_ENABLED","0")
    Simulation()
    assert not ws.workshop_snapshot()["active"]
    with pytest.raises(ValueError,match="WIRED_CONNECTION_REQUIRED"): act("TEST_LIFE",source=LIFE_HINT)


def test_sources_and_polls_are_private_read_only_and_reinitialization_safe(game):
    before=dump()
    for _ in range(3): ws.workshop_snapshot(); build_player_snapshot()
    assert dump()==before
    ws.initialize_workshop()
    assert dump()==before
    assert not ws.workshop_snapshot("AGENT_K")["active"]
    with pytest.raises(ValueError,match="WIRED_CONNECTION_REQUIRED"): act("SAVE_PROGRAM",actor="AGENT_K",source="secret")


def test_lesson_location_and_first_device_gate(game):
    before=dump()
    with pytest.raises(ValueError,match="WORKSHOP_WRONG_LOCATION"): act("LESSON")
    with pytest.raises(ValueError,match="LESSON_REQUIRED"): act("TEST_LIFE",source=LIFE_HINT)
    assert dump()==before
    learn()
    assert not act("TEST_LIFE",source=LIFE_TEMPLATE)["passed"]
    assert not any(a["model"]=="matrix" for a in ws.workshop_snapshot()["assets"])


@pytest.mark.parametrize("source", [
    "import os",
    "def next_cell(alive, neighbors):\n    return __import__('os').system('echo nope')",
    "def next_cell(alive, neighbors):\n    while True:\n        pass",
    "def next_cell(alive, neighbors):\n    return alive.__class__",
    "def next_cell(alive, neighbors):\n    return [True]*999999999",
    "def next_cell(alive, neighbors):\n    return next_cell(alive, neighbors)",
    "def next_cell(alive, neighbors):\n    return 1",
    "def next_cell(alive, neighbors):\n    if alive:\n        return True",
    "def next_cell(alive, neighbors):\n    return 'True'",
    "@open('secret')\ndef next_cell(alive, neighbors):\n    return True",
    "def next_cell(alive=open('secret'), neighbors=3):\n    return True",
    "\x00",
    "("*5000,
])
def test_lesson_is_bounded_and_never_runs_arbitrary_python(source):
    assert not run_life(source)["passed"]


def test_real_python_alternatives_and_synchronous_grid():
    alternative="def next_cell(alive, neighbors):\n    return neighbors == 3 or alive and 2 <= neighbors <= 3"
    assert run_life(alternative)["passed"]
    rule=lambda a,n: n==3 or (a and n==2)
    block=[[0,0,0,0],[0,1,1,0],[0,1,1,0],[0,0,0,0]]
    assert step_grid(block,rule)==block
    blinker=[[0]*5 for _ in range(5)]
    blinker[2][1:4]=[1,1,1]
    original=json.dumps(blinker)
    assert step_grid(step_grid(blinker,rule),rule)==blinker
    assert json.dumps(blinker)==original
    frames=run_life(alternative)["frames"]
    for y in range(7):
        for x in range(7): assert frames[0][y][x]==frames[4][y+1][x+1]


def test_reward_retry_and_repeat_cannot_duplicate_equipment_or_provenance(game):
    learn()
    first=act("TEST_LIFE",source=LIFE_HINT,request_id="life_attempt_01")
    saved=dump()
    assert act("TEST_LIFE",source=LIFE_HINT,request_id="life_attempt_01")==first
    assert dump()==saved
    act("TEST_LIFE",source=LIFE_HINT)
    assets=ws.workshop_snapshot()["assets"]
    assert len([a for a in assets if a["model"]=="matrix"])==1
    assert len([a for a in assets if a["model"]=="shield"])==1
    with pytest.raises(ValueError,match="REQUEST_ID_REUSED"):
        act("TEST_LIFE",source=LIFE_TEMPLATE,request_id="life_attempt_01")


def test_compilation_capacity_duplicate_code_and_last_valid_build(game):
    solve()
    source='use("routing")\nuse("shield")'
    assert not act("COMPILE",source=source)["passed"]
    assert ws.workshop_snapshot()["modules"]==["routing"]
    act("DEVICE",id="life_matrix",active=True)
    assert act("COMPILE",source=source+'\nuse("shield")')["passed"]
    state=ws.workshop_snapshot()
    assert state["cost"]==6 and state["capacity"]==8
    for bad in ['use("unknown")',source+"\nimport os",source+"\nuse.__call__('scan')"]:
        assert not act("COMPILE",source=bad)["passed"]
        assert ws.workshop_snapshot()["compiled"]==state["compiled"]
    act("DEVICE",id="life_matrix",active=False)
    assert ws.workshop_snapshot()["modules"]==["routing"]
    assert ws.workshop_snapshot()["draft"]==bad


def test_ownership_device_dedup_and_contract_withdrawal(game):
    solve()
    act("DEVICE",id="life_matrix",active=True)
    with pytest.raises(ValueError,match="DEVICE_NOT_OWNED"): act("DEVICE",id="invented",active=True)
    with pytest.raises(ValueError,match="BASE_DEVICE_REQUIRED"): act("DEVICE",id="home_navi",active=False)
    act("CONTRACT",faction="KAGAMI")
    assert ws.workshop_snapshot()["capacity"]==7  # second Navi never stacks; one reserved unit.
    assert any(a["ownership"]=="LOAN" for a in ws.workshop_snapshot()["assets"])
    act("CONTRACT",faction="NOEMA")
    assert act("COMPILE",source='use("routing")\nuse("scan")')["passed"]
    act("CONTRACT",faction="INDEPENDENT")
    view=ws.workshop_snapshot()
    assert view["modules"]==["routing"]
    assert view["capacity"]==8
    assert not any(a["ownership"]=="LOAN" for a in view["assets"])
    assert all(a["id"]!="life_matrix" or a["ownership"]=="OWNED" for a in view["assets"])


def test_program_shield_changes_real_intervention_and_preserves_control(game):
    assert shield()["passed"]
    place("SCHOOL_LAB")
    for action in ["INSPECT","CLAIM"]:
        net.perform_network_action(P,action,R,"",uuid.uuid4().hex)
    with net.connection() as c: c.execute("UPDATE simulation_state SET minute=10 WHERE id=1")
    net.perform_network_action(P,"PROGRAM_SHIELD",R,"",uuid.uuid4().hex)
    with net.connection() as c:
        assert c.execute("SELECT defense FROM network_influence WHERE actor_id=? AND relay=?",(P,R)).fetchone()==(2,)
    net.advance_conflict(100)
    with net.connection() as c:
        assert c.execute("SELECT amount,defense FROM network_influence WHERE actor_id=? AND relay=?",(P,R)).fetchone()==(20,0)
        assert c.execute("SELECT corporation FROM network_relays WHERE id=?",(R,)).fetchone()==(80,)


def test_uncompiled_module_cannot_be_forged(game):
    place("SCHOOL_LAB")
    for action in ["INSPECT","CLAIM"]:
        net.perform_network_action(P,action,R,"",uuid.uuid4().hex)
    with net.connection() as c: c.execute("UPDATE simulation_state SET minute=10 WHERE id=1")
    before=dump()
    with pytest.raises(ValueError,match="SHIELD_MODULE_REQUIRED"):
        net.perform_network_action(P,"PROGRAM_SHIELD",R,"",uuid.uuid4().hex)
    assert dump()==before


def test_scan_contract_records_only_explicit_telemetry_and_can_be_ended(game):
    solve()
    act("DEVICE",id="life_matrix",active=True)
    act("CONTRACT",faction="NOEMA")
    act("COMPILE",source='use("routing")\nuse("scan")')
    with pytest.raises(ValueError,match="INSPECT_RELAY_FIRST"): act("SCAN",relay=R)
    place("SCHOOL_LAB")
    net.perform_network_action(P,"INSPECT",R,"",uuid.uuid4().hex)
    place("APARTMENT")
    act("SCAN",relay=R)
    with net.connection() as c:
        assert c.execute("SELECT * FROM workshop_contract_reports").fetchall()==[(P,"NOEMA",R,0,0)]
    act("CONTRACT",faction="INDEPENDENT")
    with pytest.raises(ValueError,match="SCAN_MODULE_REQUIRED"): act("SCAN",relay=R)


def test_cafe_replay_rewards_only_valid_owned_run_once(game):
    moves=winning_moves()
    place("CAFE")
    act("TECHNICIAN")
    assert len([a for a in ws.workshop_snapshot()["assets"] if a["model"]=="routing"])==2
    run=act("ARCADE_START")["run_id"]
    with pytest.raises(ValueError,match="ARCADE_NOT_FINISHED"): act("ARCADE_FINISH",run_id=run,moves="")
    with pytest.raises(ValueError,match="INVALID_ARCADE_MOVES"): act("ARCADE_FINISH",run_id=run,moves="teleport")
    result=act("ARCADE_FINISH",run_id=run,moves=moves)
    assert result["won"] and result["score"]>0
    assert act("ARCADE_FINISH",run_id=run,moves=moves)==result
    view=ws.workshop_snapshot()
    assert len([a for a in view["assets"] if a["model"]=="interface"])==1
    assert len([a for a in view["assets"] if a["model"]=="scan"])==1
    place("APARTMENT")
    act("DEVICE",id="courier_interface",active=True)
    assert act("COMPILE",source='use("routing")\nuse("scan")')["passed"]


def test_abandoned_runs_foreign_identity_and_invalid_moves(game):
    place("CAFE")
    old=act("ARCADE_START")["run_id"]
    act("ARCADE_START")
    with pytest.raises(ValueError,match="ARCADE_RUN_REQUIRED"):
        act("ARCADE_FINISH",run_id=old,moves=winning_moves())
    load_or_create_agent(Agent("PLAYER_2","Amiga","UNALIGNED","CAFE","EXPLORE",1.0,"HUMAN"))
    net.enroll_player("PLAYER_2")
    ws.enroll_workshop()
    run=act("ARCADE_START")["run_id"]
    with pytest.raises(ValueError,match="ARCADE_RUN_REQUIRED"):
        act("ARCADE_FINISH",actor="PLAYER_2",run_id=run,moves=winning_moves())
    assert ws.workshop_snapshot("PLAYER_2")["best_score"]==0
    with pytest.raises(ValueError): ws.arcade_replay("R"*81)
    with pytest.raises(ValueError): ws.arcade_replay(winning_moves()+"U")


def test_http_identity_extra_fields_and_validation(game,monkeypatch):
    from pydantic import ValidationError
    from fastapi import HTTPException
    from server import api
    monkeypatch.setattr(api,"_runtime",game)
    request={"action":"SAVE_PROGRAM","data":{"source":'use("routing")'},"request_id":"workshop_http_01"}
    assert api.workshop_action(api.WorkshopActionRequest(**request))["state"]["workshop"]["active"]
    with pytest.raises(ValidationError):
        api.WorkshopActionRequest(**{**request,"actor_id":"AGENT_K"})
    with pytest.raises(ValidationError):
        api.WorkshopActionRequest(**{**request,"data":{"source":["bad"]}})
    with pytest.raises(HTTPException) as error:
        api.workshop_action(api.WorkshopActionRequest(**{**request,"data":{"source":"a"*4001}}))
    assert error.value.status_code==409


def test_disabling_conflict_also_disables_workshop(monkeypatch):
    monkeypatch.setenv("LAIN_WORKSHOP","1")
    monkeypatch.setenv("LAIN_CORPORATION","0")
    monkeypatch.setenv("LAIN_LLM_ENABLED","0")
    Simulation()
    assert ws.workshop_snapshot()=={"active":False}


def test_contract_cover_and_reloading_preserve_owned_work(game):
    shield()
    act("CONTRACT",faction="KAGAMI")
    before=ws.workshop_snapshot()
    ws.initialize_workshop()
    assert ws.workshop_snapshot()==before
    place("SCHOOL_LAB")
    for action in ["INSPECT","CLAIM"]:
        net.perform_network_action(P,action,R,"",uuid.uuid4().hex)
    net.advance_conflict(100)
    with net.connection() as c:
        assert c.execute("SELECT amount FROM network_influence WHERE actor_id=? AND relay=?",(P,R)).fetchone()==(5,)
    place("APARTMENT")
    act("CONTRACT",faction="INDEPENDENT")
    with net.connection() as c:
        assert ws.corporate_cover(c,P)==0
