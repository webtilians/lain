"""Consent, distinct resources, actual shared functions and loss of access."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from server.world_core import circles as cs, workshop as ws, network_conflict as net
from server.world_core.code_lab import LIFE_HINT
from server.world_core.database import load_or_create_agent
from server.world_core.models import Agent
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement
from server.world_core.player_view import build_player_snapshot

P = "PLAYER_1"
Q = "PLAYER_TEST_OTHER"
R = "RELAY_SCHOOL"
PROGRAM = 'use("routing")\nuse("shield")\nuse("scan")\n'


@pytest.fixture
def game(monkeypatch):
    for key in ["LAIN_CIRCLES","LAIN_WORKSHOP","LAIN_CORPORATION","LAIN_NOEMA","LAIN_CHAPTER_ONE"]:
        monkeypatch.setenv(key,"1")
    for key in ["LAIN_LLM_ENABLED","LAIN_PROLOGUE_ENABLED","LAIN_CITY_RESIDENTS_ENABLED","LAIN_WORLD_CLOCK"]:
        monkeypatch.setenv(key,"0")
    sim = Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001",P,sim.minute)
    place("APARTMENT")
    build_player_snapshot()
    return sim


def place(where, actor=P):
    with net.connection() as c: c.execute("UPDATE agents SET location=? WHERE id=?",(where,actor))


def circle(action, actor=P, request_id=None, **data):
    return cs.perform_circle_action(actor,action,data,request_id or uuid.uuid4().hex)


def workshop(action, actor=P, **data):
    return ws.perform_workshop_action(actor,action,data,uuid.uuid4().hex)


def dump():
    with net.connection() as c: return list(c.iterdump())


def solve(actor=P):
    place("SCHOOL_LAB",actor)
    workshop("LESSON",actor=actor)
    place("APARTMENT",actor)
    assert workshop("TEST_LIFE",actor=actor,source=LIFE_HINT)["passed"]


def meet(peer, actor=P):
    place(cs.PARTNERS[peer]["location"],actor)
    circle("CONTACT",actor=actor,target=peer)
    place("APARTMENT",actor)


def basic(actor=P):
    circle("CREATE",actor=actor,name="Círculo de prueba")
    for ident in ["home_navi","first_connection"]:
        circle("CONTRIBUTE",actor=actor,id=ident,active=True)


def full_circle():
    solve()
    basic()
    workshop("DEVICE",id="life_matrix",active=True)
    for ident in ["life_matrix","life_shield"]:
        circle("CONTRIBUTE",id=ident,active=True)
    meet("RYOKO")
    circle("INVITE",target="RYOKO")
    assert circle("COMPILE",source=PROGRAM)["passed"]


def other_account():
    load_or_create_agent(Agent(Q,"Otra cuenta","UNALIGNED","APARTMENT","EXPLORE",1.0,"HUMAN"))
    net.enroll_player(Q)
    ws.enroll_workshop()


def test_feature_does_not_bypass_new_game_prologue(monkeypatch):
    for key in ["LAIN_CIRCLES","LAIN_WORKSHOP","LAIN_CORPORATION","LAIN_PROLOGUE_ENABLED"]:
        monkeypatch.setenv(key,"1")
    monkeypatch.setenv("LAIN_LLM_ENABLED","0")
    Simulation()
    assert cs.circle_snapshot()=={"active":False}
    with pytest.raises(ValueError,match="WIRED_CONNECTION_REQUIRED"): circle("CREATE",name="Antes de conectar")


def test_empty_circle_requires_explicit_own_contributions_and_read_is_pure(game):
    initial = ws.workshop_snapshot()
    circle("CREATE",name="Mi círculo")
    assert cs.circle_snapshot()["group"]["capacity"]==0
    assert not circle("COMPILE",source='use("routing")')["passed"]
    before = dump()
    for _ in range(3): build_player_snapshot(); cs.circle_snapshot()
    cs.initialize_circles()
    assert dump()==before
    assert ws.workshop_snapshot()==initial


def test_meeting_and_authored_conditions_are_required(game):
    basic()
    with pytest.raises(ValueError,match="MEET_PARTNER_FIRST"): circle("INVITE",target="RYOKO")
    meet("RYOKO")
    with pytest.raises(ValueError,match="PARTNER_CONDITION_REQUIRED"): circle("INVITE",target="RYOKO")
    solve()
    circle("INVITE",target="RYOKO")
    assert cs.circle_snapshot()["group"]["capacity"]==7
    assert "scan" not in ws.workshop_snapshot()["modules"]
    assert "scan" not in ws.workshop_snapshot()["shared_modules"]  # No automatic compilation.


def test_duplicate_devices_and_code_keep_all_provenance_but_add_no_capacity(game):
    solve()
    basic()
    meet("RYOKO")
    circle("INVITE",target="RYOKO")
    with net.connection() as c:
        ws._grant(c,P,"extra_navi","DEVICE","navi","Otro equipo propio",5,1)
        ws._grant(c,P,"extra_routing","CODE","routing","Copia conocida",5)
    for ident in ["extra_navi","extra_routing"]: circle("CONTRIBUTE",id=ident,active=True)
    group = cs.circle_snapshot()["group"]
    assert group["capacity"]==7
    assert len(group["contributions"])==7
    assert sum(p["counted"] for p in group["contributions"] if p["model"]=="navi")==1
    assert sum(p["counted"] for p in group["contributions"] if p["model"]=="routing")==1
    assert {p["source"] for p in group["contributions"]} >= {"Otro equipo propio","Copia conocida"}
    assert all(p["acquired_minute"] is None for p in group["contributions"] if p["actor"]=="RYOKO")
    assert circle("COMPILE",source='use("routing")\nuse("scan")\nuse("scan")')["passed"]
    assert cs.circle_snapshot()["group"]["cost"]==5


def test_shared_program_is_separate_and_drives_real_scan_and_defense(game):
    personal = ws.workshop_snapshot()["compiled"]
    full_circle()
    view = ws.workshop_snapshot()
    assert view["compiled"]==personal and view["modules"]==["routing"]
    assert set(view["shared_modules"])=={"routing","shield","scan"}
    assert cs.circle_snapshot()["group"]["capacity"]==11
    place("SCHOOL_LAB")
    net.perform_network_action(P,"INSPECT",R,"",uuid.uuid4().hex)
    net.perform_network_action(P,"CLAIM",R,"",uuid.uuid4().hex,"NOEMA")
    with net.connection() as c: c.execute("UPDATE simulation_state SET minute=10 WHERE id=1")
    net.perform_network_action(P,"PROGRAM_SHIELD",R,"",uuid.uuid4().hex)
    place("APARTMENT")
    assert "NOEMA" in workshop("SCAN",relay=R)["text"]
    net.advance_conflict(80)
    assert next(r for r in net.network_snapshot()["relays"] if r["id"]==R)["mine"]==20


@pytest.mark.parametrize("change",["REMOVE","DISCONNECT","WITHDRAW","CONTRACT"])
def test_withdrawal_revokes_shared_functions_atomically_preserving_drafts(game,change):
    full_circle()
    if change=="REMOVE": circle("REMOVE",target="RYOKO")
    elif change=="DISCONNECT": workshop("DEVICE",id="life_matrix",active=False)
    elif change=="WITHDRAW": circle("CONTRIBUTE",id="first_connection",active=False)
    else: workshop("CONTRACT",faction="KAGAMI")
    group = cs.circle_snapshot()["group"]
    assert group["modules"]==[] and group["compiled"]==""
    assert group["draft"]==PROGRAM
    assert ws.workshop_snapshot()["modules"]==["routing"]
    with net.connection() as c: assert not ws.has_module(c,P,"scan")
    assert "Montaje detenido" in group["events"][0]["text"]
    if change=="DISCONNECT":
        workshop("DEVICE",id="life_matrix",active=True)
        assert ws.workshop_snapshot()["shared_modules"]==[]
        assert circle("COMPILE",source=PROGRAM)["passed"]


def test_duplicate_backup_keeps_program_working_when_one_contribution_leaves(game):
    full_circle()
    circle("CONTRIBUTE",id="home_navi",active=False)  # Ryoko still supplies the same model.
    assert set(cs.circle_snapshot()["group"]["modules"])=={"routing","shield","scan"}
    assert cs.circle_snapshot()["group"]["capacity"]==11


def test_invalid_build_keeps_previous_compiled_and_saves_bounded_draft(game):
    full_circle()
    for source in ["import os",'use("invented")','use("routing")\nopen("secret")']:
        assert not circle("COMPILE",source=source)["passed"]
        group=cs.circle_snapshot()["group"]
        assert group["draft"]==source and group["compiled"]==PROGRAM
    before=dump()
    with pytest.raises(ValueError,match="INVALID_SOURCE"): circle("COMPILE",source="a"*4001)
    assert dump()==before


def test_loans_disconnected_and_other_people_assets_cannot_be_contributed(game):
    solve()
    basic()
    with pytest.raises(ValueError,match="ASSET_NOT_AVAILABLE"): circle("CONTRIBUTE",id="life_matrix",active=True)
    with pytest.raises(ValueError,match="ASSET_NOT_OWNED"): circle("CONTRIBUTE",id="DEVICE:interface",active=True)
    workshop("CONTRACT",faction="KAGAMI")
    with pytest.raises(ValueError,match="ASSET_NOT_AVAILABLE"): circle("CONTRIBUTE",id="kagami_loan",active=True)
    assert all(p["id"]!="kagami_loan" for p in cs.circle_snapshot()["group"]["eligible"])


def test_dissolution_removes_only_shared_access_and_replay_cannot_recreate(game):
    full_circle()
    with net.connection() as c:
        assets=c.execute("SELECT * FROM workshop_assets").fetchall()
        personal=c.execute("SELECT * FROM workshop_players").fetchall()
    response=circle("LEAVE",request_id="leave_circle_01")
    assert cs.circle_snapshot()["group"] is None
    before=dump()
    assert circle("LEAVE",request_id="leave_circle_01")==response
    assert dump()==before
    with net.connection() as c:
        assert c.execute("SELECT * FROM workshop_assets").fetchall()==assets
        assert c.execute("SELECT * FROM workshop_players").fetchall()==personal
    basic()
    assert cs.circle_snapshot()["group"]["modules"]==[]
    circle("INVITE",target="RYOKO")  # Released partner can choose a new circle.


def test_retries_location_and_identity_are_authoritative(game):
    response=circle("CREATE",name="Uno",request_id="create_circle_01")
    before=dump()
    assert circle("CREATE",name="Uno",request_id="create_circle_01")==response
    assert dump()==before
    with pytest.raises(ValueError,match="REQUEST_ID_REUSED"): circle("CREATE",name="Dos",request_id="create_circle_01")
    place("CAFE")
    before=dump()
    with pytest.raises(ValueError,match="CIRCLE_PC_REQUIRED"): circle("COMPILE",source=PROGRAM)
    with pytest.raises(ValueError,match="PARTNER_NOT_PRESENT"): circle("CONTACT",target="RYOKO")
    with pytest.raises(ValueError,match="WIRED_CONNECTION_REQUIRED"): circle("CREATE",actor="AGENT_K",name="No")
    assert dump()==before
    assert cs.circle_snapshot("AGENT_K")=={"active":False}


@pytest.mark.parametrize("action,data",[
    ("CREATE",{"name":"x","actor_id":"AGENT_K"}),("CREATE",{"name":"\n"}),
    ("CONTRIBUTE",{"id":"home_navi","active":1}),("INVITE",{"target":None}),
    ("INVITE",{"target":"PLAYER_TEST_OTHER"}),("COMPILE",{"source":[]} ),
])
def test_malformed_and_unimplemented_human_invites_never_mutate(game,action,data):
    basic()
    before=dump()
    with pytest.raises(ValueError): cs.perform_circle_action(P,action,data,uuid.uuid4().hex)
    assert dump()==before


def test_concurrent_invites_cannot_clone_npc_resources_into_two_circles(game):
    other_account()
    for actor in [P,Q]:
        solve(actor)
        meet("RYOKO",actor)
        basic(actor)
    def invite(actor):
        try: circle("INVITE",actor=actor,target="RYOKO"); return "accepted"
        except ValueError as error: return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(invite,[P,Q]))
    assert sorted(results)==["PARTNER_ALREADY_COMMITTED","accepted"]
    assert sorted([cs.circle_snapshot(a)["group"]["capacity"] for a in [P,Q]])==[4,7]


def test_other_account_cannot_see_circle_drafts_or_private_memories(game):
    other_account()
    with net.connection() as c:
        c.execute("INSERT INTO agent_memory(agent_id,memory) VALUES('AGENT_K','K private sentinel')")
        c.execute("INSERT INTO agent_memory(agent_id,memory) VALUES('NORA','Nora private sentinel')")
        before=c.execute("SELECT * FROM agent_memory").fetchall()
    full_circle()
    circle("COMPILE",source="# private group sentinel\n"+PROGRAM)
    own=json.dumps(build_player_snapshot())
    other=json.dumps(build_player_snapshot(Q))
    assert "K private sentinel" not in own and "Nora private sentinel" not in own
    assert "private group sentinel" not in other
    assert cs.circle_snapshot(Q)["group"] is None
    with net.connection() as c: assert c.execute("SELECT * FROM agent_memory").fetchall()==before


def test_technician_alternative_route_uses_verified_arcade_reward(game):
    basic()
    meet("KISSA_TECH")
    with pytest.raises(ValueError,match="PARTNER_CONDITION_REQUIRED"): circle("INVITE",target="KISSA_TECH")
    place("CAFE")
    run=workshop("ARCADE_START")
    assert workshop("ARCADE_FINISH",run_id=run["run_id"],moves="DDRDRRRRRDDDDR")["won"]
    place("APARTMENT")
    circle("INVITE",target="KISSA_TECH")
    assert cs.circle_snapshot()["group"]["capacity"]==8
    assert circle("COMPILE",source='use("routing")\nuse("shield")')["passed"]
    assert ws.workshop_snapshot()["lesson"]==0


def test_disabled_feature_and_additive_initialization_preserve_existing_tables(game,monkeypatch):
    with net.connection() as c:
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'") if not r[0].startswith("circle_")]
        before={t:c.execute('SELECT * FROM "'+t+'"').fetchall() for t in tables}
    cs.initialize_circles()
    with net.connection() as c:
        for table, rows in before.items(): assert c.execute('SELECT * FROM "'+table+'"').fetchall()==rows
    full_circle()
    before=dump()
    monkeypatch.setenv("LAIN_CIRCLES","0")
    assert cs.circle_snapshot()=={"active":False}
    assert ws.workshop_snapshot()["shared_modules"]==[]
    assert dump()==before
    monkeypatch.setenv("LAIN_CIRCLES","1")
    assert cs.circle_snapshot()["group"]["compiled"]==PROGRAM


def test_http_model_forbids_forged_identity_and_invalid_data(game,monkeypatch):
    from server import api
    from pydantic import ValidationError
    monkeypatch.setattr(api,"_runtime",game)
    command={"action":"CREATE","data":{"name":"API"},"request_id":"circle_http_01"}
    assert api.circle_action(api.CircleActionRequest(**command))["state"]["circles"]["group"]["name"]=="API"
    with pytest.raises(ValidationError): api.CircleActionRequest(**command,actor_id="AGENT_K")
    with pytest.raises(ValidationError):
        api.CircleActionRequest(action="CONTRIBUTE",data={"id":"home_navi","active":1},request_id="circle_bad_01")
