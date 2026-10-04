"""Data-only expansion, pinned editions and server/client-independent snake checks."""
import copy
import json
import uuid

import pytest

from server.world_core import arcade_catalog as cat, signal_snake as snake
from server.world_core import cafe_events as ev, workshop as ws, network_conflict as net
from server.world_core.simulation import Simulation
from server.world_core.player_view import build_player_snapshot
from server.world_core.wired import process_wired_message_acknowledgement

WIN = "RRRRRDDDLLDLLDL"


@pytest.fixture
def game(monkeypatch):
    cat.current.cache_clear()
    monkeypatch.delenv("LAIN_ARCADE_CATALOG_PATH",raising=False)
    for flag in ("WORKSHOP","CORPORATION","CAFE_EVENTS","ARCADE_CATALOG"):
        monkeypatch.setenv("LAIN_"+flag,"1")
    for flag in ("LLM_ENABLED","PROLOGUE_ENABLED","WORLD_CLOCK","CITY_RESIDENTS_ENABLED","REALITY_GENERATION"):
        monkeypatch.setenv("LAIN_"+flag,"0")
    sim = Simulation()
    process_wired_message_acknowledgement("MSG_BOOTSTRAP_001","PLAYER_1",sim.minute)
    with net.connection() as c:
        c.execute("UPDATE agents SET location='CAFE' WHERE id='PLAYER_1'")
    build_player_snapshot()
    yield sim
    cat.current.cache_clear()


def action(system, verb, **data):
    call = ws.perform_workshop_action if system == "practice" else ev.perform_event_action
    return call("PLAYER_1",verb,data,uuid.uuid4().hex)


def clock(minute):
    with net.connection() as c:
        c.execute("UPDATE simulation_state SET minute=? WHERE id=1",(minute,))
    ev.advance_events(minute)


def dump():
    with net.connection() as c: return list(c.iterdump())


@pytest.mark.parametrize("variant", range(4))
def test_snake_rotations_and_perfect_route(variant):
    horizontal = str.maketrans("LR","RL") if variant & 1 else {}
    vertical = str.maketrans("UD","DU") if variant & 2 else {}
    path = WIN.translate(horizontal).translate(vertical)
    result = snake.replay(path,snake.board(variant))
    assert result["finished"] and result["won"] and not result["collision"]
    assert result["collected"] == 6 and result["score"] == 570
    assert len(result["snake"]) == 9
    assert result["food"] not in result["snake"]
    with pytest.raises(ValueError,match="ARCADE_ALREADY_FINISHED"):
        snake.replay(path+"U",snake.board(variant))


@pytest.mark.parametrize("moves", ["L","UU","RDDLLL"])
def test_collision_ends_without_free_score(moves):
    result = snake.replay(moves,snake.board())
    assert result["finished"] and result["collision"] and not result["won"]


def test_tail_moves_out_of_the_way_and_growth_blocks_occupied_square():
    layout = snake.board()
    layout["snake"] = [[1,1],[1,2],[0,2],[0,1]]
    result = snake.replay("L",layout)
    assert not result["collision"] and result["snake"][0] == [0,1]
    assert len(result["snake"]) == 4
    layout["foods"] = [[1,1],[1,2],[0,2],[0,1],[3,1]]
    state = snake.replay("",layout)
    assert state["food"] == [3,1] and state["food_index"] == 4


def test_partial_path_and_move_limit_have_same_server_semantics():
    result = snake.replay("RR",snake.board())
    assert not result["finished"] and result["collected"] == 1 and result["score"] == 0
    # A small cycle away from food survives to the cap but cannot rank.
    result = snake.replay("DRUL"*20,snake.board())
    assert result["finished"] and not result["won"] and not result["collision"]
    for moves in ("X","R"*81,None):
        with pytest.raises(ValueError,match="INVALID_ARCADE_MOVES"):
            snake.replay(moves,snake.board())


@pytest.mark.parametrize("variant", range(4))
@pytest.mark.parametrize("target",[3,4])
def test_npc_marks_use_legal_replays(variant,target):
    moves = snake.npc_route(variant,target)
    result = snake.replay(moves,snake.board(variant))
    assert result["won"] and result["collected"] == target and len(moves) <= 80


def test_catalog_contains_only_supported_rules_and_prizes():
    spec = cat.load()
    assert {e["game"] for e in spec["entries"]} == set(cat.GAMES)
    assert spec["revision"] == 1


@pytest.mark.parametrize("change,error", [
    (lambda s:s.update(revision=True),"CATALOG_REVISION"),
    (lambda s:s.update(entries=[]),"CATALOG_ENTRIES"),
    (lambda s:s.update(entries=s["entries"]*9),"CATALOG_ENTRIES"),
    (lambda s:s["entries"].append(copy.deepcopy(s["entries"][0])),"CATALOG_ENTRY_ID"),
    (lambda s:s["entries"][0].update(game="exec"),"CATALOG_GAME"),
    (lambda s:s["entries"][0].update(game=[]),"CATALOG_GAME"),
    (lambda s:s["entries"][0].update(source="import os"),"CATALOG_ENTRY_FIELDS"),
    (lambda s:s["entries"][0].update(orientations=[True]),"CATALOG_ORIENTATIONS"),
    (lambda s:s["entries"][0].update(orientations=[0,0]),"CATALOG_ORIENTATIONS"),
    (lambda s:s["entries"][0]["prize"].update(model="unlimited_power"),"CATALOG_PRIZE"),
    (lambda s:s["entries"][0]["prize"].update(kind=[]),"CATALOG_PRIZE"),
])
def test_malformed_catalog_rejected_without_executing_data(change,error):
    spec = copy.deepcopy(cat.load())
    change(spec)
    with pytest.raises(ValueError,match=error):
        cat.validate(spec)


