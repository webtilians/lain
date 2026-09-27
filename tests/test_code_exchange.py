"""Exchange ownership, atomic receipts, provenance and usable copies."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from server.world_core import code_exchange as ex, workshop as ws, circles as cs, network_conflict as net
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement
from server.world_core.player_view import build_player_snapshot

P = "PLAYER_1"
OFFER = "ryoko_scan_v1"


@pytest.fixture
def game(monkeypatch):
    for flag in ("WORKSHOP","CORPORATION","CIRCLES","CODE_EXCHANGE"):
        monkeypatch.setenv("LAIN_"+flag,"1")
    for flag in ("PROLOGUE_ENABLED","LLM_ENABLED","CITY_RESIDENTS_ENABLED","WORLD_CLOCK","REALITY_GENERATION","CAFE_EVENTS"):
        monkeypatch.setenv("LAIN_"+flag,"0")
    sim = Simulation()
    assert ex.exchange_snapshot() == {"active":False}
    with pytest.raises(ValueError,match="WIRED_CONNECTION_REQUIRED"):
        act("CONTACT",peer="RYOKO")
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001",P,sim.minute)
    build_player_snapshot()
    place("APARTMENT")
    return sim


def place(where):
    with net.connection() as c: c.execute("UPDATE agents SET location=? WHERE id=?",(where,P))


def act(action, request_id=None, **data):
    return ex.perform_exchange_action(P,action,data,request_id or uuid.uuid4().hex)


def grant(ident="won_buffer",model="buffer",ownership="OWNED",actor=P,kind="CODE"):
    with net.connection() as c:
        ws._grant(c,actor,ident,kind,model,"Kissa · torneo 1 · primer puesto",10)
        c.execute("UPDATE workshop_assets SET ownership=? WHERE actor=? AND id=?",(ownership,actor,ident))


def meet(peer="RYOKO"):
    place(cs.PARTNERS[peer]["location"])
    result = act("CONTACT",peer=peer)
    place("APARTMENT")
    return result


def dump():
    with net.connection() as c: return list(c.iterdump())


def test_new_player_sees_contacts_but_not_unknown_proposals(game):
    state = ex.exchange_snapshot()
    assert state["active"] and state["history"] == []
    for offer in state["offers"]:
        assert not offer["met"] and not offer["ready"]
        assert not offer["copies"] and not offer["given"] and not offer["motive"]
    before = dump()
    assert ex.exchange_snapshot() == state
    assert dump() == before


def test_physical_meeting_records_first_minute_and_no_rewards(game):
    before = dump()
    with pytest.raises(ValueError,match="PARTNER_NOT_PRESENT"): act("CONTACT",peer="RYOKO")
    assert dump() == before
    meet()
    state = ex.exchange_snapshot()["offers"][0]
    assert state["met"] and state["wanted"] == "buffer" and not state["ready"]
    with net.connection() as c:
        c.execute("UPDATE simulation_state SET minute=900 WHERE id=1")
    meet()
    assert ex.exchange_snapshot()["offers"][0]["met_minute"] == state["met_minute"]
    assert len(ws.workshop_snapshot()["assets"]) == 2


def test_exchange_requires_own_fragment_and_contact(game):
    grant()
    with pytest.raises(ValueError,match="MEET_EXCHANGE_PEER_FIRST"):
        act("ACCEPT",offer=OFFER,asset="won_buffer")
    meet()
    for asset in ("first_connection","home_navi","missing"):
        before = dump()
        with pytest.raises(ValueError,match="EXCHANGE_OWNED_CODE_REQUIRED"):
            act("ACCEPT",offer=OFFER,asset=asset)
        assert dump() == before


@pytest.mark.parametrize("case",["loan","other_owner","wrong_kind","circle","noema"])
def test_borrowed_or_shared_code_is_not_owned(game,case):
    meet()
    if case == "loan": grant(ownership="LOAN")
    if case == "other_owner": grant(actor="AGENT_K")
    if case == "wrong_kind": grant(kind="DEVICE")
    if case == "circle":
        with net.connection() as c:
            c.execute("INSERT INTO circle_groups(name,leader,created_minute,modules) VALUES('Test',?,0,'[\"buffer\"]')",(P,))
    if case == "noema":
        with net.connection() as c: c.execute("UPDATE workshop_players SET contract='NOEMA' WHERE actor=?",(P,))
    before = dump()
    with pytest.raises(ValueError,match="INDEPENDENT_REQUIRED|EXCHANGE_OWNED_CODE_REQUIRED"):
        act("ACCEPT",offer=OFFER,asset="won_buffer")
    assert dump() == before


def test_copy_keeps_original_program_and_individual_provenance(game):
    meet()
    grant()
    grant("another_buffer")
    with net.connection() as c:
        c.execute("UPDATE workshop_assets SET source='Different origin',minute=5 WHERE id='another_buffer'")
    before = ws.workshop_snapshot()
    result = act("ACCEPT",offer=OFFER,asset="won_buffer",request_id="exchange_receipt_test")
    state = ws.workshop_snapshot()
    assert len(state["assets"]) == len(before["assets"])+1
    assert state["compiled"] == before["compiled"] and state["modules"] == ["routing"]
    assert state["capacity"] == before["capacity"]
    assert result["sent"]["acquired_minute"] == 10
    assert result["sent"]["source"] == "Kissa · torneo 1 · primer puesto"
    assert result["received"]["owner"] == P and result["received"]["original_acquired_minute"] is None
    assert result["received"]["from"] == "RYOKO"
    receipt = ex.exchange_snapshot()["history"][0]
    with net.connection() as c:
        c.execute("UPDATE workshop_assets SET source='changed later' WHERE id='won_buffer'")
    assert ex.exchange_snapshot()["history"][0] == receipt
    before = dump()
    assert act("ACCEPT",offer=OFFER,asset="won_buffer",request_id="exchange_receipt_test") == result
    assert dump() == before


def test_duplicate_function_preserves_sources_without_extra_capacity(game):
    meet()
    grant()
    grant("existing_scan","scan")
    act("ACCEPT",offer=OFFER,asset="won_buffer")
    state = ws.workshop_snapshot()
    assert len([a for a in state["assets"] if a["model"] == "scan"]) == 2
    assert len([m for m in state["library"] if m["id"] == "scan"]) == 1
    assert state["capacity"] == 4


def test_unique_offer_is_atomic_across_concurrent_and_new_request_ids(game):
    meet()
    grant()
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(lambda _:act("ACCEPT",offer=OFFER,asset="won_buffer"),range(4)))
    assert all(r == results[0] for r in results)
    with net.connection() as c:
        assert c.execute("SELECT count(*) FROM code_exchange_deals").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM workshop_assets WHERE id=?",("exchange_"+OFFER,)).fetchone()[0] == 1
        c.execute("UPDATE agents SET location='CAFE' WHERE id=?",(P,))
    # A retry of the exact request may arrive after moving; a new request cannot trade remotely.
    with pytest.raises(ValueError,match="EXCHANGE_PC_REQUIRED"): act("ACCEPT",offer=OFFER,asset="won_buffer")


def test_receipts_survive_restart_switch_off_and_contract(game,monkeypatch):
    meet()
    grant()
    received = act("ACCEPT",offer=OFFER,asset="won_buffer")
    original = dump()
    ex.initialize_exchange()
    assert dump() == original
    monkeypatch.setenv("LAIN_CODE_EXCHANGE","0")
    assert ex.exchange_snapshot() == {"active":False}
    assert "scan" in {a["model"] for a in ws.workshop_snapshot()["assets"]}
    with pytest.raises(ValueError,match="EXCHANGE_DISABLED"): act("CONTACT",peer="RYOKO")
    monkeypatch.setenv("LAIN_CODE_EXCHANGE","1")
    with net.connection() as c: c.execute("UPDATE workshop_players SET contract='KAGAMI' WHERE actor=?",(P,))
    assert ex.exchange_snapshot()["history"] == [received]


def test_received_code_can_be_relayed_compiled_and_contributed(game):
    meet()
    meet("KISSA_TECH")
    grant()
    first = act("ACCEPT",offer=OFFER,asset="won_buffer")
    second = act("ACCEPT",offer="kissa_shield_v1",asset=first["received"]["asset"])
    assert second["sent"]["source"] == first["received"]["source"]
    assert second["sent"]["acquired_minute"] == first["minute"]
    source = 'use("routing")\nuse("shield")\n'
    call = lambda a,**d:ws.perform_workshop_action(P,a,d,uuid.uuid4().hex)
    assert not call("COMPILE",source=source)["passed"] # Navi alone is insufficient.
    grant("test_cache","cache",kind="DEVICE")
    call("DEVICE",id="test_cache",active=True)
    assert call("COMPILE",source=source)["passed"]
    cs.perform_circle_action(P,"CREATE",{"name":"Copias"},uuid.uuid4().hex)
    for ident in ("home_navi","first_connection","test_cache",second["received"]["asset"]):
        cs.perform_circle_action(P,"CONTRIBUTE",{"id":ident,"active":True},uuid.uuid4().hex)
    assert cs.perform_circle_action(P,"COMPILE",{"source":source},uuid.uuid4().hex)["passed"]


@pytest.mark.parametrize("action,data",[("CONTACT",{"peer":"AGENT_K"}),("ACCEPT",{"offer":"made_up","asset":"x"}),
    ("CONTACT",{"peer":True}),("CONTACT",{"peer":"RYOKO","owner":"PLAYER_1"}),
    ("ACCEPT",{"offer":OFFER,"asset":[]}),("DELETE",{}),("ACCEPT",{"offer":OFFER,"asset":""})])
def test_bad_requests_are_read_only(game,action,data):
    before = dump()
    with pytest.raises(ValueError): ex.perform_exchange_action(P,action,data,uuid.uuid4().hex)
    assert dump() == before


def test_identity_request_reuse_and_private_state_isolation(game):
    from server.world_core.database import load_or_create_agent
    from server.world_core.models import Agent
    other = "PLAYER_EXCHANGE_OTHER"
    load_or_create_agent(Agent(other,"Otra cuenta","UNALIGNED","APARTMENT","EXPLORE",1.0,"HUMAN"))
    net.enroll_player(other)
    ws.enroll_workshop()
    with net.connection() as c:
        c.execute("INSERT INTO agent_memory(agent_id,memory) VALUES('AGENT_K','K private exchange sentinel')")
        c.execute("INSERT INTO agent_memory(agent_id,memory) VALUES('NORA','Nora private exchange sentinel')")
    meet()
    grant()
    act("ACCEPT",offer=OFFER,asset="won_buffer",request_id="exchange_key_0001")
    before = dump()
    with pytest.raises(ValueError,match="REQUEST_ID_REUSED"):
        act("CONTACT",peer="RYOKO",request_id="exchange_key_0001")
    with pytest.raises(ValueError,match="WIRED_CONNECTION_REQUIRED"):
        ex.perform_exchange_action("AGENT_K","CONTACT",{"peer":"RYOKO"},"exchange_key_0002")
    assert ex.exchange_snapshot("AGENT_K") == {"active":False}
    assert ex.exchange_snapshot("other") == {"active":False}
    state = ex.exchange_snapshot(other)
    assert state["active"] and not state["history"] and not any(o["met"] for o in state["offers"])
    own = json.dumps(ex.exchange_snapshot())
    assert "private exchange sentinel" not in own
    assert dump() == before


def test_migration_and_exchange_leave_other_tables_untouched(game):
    meet()
    grant()
    allowed = {"code_exchange_deals","code_exchange_requests","workshop_assets","network_reports","sqlite_sequence"}
    with net.connection() as c:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0] not in allowed]
        before = {t:c.execute('SELECT * FROM "'+t+'"').fetchall() for t in tables}
    act("ACCEPT",offer=OFFER,asset="won_buffer")
    with net.connection() as c:
        assert before == {t:c.execute('SELECT * FROM "'+t+'"').fetchall() for t in tables}


def test_http_model_binds_actor_and_rejects_extra_claims(game,monkeypatch):
    from server import api
    from pydantic import ValidationError
    monkeypatch.setattr(api,"_runtime",game)
    place("NIGHTCLUB")
    command = dict(action="CONTACT",data={"peer":"RYOKO"},request_id="http_exchange_contact")
    assert api.code_exchange_action(api.ExchangeActionRequest(**command))["state"]["code_exchange"]["offers"][0]["met"]
    with pytest.raises(ValidationError): api.ExchangeActionRequest(**command,actor_id="AGENT_K")
    with pytest.raises(ValidationError): api.ExchangeActionRequest(action="CONTACT",data={"peer":False},request_id="http_bad_exchange")
