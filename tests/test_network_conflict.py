"""Deterministic conflict, shared opposition, private discoveries and save safety."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from server.world_core import network_conflict as net
from server.world_core.database import load_or_create_agent
from server.world_core.models import Agent
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement
from server.world_core.player_view import build_player_snapshot

P="PLAYER_1"
Q="PLAYER_RIVAL"
R="RELAY_STATION"


@pytest.fixture
def game(monkeypatch):
    monkeypatch.setenv("LAIN_CORPORATION","1")
    monkeypatch.setenv("LAIN_LLM_ENABLED","0")
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED","0")
    monkeypatch.setenv("LAIN_CITY_RESIDENTS_ENABLED","0")
    sim=Simulation()
    assert not net.network_snapshot()["active"]
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001",P,sim.minute)
    place(P,"STATION")
    build_player_snapshot()  # Initialize legacy projection-only schemas first.
    return sim


def place(actor, location):
    with net.connection() as c:
        c.execute("UPDATE agents SET location=? WHERE id=?",(location,actor))


def clock(minute):
    with net.connection() as c:
        c.execute("UPDATE simulation_state SET minute=? WHERE id=1",(minute,))
    net.advance_conflict(minute)


def act(action, relay=R, actor=P, rival="", request_id=None):
    return net.perform_network_action(actor,action,relay,rival,request_id or uuid.uuid4().hex)


def dump():
    with net.connection() as c:
        return list(c.iterdump())


def own(actor=P):
    return next(r for r in net.network_snapshot(actor)["relays"] if r["id"]==R)


def invariant():
    with net.connection() as c:
        for relay in net.RELAYS:
            corp=c.execute("SELECT corporation FROM network_relays WHERE id=?",(relay,)).fetchone()[0]
            humans=c.execute("SELECT coalesce(sum(amount),0) FROM network_influence WHERE relay=?",(relay,)).fetchone()[0]
            assert corp+humans==100
            assert 0<=corp<=100


def rival():
    load_or_create_agent(Agent(Q,"Otra cuenta","UNALIGNED","STATION","EXPLORE",1.0,"HUMAN"))
    net.enroll_player(Q)


def test_activation_preserves_prologue_and_never_enrolls_npcs(game):
    assert net.network_snapshot()["active"]
    with pytest.raises(ValueError,match="HUMAN_PLAYER_REQUIRED"):
        net.enroll_player("AGENT_K")
    assert [r["actor_id"] for r in net.network_snapshot()["rankings"]]==[P]


def test_new_game_cannot_bypass_first_wired_connection(monkeypatch):
    monkeypatch.setenv("LAIN_CORPORATION","1")
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED","1")
    Simulation()
    before=dump()
    with pytest.raises(ValueError,match="WIRED_CONNECTION_REQUIRED"):
        act("OPEN")
    assert dump()==before


def test_ownership_and_agent_affiliation_are_not_revealed_before_inspection(game):
    view=net.network_snapshot()
    assert view["corporation"]=="Administrador desconocido"
    assert len(view["visible_personnel"])==1
    assert "KAGAMI" not in json.dumps(view)
    act("INSPECT")
    assert net.network_snapshot()["corporation"]==net.CORPORATION
    assert "KAGAMI" not in net.network_snapshot()["visible_personnel"][0]["role"]
    assert "no creó la Wired" in net.network_snapshot()["reports"][0]["text"]


@pytest.mark.parametrize("action",["CLAIM","FORTIFY","CONTEST","EXPOSE"])
def test_unknown_evidence_cannot_be_forged(game,action):
    before=dump()
    with pytest.raises(ValueError): act(action,rival=Q)
    assert dump()==before


def test_retries_and_polls_cannot_advance_or_duplicate_a_claim(game):
    act("INSPECT")
    request_id="stable_claim_01"
    result=act("CLAIM",request_id=request_id)
    before=dump()
    assert act("CLAIM",request_id=request_id)==result
    for _ in range(3):
        build_player_snapshot()
    assert dump()==before
    assert own()["mine"]==20
    with pytest.raises(ValueError,match="REQUEST_ID_REUSED"):
        act("FORTIFY",request_id=request_id)
    with pytest.raises(ValueError,match="NETWORK_COOLDOWN"):
        act("CLAIM")
    assert dump()==before


@pytest.mark.parametrize("defenses,expected",[(0,0),(1,5),(2,20)])
def test_corporate_response_is_warned_finite_and_respects_defenses(game,defenses,expected):
    act("INSPECT")
    act("CLAIM")
    assert net.network_snapshot()["pending"][0]["due_minute"]==100
    for i in range(defenses):
        clock((i+1)*10)
        act("FORTIFY")
    clock(99)
    assert own()["mine"]==20
    clock(100)
    assert own()["mine"]==expected
    assert own()["defense"]==0
    assert not net.network_snapshot()["pending"]
    before=dump()
    net.advance_conflict(100)
    net.advance_conflict(100000)
    assert dump()==before  # No infinite punishment of a disconnected player.
    invariant()


def test_exposing_operative_protects_rivals_without_sharing_private_evidence(game):
    rival()
    for actor in [P,Q]:
        act("INSPECT",actor=actor)
        act("CLAIM",actor=actor)
    act("INSPECT")
    assert "credencial" in act("TALK")["choices"][0]["text"]
    act("EXPOSE")
    assert not net.network_snapshot(P)["pending"]
    assert not net.network_snapshot(Q)["pending"]
    assert "KAGAMI" in net.network_snapshot(P)["visible_personnel"][0]["role"]
    assert "KAGAMI" not in net.network_snapshot(Q)["visible_personnel"][0]["role"]
    clock(10)
    act("CLAIM",actor=Q)
    assert not net.network_snapshot(Q)["pending"]
    clock(120)
    act("CLAIM",actor=Q)
    assert net.network_snapshot(Q)["pending"]
    invariant()


def test_invalid_expired_proof_cannot_interrupt_a_later_operation(game):
    act("INSPECT")
    act("CLAIM")
    act("INSPECT")
    clock(100)
    act("CLAIM")
    before=dump()
    with pytest.raises(ValueError,match="CURRENT_PROOF_REQUIRED"):
        act("EXPOSE")
    assert dump()==before


def test_dark_connection_costs_control_and_only_cancels_its_own_attack(game):
    rival()
    for actor in [P,Q]:
        act("INSPECT",actor=actor)
        act("CLAIM",actor=actor)
    clock(10)
    place(P,"APARTMENT")
    act("GO_DARK")
    assert own()["mine"]==15
    assert not net.network_snapshot()["pending"]
    assert net.network_snapshot(Q)["pending"]
    assert net.network_snapshot()["trace"]==0
    invariant()


def test_real_accounts_compete_over_a_finite_shared_pool(game):
    rival()
    act("INSPECT")
    act("CLAIM")
    act("INSPECT",actor=Q)
    act("CONTEST",actor=Q,rival=P)
    assert own(P)["mine"]==5
    assert own(Q)["mine"]==15
    assert net.network_snapshot(Q)["rankings"][0]["actor_id"]==Q
    assert len(net.network_snapshot(P)["pending"])==1
    assert len(net.network_snapshot(Q)["pending"])==1
    invariant()
    clock(10)
    with pytest.raises(ValueError,match="INVALID_RIVAL"):
        act("CONTEST",actor=Q,rival=Q)


def test_simultaneous_claims_serialize_without_creating_control(game):
    rival()
    for actor in [P,Q]: act("INSPECT",actor=actor)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda actor:act("CLAIM",actor=actor),[P,Q]))
    assert len(results)==2
    assert own(P)["mine"]==own(Q)["mine"]==20
    assert own()["corporation"]==60
    invariant()


def test_location_validation_and_other_agents_memory_are_preserved(game):
    act("INSPECT")
    with net.connection() as c:
        memory_before=c.execute("SELECT * FROM agent_memory").fetchall()
    act("CLAIM")
    with net.connection() as c:
        assert c.execute("SELECT * FROM agent_memory").fetchall()==memory_before
    place(P,"BOOKSHOP")
    before=dump()
    with pytest.raises(ValueError,match="RELAY_NOT_PRESENT"):
        act("INSPECT")
    assert dump()==before
    assert not net.network_snapshot()["visible_personnel"]


def test_save_reload_and_tick_integration(game):
    act("INSPECT")
    act("CLAIM")
    view=net.network_snapshot()
    net.initialize_conflict()
    assert net.network_snapshot()==view
    game.minute=90
    game.tick()
    assert own()["mine"]==0
    assert not net.network_snapshot()["pending"]


def test_http_actor_identity_is_bound_by_server(game,monkeypatch):
    import server.api as api
    monkeypatch.setattr(api,"_runtime",game)
    rival()
    with pytest.raises(ValueError):
        api.NetworkActionRequest(action="INSPECT",relay=R,request_id="api_inspect_01",actor_id=Q)
    response=api.network_action(api.NetworkActionRequest(action="INSPECT",relay=R,request_id="api_inspect_01"))
    assert response["state"]["network_conflict"]["corporation"]==net.CORPORATION
    assert net.network_snapshot(Q)["corporation"]=="Administrador desconocido"
