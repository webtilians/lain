"""A complete authored case, with no LLM/network dependency or user save access."""
import json
import uuid
from collections import deque

import pytest

from server.world_core import chapter_one as case
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection
from server.world_core.locations import LOCATION_GRAPH
from server.world_core.player_view import build_player_snapshot
from server.world_core.prologue import talk_to_prologue_npc, submit_terminal_command
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement
from server.world_core.action_queue import queue_action


def move(sim, destination):
    pending = deque([(sim.player.location, [])])
    seen = set()
    while pending:
        place, route = pending.popleft()
        if place == destination:
            for step in route:
                aid = queue_action(actor_id=case.PLAYER, action="MOVE", target=step, source="GODOT_CLIENT")
                assert sim.tick()[aid]["accepted"], (step, route)
            return
        if place not in seen:
            seen.add(place)
            pending.extend((other,route+[other]) for other in LOCATION_GRAPH.get(place,()) if other not in seen)
    raise AssertionError("No route")


def action(sim, kind, target="", request_id=None, **data):
    return case.perform_chapter_action(case.PLAYER, kind, target, data, sim.minute,
                                       request_id or uuid.uuid4().hex)


def dump():
    with get_connection() as c:
        return list(c.iterdump())


@pytest.fixture
def game(monkeypatch):
    monkeypatch.setenv("LAIN_CHAPTER_ONE", "1")
    monkeypatch.setenv("LAIN_CITY_RESIDENTS_ENABLED", "1")
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    sim = Simulation()
    assert case.chapter_snapshot()=={"active":False}
    move(sim,"SCHOOL_LAB")
    talk_to_prologue_npc(case.PLAYER,"PROFESSOR",sim.minute,"ASK_STUDENT")
    move(sim,"NIGHTCLUB")
    talk_to_prologue_npc(case.PLAYER,"RYOKO",sim.minute,"ASK_ADDRESS")
    move(sim,"APARTMENT")
    assert submit_terminal_command(case.PLAYER,"telnet wired 23",sim.minute)["accepted"]
    assert not case.chapter_snapshot()["active"]
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001",case.PLAYER,sim.minute)
    return sim


def clues():
    return {e["id"]:e for e in case.chapter_snapshot()["evidence"]}


def reconstruct(sim, remote=False):
    move(sim,"APARTMENT_DISTRICT")
    action(sim,"TALK",case.HARUTO)
    move(sim,"SCHOOL")
    action(sim,"EXAMINE","CLOSURE_SHEET")
    action(sim,"LINK",first="NIGHT_SIGHTING",second="CLOSURE_SHEET",relation="CONTRADICTS")
    if remote:
        move(sim,"APARTMENT")
        action(sim,"WIRED","SEARCH")
        action(sim,"WIRED","RECONSTRUCT")
    else:
        move(sim,"SCHOOL_LAB")
        action(sim,"EXAMINE","SCHOOL_PC")
        action(sim,"EXAMINE","SCHOOL_PC",choice="RECONSTRUCT")
    assert "IDENTITY_LOG" in clues()


def test_connection_starts_once_and_polling_is_read_only(game):
    message = clues()["RETURN_MESSAGE"]
    assert message["text"] == "Has vuelto."
    assert message["source_id"] == "UNKNOWN_WIRED"
    original = case.chapter_snapshot()
    assert not case.activate_chapter()
    Simulation()
    assert case.chapter_snapshot()==original
    before = dump()
    for _ in range(3):
        assert build_player_snapshot()["chapter_one"]==original
    assert dump()==before


def test_new_offline_player_cannot_skip_prologue(monkeypatch):
    monkeypatch.setenv("LAIN_CHAPTER_ONE","1")
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED","1")
    sim=Simulation()
    before=dump()
    with pytest.raises(ValueError,match="CHAPTER_NOT_STARTED"):
        action(sim,"WIRED","SEARCH")
    assert dump()==before
    assert case.chapter_snapshot()=={"active":False}


def test_clue_order_and_real_prologue_provenance(game):
    move(game,"SCHOOL")
    action(game,"EXAMINE","CLOSURE_SHEET")
    move(game,"APARTMENT_DISTRICT")
    action(game,"TALK",case.HARUTO)
    action(game,"TALK",case.HARUTO,choice="DETAIL")
    evidence=clues()
    assert evidence["WRONG_DETAIL"]["kind"]=="TESTIMONY"
    assert evidence["MY_VISIT"]["kind"]=="OBSERVATION"
    assert "profesor" in evidence["MY_VISIT"]["text"]
    with get_connection() as c:
        event=c.execute("SELECT minute,actor_id,action,target FROM events WHERE id=?",(evidence["MY_VISIT"]["event_id"],)).fetchone()
        assert event[1:]==(case.PLAYER,"PROLOGUE_TALK","PROFESSOR")
        assert event[0] < evidence["MY_VISIT"]["acquired_minute"]
    assert not case.chapter_snapshot()["contradiction_linked"]