def test_file_size_and_malformed_json_are_bounded(tmp_path):
    path=tmp_path/"catalog.json"
    for raw,error in [(b"x"*65537,"CATALOG_TOO_LARGE"),(b"{","CATALOG_JSON"),(b"\xff","CATALOG_JSON")]:
        path.write_bytes(raw)
        with pytest.raises(ValueError,match=error): cat.load(path)


def test_practice_is_isolated_from_prizes_best_scores_and_circle_requirements(game):
    run=action("practice","ARCADE_START",game="signal_snake")
    with pytest.raises(ValueError,match="ARCADE_NOT_FINISHED"):
        action("practice","ARCADE_FINISH",run_id=run["run_id"],moves="RR")
    result=action("practice","ARCADE_FINISH",run_id=run["run_id"],moves=WIN)
    assert result["won"] and result["score"] == 570
    view=ws.workshop_snapshot()
    assert view["best_score"] == 0 and view["snake_best_score"] == 570
    assert len(view["assets"]) == 2
    assert not any(a["id"] == "courier_interface" for a in view["assets"])
    assert not any(r["mine"] for e in ev.event_snapshot()["events"] for r in e["ranking"])
    with net.connection() as c: c.execute("UPDATE agents SET location='APARTMENT' WHERE id='PLAYER_1'")
    with pytest.raises(ValueError,match="WORKSHOP_WRONG_LOCATION"):
        action("practice","ARCADE_START",game="signal_snake")


def test_existing_practice_keeps_board_on_restart_or_disabling_catalog(game,monkeypatch):
    run=action("practice","ARCADE_START",game="signal_snake")
    monkeypatch.setenv("LAIN_ARCADE_CATALOG","0")
    Simulation()
    result=action("practice","ARCADE_FINISH",run_id=run["run_id"],moves=WIN)
    assert result["collected"] == 6
    with pytest.raises(ValueError,match="ARCADE_GAME_UNAVAILABLE"):
        action("practice","ARCADE_START",game="signal_snake")
    assert not ws.workshop_snapshot()["arcade_catalog"]


def test_game_score_board_and_identity_cannot_be_chosen_in_tournament_payload(game):
    clock(ev.LEAD+ev.PERIOD)
    run=action("event","START",event="KISSA_000002")
    assert run["board"]["game_id"] == "signal_snake"
    with pytest.raises(ValueError,match="INVALID_EVENT_DATA"):
        action("event","FINISH",run_id=run["run_id"],moves=WIN,game="bit_courier")
    with pytest.raises(ValueError,match="EVENT_RUN_REQUIRED"):
        ev.perform_event_action("PLAYER_1","FINISH",{"run_id":"another_account","moves":WIN},uuid.uuid4().hex)
    result=action("event","FINISH",run_id=run["run_id"],moves=WIN)
    assert result["won"]
    clock(ev.LEAD+ev.PERIOD+ev.DURATION)
    view=ws.workshop_snapshot()
    prize=next(a for a in view["assets"] if a["id"] == "event_KISSA_000002")
    assert prize["model"] == "cache" and prize["ownership"] == "OWNED"
    assert view["best_score"] == 0 and view["snake_best_score"] == 0


def test_announced_events_and_inflight_runs_survive_catalog_change(game,tmp_path,monkeypatch):
    clock(ev.LEAD+ev.PERIOD)
    run=action("event","START",event="KISSA_000002")
    with net.connection() as c:
        old=c.execute("SELECT * FROM cafe_events ORDER BY id").fetchall()
        opponents=c.execute("SELECT * FROM cafe_entries ORDER BY event,actor").fetchall()
    spec={"revision":2,"entries":[{"id":"new_reward","game":"bit_courier","orientations":[3],"prize":{"kind":"CODE","model":"routing"}}]}
    path=tmp_path/"custom.json"
    path.write_text(json.dumps(spec),encoding="utf-8")
    monkeypatch.setenv("LAIN_ARCADE_CATALOG_PATH",str(path))
    cat.current.cache_clear()  # Simulate loading the changed catalogue on restart.
    ev.initialize_events()
    with net.connection() as c:
        assert c.execute("SELECT * FROM cafe_events ORDER BY id").fetchall() == old
        assert c.execute("SELECT * FROM cafe_entries ORDER BY event,actor").fetchall() == opponents
    assert action("event","FINISH",run_id=run["run_id"],moves=WIN)["won"]
    clock(ev.LEAD+2*ev.PERIOD)
    with net.connection() as c:
        row=c.execute("SELECT board,prize_model FROM cafe_events WHERE edition=4").fetchone()
    assert json.loads(row[0])["catalog_revision"] == 2 and row[1] == "routing"


def test_legacy_event_boards_are_unchanged_when_enabling_catalog(game,monkeypatch):
    with net.connection() as c:
        c.execute("DELETE FROM cafe_events")
        c.execute("DELETE FROM cafe_entries")
    monkeypatch.setenv("LAIN_ARCADE_CATALOG","0")
    ev.initialize_events()
    before=dump()
    monkeypatch.setenv("LAIN_ARCADE_CATALOG","1")
    ev.initialize_events()
    assert dump() == before
    assert all(e["game_id"] == "bit_courier" for e in ev.event_snapshot()["events"])
    clock(ev.LEAD+ev.PERIOD)
    assert action("event","START",event="KISSA_000002")["board"].get("game_id","bit_courier") == "bit_courier"


def test_snapshots_are_read_only_and_do_not_expose_saved_routes(game):
    before=dump()
    state=build_player_snapshot()
    assert dump() == before
    items=state["cafe_events"]["events"]
    assert items[1]["game_name"] == snake.NAME and "snake" in items[1]["catalog_entry"]
    assert "foods" not in json.dumps(items)
