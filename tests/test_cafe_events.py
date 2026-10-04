"""Deterministic calendar, replay boundary, prizes and integration with real builds."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
import uuid

import pytest
from pydantic import ValidationError

from server.world_core import cafe_events as ev, workshop as ws, network_conflict as net, circles
from server.world_core.database import load_or_create_agent
from server.world_core.models import Agent
from server.world_core.player_view import build_player_snapshot
from server.world_core.simulation import Simulation
from server.world_core.wired import process_wired_message_acknowledgement

P = "PLAYER_1"


@pytest.fixture
def game(monkeypatch):
    for flag in ("CORPORATION", "WORKSHOP", "CAFE_EVENTS", "CIRCLES", "NOEMA", "CHAPTER_ONE"):
        monkeypatch.setenv("LAIN_" + flag, "1")
    for flag in ("LLM_ENABLED", "WORLD_CLOCK", "PROLOGUE_ENABLED", "CITY_RESIDENTS_ENABLED", "REALITY_GENERATION"):
        monkeypatch.setenv("LAIN_" + flag, "0")
    sim = Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001", P, sim.minute)
    place("CAFE")
    build_player_snapshot()  # Complete legacy lazy schema initialization once.
    return sim


def place(where, actor=P):
    with net.connection() as c:
        c.execute("UPDATE agents SET location=? WHERE id=?", (where, actor))


def clock(minute):
    with net.connection() as c:
        c.execute("UPDATE simulation_state SET minute=? WHERE id=1", (minute,))
    ev.advance_events(minute)


def event(edition=1, actor=P):
    return next(x for x in ev.event_snapshot(actor)["events"] if x["edition"] == edition)


def act(action, actor=P, request_id=None, **data):
    return ev.perform_event_action(actor, action, data, request_id or uuid.uuid4().hex)


def workshop(action, **data):
    return ws.perform_workshop_action(P, action, data, uuid.uuid4().hex)


def dump():
    with net.connection() as c:
        return list(c.iterdump())


def route(board, count=5):
    """Independent shortest-path solver; scores never come from the client."""
    blocked = set(map(tuple, board["walls"]))
    chips = {tuple(p): i for i, p in enumerate(board["chips"])}
    seen = set()
    pending = deque([(*board["start"], 0, "")])
    while pending:
        x, y, mask, path = pending.popleft()
        if [x, y] == board["exit"]:
            if mask.bit_count() >= count:
                return path
            continue
        if (x, y, mask) in seen:
            continue
        seen.add((x, y, mask))
        for direction, (dx, dy) in zip("RLDU", ((1,0),(-1,0),(0,1),(0,-1))):
            a, b = x+dx, y+dy
            if 0 <= a < 8 and 0 <= b < 8 and (a, b) not in blocked:
                bit = 1 << chips[(a, b)] if (a, b) in chips else 0
                pending.append((a, b, mask | bit, path + direction))
    raise AssertionError("No winning route")


def win(edition=1, actor=P):
    item = event(edition, actor)
    clock(item["opens"])
    run = act("START", actor=actor, event=item["id"])
    result = act("FINISH", actor=actor, run_id=run["run_id"], moves=route(run["board"]))
    assert result["won"]
    return item, run, result


def test_prologue_has_no_calendar_or_early_reward(game, monkeypatch, tmp_path):
    from server.world_core import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "new.db")
    monkeypatch.setenv("LAIN_PROLOGUE_ENABLED", "1")
    Simulation()
    state = build_player_snapshot()
    assert state["prologue"]["stage"] == "FIND_TEACHER"
    assert state["cafe_events"] == {"active": False}
    with net.connection() as c:
        assert c.execute("SELECT count(*) FROM cafe_season").fetchone() == (0,)
    with pytest.raises(ValueError, match="WIRED_CONNECTION_REQUIRED"):
        act("START", event="KISSA_000001")


def test_calendar_starts_once_and_reads_never_change_world(game):
    first = event()
    assert first["opens"] == ev.LEAD and first["status"] == "UPCOMING"
    before = dump()
    ev.initialize_events()
    for _ in range(3):
        build_player_snapshot()
    assert dump() == before
    Simulation()
    assert event()["opens"] == first["opens"]


@pytest.mark.parametrize("offset,allowed", [(-1,False),(0,True),(299,True),(300,False)])
def test_server_half_open_window(game, offset, allowed):
    item = event()
    clock(item["opens"] + offset)
    if allowed:
        assert act("START", event=item["id"])["board"]
    else:
        before = dump()
        with pytest.raises(ValueError, match="EVENT_NOT_OPEN"):
            act("START", event=item["id"])
        assert dump() == before


def test_location_and_identity_cannot_be_forged(game):
    item = event()
    clock(item["opens"])
    place("APARTMENT")
    with pytest.raises(ValueError, match="CAFE_REQUIRED"):
        act("START", event=item["id"])
    with pytest.raises(ValueError, match="WIRED_CONNECTION_REQUIRED"):
        act("START", actor="AGENT_K", event=item["id"])
    place("CAFE")
    for data in ({"event":item["id"],"score":"9999"}, {"event":item["id"],"actor":P}, {"event":False}):
        with pytest.raises(ValueError, match="INVALID_EVENT_DATA"):
            ev.perform_event_action(P, "START", data, uuid.uuid4().hex)


def test_resume_is_one_attempt_and_retries_are_bound(game):
    item = event()
    clock(item["opens"])
    run = act("START", event=item["id"], request_id="first_event_run")
    before = dump()
    assert act("START", event=item["id"], request_id="first_event_run") == run
    assert dump() == before
    assert act("START", event=item["id"])["run_id"] == run["run_id"]
    assert event()["attempts"] == 1
    with pytest.raises(ValueError, match="REQUEST_ID_REUSED"):
        act("FINISH", run_id=run["run_id"], moves="U"*80, request_id="first_event_run")


def test_three_attempts_and_best_mark_only(game):
    item = event()
    clock(item["opens"])
    scores = []
    for chips in (4, 3, 5):
        run = act("START", event=item["id"])
        result = act("FINISH", run_id=run["run_id"], moves=route(run["board"], chips))
        scores.append(result["score"])
        assert next(x for x in event()["ranking"] if x["mine"])["score"] == max(scores)
    with pytest.raises(ValueError, match="EVENT_ATTEMPTS_USED"):
        act("START", event=item["id"])


@pytest.mark.parametrize("moves", ["X", "U"*81, "", "DDD"])
def test_invalid_and_partial_replays_cannot_rank(game, moves):
    item = event()
    clock(item["opens"])
    run = act("START", event=item["id"])
    before = dump()
    with pytest.raises(ValueError):
        act("FINISH", run_id=run["run_id"], moves=moves)
    assert dump() == before


def test_failed_complete_run_consumes_attempt_without_ranking_or_prize(game):
    item = event()
    clock(item["opens"])
    run = act("START", event=item["id"])
    assert not act("FINISH", run_id=run["run_id"], moves="U"*80)["won"]
    assert event()["attempts"] == 1 and not event()["ranking"]
    clock(item["closes"])
    assert not event()["won"]


def test_late_finish_is_rejected_and_no_reward_until_close(game):
    item, run, result = win()
    assert not event()["won"]
    clock(item["closes"] - 1)
    late = act("START", event=item["id"])
    clock(item["closes"])
    with pytest.raises(ValueError, match="EVENT_NOT_OPEN"):
        act("FINISH", run_id=late["run_id"], moves=route(late["board"]))
    assert act("FINISH", run_id=run["run_id"], moves=route(run["board"])) == result
    assert event()["won"]


def test_settlement_is_atomic_unique_and_preserves_provenance(game):
    item, _, _ = win()
    clock(item["closes"])
    before = dump()
    ev.advance_events(item["closes"])
    ev.initialize_events()
    assert dump() == before
    with net.connection() as c:
        prize = c.execute("SELECT kind,model,minute,ownership,source FROM workshop_assets WHERE id=?",
                          ("event_" + item["id"],)).fetchall()
    assert len(prize) == 1
    assert prize[0][:4] == ("CODE","buffer",item["closes"],"OWNED")
    assert "torneo 1" in prize[0][4]


def test_delayed_settlement_records_actual_acquisition_not_retroactive_knowledge(game):
    item, _, _ = win()
    clock(item["closes"] + 100)
    with net.connection() as c:
        assert c.execute("SELECT minute FROM workshop_assets WHERE id=?",
                         ("event_" + item["id"],)).fetchone() == (item["closes"] + 100,)


@pytest.mark.parametrize("edition", [1,2,3,4])
def test_all_boards_are_playable_and_npc_scores_are_replayed(game, edition):
    clock(ev.LEAD + (edition - 1) * ev.PERIOD)
    item = event(edition)
    run = act("START", event=item["id"])
    assert ws.arcade_replay(route(run["board"]), run["board"])["collected"] == 5
    clock(item["opens"] + 120)
    ranks = event(edition)["ranking"]
    assert len(ranks) == 2 and all(r["npc"] for r in ranks)
    expected = sorted(ws.arcade_replay(ev.npc_route(edition-1,n),run["board"])["score"] for n in (3,4))
    assert sorted(r["score"] for r in ranks) == expected


def test_unpublished_opponent_scores_are_not_revealed(game):
    item = event()
    clock(item["opens"] + 39)
    assert event()["ranking"] == []
    clock(item["opens"] + 40)
    assert [r["name"] for r in event()["ranking"]] == ["Aki"]


def test_ties_share_first_without_sharing_private_runs(game):
    load_or_create_agent(Agent(id="OTHER_HUMAN",name="Invitado",faction="HUMAN",location="CAFE",
                               goal="EXPLORE",controller_type="HUMAN"))
    net.enroll_player("OTHER_HUMAN")
    ws.enroll_workshop()
    item, _, _ = win()
    win(actor="OTHER_HUMAN")
    clock(item["closes"])
    assert event()["won"] and event(actor="OTHER_HUMAN")["won"]
    firsts = [r for r in event()["ranking"] if r["rank"] == 1]
    assert len(firsts) == 2 and sum(r["mine"] for r in firsts) == 1
    assert "moves" not in json.dumps(ev.event_snapshot())
    assert "AGENT_K" not in json.dumps(ev.event_snapshot())
    assert ev.event_snapshot("AGENT_K") == {"active":False}


def test_parallel_starts_resume_one_slot_and_parallel_settlement_grants_once(game):
    item = event()
    clock(item["opens"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = list(pool.map(lambda _: act("START", event=item["id"]), range(2)))
    assert runs[0]["run_id"] == runs[1]["run_id"]
    act("FINISH",run_id=runs[0]["run_id"],moves=route(runs[0]["board"]))
    with net.connection() as c:
        c.execute("UPDATE simulation_state SET minute=? WHERE id=1", (item["closes"],))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(ev.advance_events, [item["closes"]]*2))
    with net.connection() as c:
        assert c.execute("SELECT count(*) FROM workshop_assets WHERE id=?",("event_"+item["id"],)).fetchone() == (1,)


def test_migration_and_large_time_jump_are_bounded(game):
    before = dump()
    ev.initialize_events()
    assert dump() == before
    clock(10_000_000)
    with net.connection() as c:
        assert c.execute("SELECT count(*) FROM cafe_events").fetchone()[0] <= 4
    assert len(ev.event_snapshot()["events"]) <= 5


def test_reward_device_connects_and_duplicate_models_count_once(game):
    clock(ev.LEAD + ev.PERIOD)
    item, _, _ = win(2)
    clock(item["closes"])
    place("APARTMENT")
    assert ws.workshop_snapshot()["capacity"] == 4
    workshop("DEVICE", id="event_"+item["id"], active=True)
    assert ws.workshop_snapshot()["capacity"] == 6
    with net.connection() as c:
        ws._grant(c,P,"second_cache","DEVICE","cache","Otra procedencia",item["closes"],1)
    assert ws.workshop_snapshot()["capacity"] == 6


@pytest.mark.parametrize("faction,strength", [("KAGAMI",30),("NOEMA",20)])
@pytest.mark.parametrize("mode", ["personal","shared","both"])
def test_won_module_reduces_real_intervention_once(game, faction, strength, mode):
    item, _, _ = win()
    clock(item["closes"])
    place("APARTMENT")
    source = 'use("routing")\nuse("buffer")\n'
    if mode != "shared":
        assert workshop("COMPILE",source=source)["passed"]
    if mode != "personal":
        def circle(action, **data):
            return circles.perform_circle_action(P,action,data,uuid.uuid4().hex)
        circle("CREATE", name="Ensayo")
        for ident in ("home_navi","first_connection","event_"+item["id"]):
            circle("CONTRIBUTE",id=ident,active=True)
        assert circle("COMPILE",source=source)["passed"]
    with net.connection() as c:
        c.execute("INSERT INTO network_influence VALUES('RELAY_SCHOOL',?,60,0)",(P,))
        c.execute("UPDATE network_relays SET corporation=10 WHERE id='RELAY_SCHOOL'")
        op = c.execute("INSERT INTO network_operations(relay,target,created_minute,due_minute,status) VALUES('RELAY_SCHOOL',?,0,1,'PENDING')",(P,)).lastrowid
        if faction == "NOEMA":
            c.execute("INSERT INTO network_operation_factions VALUES(?,'NOEMA')",(op,))
    net.advance_conflict(item["closes"])
    with net.connection() as c:
        assert c.execute("SELECT amount FROM network_influence WHERE actor_id=?",(P,)).fetchone() == (60-strength+5,)


def test_feature_off_keeps_owned_prizes_but_hides_calendar(game, monkeypatch):
    item, _, _ = win()
    clock(item["closes"])
    monkeypatch.setenv("LAIN_CAFE_EVENTS","0")
    before = dump()
    assert ev.event_snapshot() == {"active":False}
    ev.advance_events(100000)
    ev.initialize_events()
    assert dump() == before
    assert any(a["model"] == "buffer" for a in ws.workshop_snapshot()["assets"])


def test_http_binds_identity_and_rejects_client_scores(game, monkeypatch):
    from server import api
    monkeypatch.setattr(api, "_runtime", game)
    item = event()
    clock(item["opens"])
    command = dict(action="START", data={"event":item["id"]}, request_id="http_event_start")
    with pytest.raises(ValidationError):
        api.CafeEventRequest(**{**command,"actor":P})
    with pytest.raises(ValidationError):
        api.CafeEventRequest(**{**command,"data":{"event":item["id"],"score":999}})
    result = api.cafe_event_action(api.CafeEventRequest(**command))
    assert api.cafe_event_action(api.CafeEventRequest(**command)) == result
    run = result["result"]
    finish = dict(action="FINISH",data={"run_id":run["run_id"],"moves":route(run["board"])},request_id="http_event_finish")
    assert api.cafe_event_action(api.CafeEventRequest(**finish))["result"]["won"]
    before = dump()
    api.player_state()
    assert dump() == before