@pytest.mark.parametrize("remote",[False,True])
def test_both_physical_and_wired_paths_reconstruct_without_certifying_truth(game,remote):
    reconstruct(game,remote)
    record=clues()["IDENTITY_LOG"]
    assert record["kind"]=="RECORD"
    assert "firma verificable" in record["text"]
    assert "60 minutos antes" in record["text"]
    assert record["acquired_minute"]>=case.chapter_snapshot()["connection_minute"]
    with get_connection() as c:
        assert c.execute("SELECT count(*) FROM events WHERE minute<0").fetchone()[0]==0
    assert case.chapter_snapshot()["hypothesis_status"]=="UNVERIFIED"
    assert case.chapter_snapshot()["decision"] is None


def test_reconstruction_needs_an_explicit_contradiction_not_just_collection(game):
    move(game,"APARTMENT_DISTRICT")
    action(game,"TALK",case.HARUTO)
    move(game,"SCHOOL_LAB")
    action(game,"TALK","PROFESSOR")
    action(game,"EXAMINE","SCHOOL_PC")
    action(game,"EXAMINE","SCHOOL_PC",choice="RECONSTRUCT")
    assert "IDENTITY_LOG" not in clues()
    action(game,"LINK",first="NIGHT_SIGHTING",second="PROFESSOR_CLOSED",relation="SUPPORTS")
    action(game,"EXAMINE","SCHOOL_PC",choice="RECONSTRUCT")
    assert "IDENTITY_LOG" not in clues()
    action(game,"LINK",first="NIGHT_SIGHTING",second="PROFESSOR_CLOSED",relation="CONTRADICTS")
    action(game,"EXAMINE","SCHOOL_PC",choice="RECONSTRUCT")
    assert "IDENTITY_LOG" in clues()


def test_private_confidence_and_public_denial_are_both_retained(game):
    move(game,"APARTMENT_DISTRICT")
    action(game,"TALK",case.AIKO,choice="PRIVATE")
    first=clues()["AIKO_PRIVATE"]
    assert not any(m["id"]=="AIKO_PRIVATE" for m in case.chapter_actor_context(case.HARUTO)["memories"])
    action(game,"TALK",case.AIKO,choice="PUBLIC")
    assert clues()["AIKO_PRIVATE"]==first
    assert clues()["AIKO_DENIAL"]["kind"]=="OBSERVATION"
    assert "nada más" in action(game,"TALK",case.AIKO,choice="PRIVATE")["text"]
    assert not any(m["id"]=="AIKO_PRIVATE" for m in case.chapter_actor_context("PROFESSOR")["memories"])


@pytest.mark.parametrize("kind,target,data",[
    ("TALK","PROFESSOR",{}),("TALK",case.HARUTO,{}),
    ("EXAMINE","SCHOOL_PC",{}),("EXAMINE","CLOSURE_SHEET",{}),
    ("LINK","",{"first":"IDENTITY_LOG","second":"RETURN_MESSAGE","relation":"CONTRADICTS"}),
    ("DECIDE","RYOKO",{"decision":"SEAL"}),
    ("TALK","UNKNOWN_WIRED",{}),
])
def test_remote_or_unknown_evidence_and_decision_bypasses_leave_no_writes(game,kind,target,data):
    before=dump()
    with pytest.raises(ValueError):
        action(game,kind,target,**data)
    assert dump()==before


def test_hypothesis_is_private_and_does_not_rewrite_npc_knowledge(game):
    before_context={a:case.chapter_actor_context(a) for a in (*case.PEOPLE,"AGENT_K","AGENT_NORA")}
    def legacy_rows():
        return [line for line in dump() if not line.startswith('INSERT INTO "chapter_one')
                and not line.startswith('INSERT INTO "events"')
                and not line.startswith('INSERT INTO "sqlite_sequence" VALUES(\'events\',')]
    legacy = legacy_rows()
    action(game,"HYPOTHESIS",text="PRIVATE_TEST_NOTE: tal vez yo nunca estuve allí.")
    assert legacy_rows() == legacy
    assert case.chapter_snapshot()["hypothesis_status"]=="UNVERIFIED"
    for actor, before in before_context.items():
        assert case.chapter_actor_context(actor)==before
    context=AgentContextBuilder().build(case.HARUTO)
    assert "PRIVATE_TEST_NOTE" not in json.dumps(context)
    assert "chapter_memory" in context
    assert case.chapter_actor_context("AGENT_K") is None
    assert case.chapter_actor_context("AGENT_NORA") is None


