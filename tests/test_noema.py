"""Two corporate pools, individual proof, finite responses and old-save upgrades."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from server.world_core import network_conflict as net, corporate_factions as factions
from server.world_core.database import load_or_create_agent
from server.world_core.models import Agent
from server.world_core.player_view import build_player_snapshot
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement

P="PLAYER_1"
Q="PLAYER_RIVAL"
R="RELAY_SCHOOL"


@pytest.fixture
def game(monkeypatch):
    for key in ["LAIN_NOEMA","LAIN_CORPORATION"]:
        monkeypatch.setenv(key,"1")
    for key in ["LAIN_LLM_ENABLED","LAIN_PROLOGUE_ENABLED","LAIN_CITY_RESIDENTS_ENABLED","LAIN_WORKSHOP"]:
        monkeypatch.setenv(key,"0")
    sim=Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001",P,0)
    place(P,"SCHOOL_LAB")
    build_player_snapshot()
    return sim


def place(actor, location):
    with net.connection() as c: c.execute("UPDATE agents SET location=? WHERE id=?",(location,actor))


def clock(minute):
    with net.connection() as c: c.execute("UPDATE simulation_state SET minute=? WHERE id=1",(minute,))
    net.advance_conflict(minute)


def act(action, faction="KAGAMI", actor=P, request_id=None, relay=R):
    return net.perform_network_action(actor,action,relay,"",request_id or uuid.uuid4().hex,faction)


def balances():
    with net.connection() as c:
        return (factions.balance(c,R,"KAGAMI"),factions.balance(c,R,"NOEMA"),
                c.execute("SELECT coalesce(sum(amount),0) FROM network_influence WHERE relay=?",(R,)).fetchone()[0])


def invariant():
    with net.connection() as c:
        for relay in net.RELAYS:
            values=[factions.balance(c,relay,f) for f in ["KAGAMI","NOEMA"]]
            values += [a[0] for a in c.execute("SELECT amount FROM network_influence WHERE relay=?",(relay,))]
            assert all(0<=amount<=100 for amount in values)
            assert sum(values)==100


def dump():
    with net.connection() as c: return list(c.iterdump())


def rival():
    load_or_create_agent(Agent(Q,"Otra cuenta","UNALIGNED","SCHOOL_LAB","EXPLORE",1.0,"HUMAN"))
    net.enroll_player(Q)


def test_initial_pools_are_conserved_and_read_queries_do_not_change_world(game):
    assert balances()==(70,30,0)
    before=dump()
    for _ in range(3): build_player_snapshot(); net.network_snapshot()
    assert dump()==before
    net.initialize_conflict()
    assert dump()==before
    invariant()


def test_undercover_affiliation_not_revealed_by_public_identity(game):
    view=net.network_snapshot()
    assert "NOEMA" not in json.dumps(view)
    assert "KAGAMI" not in json.dumps(view)
    assert len(view["visible_personnel"])==2
    assert "NOEMA" not in act("TALK","NOEMA")["text"]
    assert not act("TALK","NOEMA")["choices"]
    act("INSPECT")
    view=net.network_snapshot()
    assert "NOEMA" in json.dumps(view["relays"])
    assert "NOEMA" not in json.dumps(view["visible_personnel"])
    with pytest.raises(ValueError,match="CURRENT_PROOF_REQUIRED"): act("EXPOSE","NOEMA")


def test_noema_reclaim_has_distinct_clock_and_never_recurs_offline(game):
    act("INSPECT")
    response=act("CLAIM","NOEMA",request_id="noema_first_claim")
    assert balances()==(70,10,20)
    pending=net.network_snapshot()["pending"]
    assert pending[0]["remaining"]==80 and pending[0]["max_loss"]==20
    assert pending[0]["operator"]=="NOEMA"
    before=dump()
    assert act("CLAIM","NOEMA",request_id="noema_first_claim")==response
    assert dump()==before
    with pytest.raises(ValueError,match="REQUEST_ID_REUSED"):
        act("CLAIM","KAGAMI",request_id="noema_first_claim")
    clock(79)
    assert balances()==(70,10,20)
    clock(80)
    assert balances()==(70,30,0)
    before=dump()
    net.advance_conflict(80)
    net.advance_conflict(100000)
    assert dump()==before
    invariant()


@pytest.mark.parametrize("defenses,held",[(1,15),(2,20)])
def test_shared_defenses_absorb_noema_attack(game,defenses,held):
    act("INSPECT")
    act("CLAIM","NOEMA")
    for i in range(defenses):
        clock(10*(i+1))
        act("FORTIFY")
    clock(80)
    assert balances()[2]==held
    with net.connection() as c:
        assert c.execute("SELECT defense FROM network_influence WHERE actor_id=? AND relay=?",(P,R)).fetchone()==(0,)
    invariant()


def test_orders_from_both_corporations_coexist_with_independent_suppression(game):
    act("INSPECT")
    act("CLAIM","KAGAMI")
    clock(10)
    act("CLAIM","NOEMA")
    assert len(net.network_snapshot()["pending"])==2
    act("INSPECT")
    before=balances()
    act("EXPOSE","NOEMA")
    assert balances()==(before[0]+5,before[1]-5,before[2])
    pending=net.network_snapshot()["pending"]
    assert len(pending)==1 and pending[0]["operator"]=="KAGAMI"
    with net.connection() as c:
        assert factions.suppressed_until(c,R,"NOEMA")==130
        assert factions.suppressed_until(c,R,"KAGAMI")==0
    clock(100)
    assert balances()[2]==10
    invariant()


def test_corporate_opportunity_can_only_transfer_existing_corporate_control(game):
    act("INSPECT")
    act("CLAIM","NOEMA")
    clock(10)
    act("CLAIM","NOEMA")  # NOEMA now has zero, but its first operation is pending.
    act("INSPECT")
    assert balances()==(70,0,30)
    act("EXPOSE","NOEMA")
    assert balances()==(70,0,30)
    invariant()


def test_cannot_use_kagami_proof_to_expose_noema_and_expired_proof_stays_invalid(game):
    act("INSPECT")
    act("CLAIM")
    act("INSPECT")
    before=dump()
    with pytest.raises(ValueError,match="CURRENT_PROOF_REQUIRED"): act("EXPOSE","NOEMA")
    assert dump()==before
    clock(10)
    act("CLAIM","NOEMA")
    act("INSPECT")
    clock(90)
    clock(100)
    act("CLAIM","NOEMA")
    before=dump()
    with pytest.raises(ValueError,match="CURRENT_PROOF_REQUIRED"): act("EXPOSE","NOEMA")
    assert dump()==before


def test_exposure_helps_other_accounts_but_does_not_share_private_proof(game):
    rival()
    for actor in [P,Q]:
        act("INSPECT",actor=actor)
        act("CLAIM","NOEMA",actor=actor)
    act("INSPECT")
    act("EXPOSE","NOEMA")
    assert not net.network_snapshot(P)["pending"]
    assert not net.network_snapshot(Q)["pending"]
    def role(actor):
        return next(p["role"] for p in net.network_snapshot(actor)["visible_personnel"] if p["slot"]=="RECORDS")
    assert "NOEMA" in role(P)
    assert "NOEMA" not in role(Q)
    with net.connection() as c:
        assert factions.discovery(c,Q,R,"NOEMA")[2]==0
    invariant()


def test_hide_cancels_both_own_orders_without_touching_rival(game):
    rival()
    for actor in [P,Q]:
        act("INSPECT",actor=actor)
        act("CLAIM",actor=actor)
    clock(10)
    act("CLAIM","NOEMA")
    clock(20)
    place(P,"APARTMENT")
    act("GO_DARK")
    assert not net.network_snapshot(P)["pending"]
    assert len(net.network_snapshot(Q)["pending"])==1
    invariant()


def test_two_accounts_cannot_mint_control_from_simultaneous_claims(game):
    rival()
    for actor in [P,Q]: act("INSPECT",actor=actor)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda actor:act("CLAIM","NOEMA",actor=actor),[P,Q]))
    assert len(results)==2
    assert balances()==(70,0,30)
    invariant()


def test_upgrade_keeps_legacy_requests_claims_pending_orders_and_memories(monkeypatch):
    monkeypatch.setenv("LAIN_CORPORATION","1")
    monkeypatch.setenv("LAIN_NOEMA","0")
    monkeypatch.setenv("LAIN_LLM_ENABLED","0")
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED","0")
    monkeypatch.setenv("LAIN_CITY_RESIDENTS_ENABLED","0")
    sim=Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001",P,sim.minute)
    place(P,"SCHOOL_LAB")
    act("INSPECT")
    old=act("CLAIM",request_id="legacy_noema_claim")
    with net.connection() as c:
        memory=c.execute("SELECT * FROM agent_memory").fetchall()
        pending=c.execute("SELECT * FROM network_operations").fetchall()
        discovery=c.execute("SELECT * FROM network_discoveries").fetchall()
    monkeypatch.setenv("LAIN_NOEMA","1")
    net.initialize_conflict()
    assert balances()==(50,30,20)
    assert act("CLAIM",request_id="legacy_noema_claim")==old
    with net.connection() as c:
        assert c.execute("SELECT * FROM agent_memory").fetchall()==memory
        assert c.execute("SELECT * FROM network_operations").fetchall()==pending
        assert c.execute("SELECT * FROM network_discoveries").fetchall()==discovery
    invariant()
    monkeypatch.setenv("LAIN_NOEMA","0")
    net.initialize_conflict()
    assert balances()==(50,30,20)  # Reload cannot erase a persisted owner.
    clock(100)
    assert balances()==(70,30,0)  # The legacy attack still credits KAGAMI.


def test_upgrade_of_entirely_player_owned_relay_never_takes_player_control(game):
    with net.connection() as c:
        c.execute("DELETE FROM network_noema_relays WHERE relay=?",(R,))
        c.execute("UPDATE network_relays SET corporation=0 WHERE id=?",(R,))
        c.execute("INSERT INTO network_influence VALUES(?,?,100,0)",(R,P))
    net.initialize_conflict()
    assert balances()==(0,0,100)
    invariant()


def test_wrong_location_invalid_faction_and_actor_cannot_be_supplied_by_client(game,monkeypatch):
    from server import api
    from pydantic import ValidationError
    monkeypatch.setattr(api,"_runtime",game)
    with pytest.raises(ValidationError):
        api.NetworkActionRequest(action="CLAIM",relay=R,faction="NOEMA",actor_id="AGENT_K",request_id="fake_identity_01")
    for wrong in ["","PLAYER_1","K","noema"]:
        before=dump()
        with pytest.raises(ValueError,match="INVALID_CORPORATION"): act("CLAIM",wrong)
        assert dump()==before
    place(P,"CAFE")
    before=dump()
    with pytest.raises(ValueError,match="RELAY_NOT_PRESENT"): act("TALK","NOEMA")
    assert dump()==before
    assert not net.network_snapshot()["visible_personnel"]


def test_scope_by_relay_and_private_npc_memory_survive(game):
    act("INSPECT")
    act("CLAIM","NOEMA")
    act("INSPECT")
    with net.connection() as c:
        memory=c.execute("SELECT * FROM agent_memory").fetchall()
    place(P,"STATION")
    act("INSPECT",relay="RELAY_STATION")
    with pytest.raises(ValueError,match="CURRENT_PROOF_REQUIRED"): act("EXPOSE","NOEMA",relay="RELAY_STATION")
    place(P,"SCHOOL_LAB")
    act("EXPOSE","NOEMA")
    with net.connection() as c:
        assert c.execute("SELECT * FROM agent_memory").fetchall()==memory
    invariant()


@pytest.mark.parametrize("contract",["KAGAMI","NOEMA"])
def test_workshop_contracts_scan_and_protection_apply_to_both_operators(game,monkeypatch,contract):
    from server.world_core import workshop as ws
    from server.world_core.code_lab import LIFE_HINT
    monkeypatch.setenv("LAIN_WORKSHOP","1")
    ws.initialize_workshop()
    def workshop(action,**data):
        return ws.perform_workshop_action(P,action,data,uuid.uuid4().hex)
    workshop("LESSON")
    place(P,"APARTMENT")
    workshop("TEST_LIFE",source=LIFE_HINT)
    workshop("DEVICE",id="life_matrix",active=True)
    workshop("CONTRACT",faction=contract)
    if contract=="NOEMA":
        assert workshop("COMPILE",source='use("routing")\nuse("scan")')["passed"]
    else:
        assert workshop("COMPILE",source='use("routing")\nuse("shield")')["passed"]
    place(P,"SCHOOL_LAB")
    act("INSPECT")
    act("CLAIM","NOEMA")
    clock(10)
    act("CLAIM","KAGAMI")
    if contract=="NOEMA":
        before_proof=None
        with net.connection() as c:
            before_proof=factions.discovery(c,P,R,"NOEMA")
        place(P,"APARTMENT")
        response=workshop("SCAN",relay=R)
        assert "NOEMA: intervención" in response["text"] and "KAGAMI: intervención" in response["text"]
        with net.connection() as c:
            assert c.execute("SELECT * FROM workshop_contract_reports").fetchall()==[(P,"NOEMA",R,10,2)]
            # Remote exploration cannot fabricate a physical credential check.
            assert factions.discovery(c,P,R,"NOEMA")==before_proof
        clock(80)
        assert balances()[2]==20
        clock(110)
        assert balances()[2]==0
    else:
        clock(20)
        act("PROGRAM_SHIELD")
        clock(80)
        assert balances()[2]==40
        clock(110)
        assert balances()[2]==25  # Used shields are gone, ongoing contract absorbs 15.
    invariant()