def test_legacy_save_does_not_invent_a_prologue_visit(monkeypatch):
    monkeypatch.setenv("LAIN_CHAPTER_ONE","1")
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED","0")
    monkeypatch.setenv("LAIN_CITY_RESIDENTS_ENABLED","1")
    sim=Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001",case.PLAYER,sim.minute)
    move(sim,"APARTMENT_DISTRICT")
    action(sim,"TALK",case.HARUTO,choice="DETAIL")
    assert "MY_VISIT" not in clues()
    assert "WRONG_DETAIL" not in clues()
    assert case.chapter_snapshot()["active"]


@pytest.mark.parametrize("decision,actor,other,bonus",[
    ("DISCLOSE","PROFESSOR","RYOKO","MAINTENANCE_APPENDIX"),
    ("SEAL","RYOKO","PROFESSOR","UNDATED_PACKET"),
])
def test_persistent_decision_changes_two_people_and_the_return_visit(game,decision,actor,other,bonus):
    reconstruct(game)
    move(game,case.PLACES[actor])
    rid=uuid.uuid4().hex
    response=action(game,"DECIDE",actor,request_id=rid,decision=decision)
    after=dump()
    assert action(game,"DECIDE",actor,request_id=rid,decision=decision)==response
    assert dump()==after
    actor_context=case.chapter_actor_context(actor)
    other_context=case.chapter_actor_context(other)
    assert actor_context["relationship"]["stance"]=="TRUSTING"
    assert other_context["relationship"]["stance"]=="GUARDED"
    assert actor_context["relationship"]["source"]==case.PLAYER
    assert other_context["relationship"]["source"]==actor
    if decision=="SEAL":
        assert not any(m["id"]=="IDENTITY_LOG" for m in other_context["memories"])
        assert any(m["id"]=="REDACTED_NOTICE" for m in other_context["memories"])
        move(game,"APARTMENT")
        action(game,"WIRED","PACKET")
        move(game,"SCHOOL_LAB")
        with pytest.raises(ValueError,match="APPENDIX_NOT_AVAILABLE"):
            action(game,"EXAMINE","SCHOOL_PC",choice="APPENDIX")
    else:
        assert any(m["id"]=="IDENTITY_LOG" and m["source"]=="PROFESSOR" for m in other_context["memories"])
        action(game,"EXAMINE","SCHOOL_PC",choice="APPENDIX")
        move(game,"APARTMENT")
        with pytest.raises(ValueError,match="PACKET_NOT_AVAILABLE"):
            action(game,"WIRED","PACKET")
    assert bonus in clues()
    restored=Simulation()
    assert case.chapter_snapshot()["decision"]==decision
    move(restored,case.PLACES[other])
    with pytest.raises(ValueError,match="CHAPTER_DECISION_ALREADY_MADE"):
        action(restored,"DECIDE",other,decision="SEAL" if decision=="DISCLOSE" else "DISCLOSE")
    assert action(restored,"TALK",other)["text"]==case._decision_response(None,case.PLAYER,other,decision)["text"]


def test_reusing_request_id_for_another_command_is_rejected(game):
    rid=uuid.uuid4().hex
    action(game,"WIRED","REPLY",request_id=rid)
    before=dump()
    with pytest.raises(ValueError,match="REQUEST_ID_REUSED"):
        action(game,"WIRED","SEARCH",request_id=rid)
    assert dump()==before


def test_api_validates_types_and_never_exposes_unknown_sources(game,monkeypatch):
    import server.api as api
    monkeypatch.setattr(api,"_runtime",game)
    request={"action":"WIRED","target":"SEARCH","data":{},"request_id":uuid.uuid4().hex}
    response=api.chapter_one_action(api.ChapterActionRequest(**request))
    assert "WIRED_MIRROR" in {e["id"] for e in response["state"]["chapter_one"]["evidence"]}
    assert "chapter_one_knowledge" not in json.dumps(response)
    assert "relationship" not in response["state"]["chapter_one"]
    before=dump()
    request["data"]={"choice":{"unexpected":1}}
    with pytest.raises(ValueError):
        api.ChapterActionRequest(**request)
    assert dump()==before
