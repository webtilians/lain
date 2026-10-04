"""Exercise the real HTTP boundary in a disposable server/world/port."""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="lain-chapter-http-") as scratch:
        db = Path(scratch)/"test.db"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, LAIN_WORLD_DB=str(db), LAIN_LLM_ENABLED="0",
                   LAIN_WORLD_CLOCK="0", LAIN_MEMORY_SEMANTIC="0",
                   LAIN_CHAPTER_ONE="1", LAIN_PROLOGUE_ENABLED="0",
                   LAIN_CITY_RESIDENTS_ENABLED="1", LAIN_REALITY_GENERATION="0")
        env["LAIN_CORPORATION"]="1" if any(flag in sys.argv for flag in ["--network","--workshop","--noema","--circles","--events"]) else "0"
        env["LAIN_WORKSHOP"]="1" if any(flag in sys.argv for flag in ["--workshop","--circles","--events"]) else "0"
        env["LAIN_NOEMA"]="1" if any(flag in sys.argv for flag in ["--noema","--circles"]) else "0"
        env["LAIN_CIRCLES"]="1" if "--circles" in sys.argv else "0"
        env["LAIN_CAFE_EVENTS"]="1" if "--events" in sys.argv else "0"
        env["LAIN_ARCADE_CATALOG"]="1" if "--arcade" in sys.argv else "0"
        env["LAIN_CODE_EXCHANGE"]="1" if "--exchange" in sys.argv else "0"
        if "--arcade" in sys.argv:
            spec=json.loads((ROOT/"server/content/cafe_catalog.json").read_text(encoding="utf-8"))
            entry=spec["entries"][0]
            entry.update(id="http_snake_buffer",game="signal_snake")
            spec["entries"]=[entry]
            custom=Path(scratch)/"catalog.json"
            custom.write_text(json.dumps(spec),encoding="utf-8")
            env["LAIN_ARCADE_CATALOG_PATH"]=str(custom)
        with (Path(scratch)/"server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.api:app",
                "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
            try:
                def request(path, payload=None):
                    req=Request(f"http://127.0.0.1:{port}"+path,
                        data=json.dumps(payload).encode() if payload is not None else None,
                        headers={"Content-Type":"application/json"})
                    with urlopen(req, timeout=30) as response:
                        return json.load(response)
                for _ in range(100):
                    try:
                        request("/health")
                        break
                    except (URLError, TimeoutError):
                        if process.poll() is not None:
                            raise RuntimeError("Disposable server failed to start")
                        time.sleep(.1)
                state=request("/api/v1/player/state")
                assert not state["chapter_one"]["active"]
                request("/api/v1/player/messages/MSG_BOOTSTRAP_001/ack", {})
                state=request("/api/v1/player/state")
                assert state["chapter_one"]["active"]
                command={"action":"WIRED", "target":"REPLY", "data":{}, "request_id":"http_reply_0001"}
                response=request("/api/v1/chapter-one/action", command)
                assert "UNKNOWN_REPLY" in {e["id"] for e in response["state"]["chapter_one"]["evidence"]}
                with sqlite3.connect(db) as conn:
                    before=list(conn.iterdump())
                conn.close()
                assert request("/api/v1/chapter-one/action", command)["result"]==response["result"]
                request("/api/v1/player/state")
                for changed, status in [
                    ({**command, "target":"SEARCH"}, 409),
                    ({**command, "request_id":"http_invalid_01", "data":{"choice":{}}},422),
                    ({**command, "request_id":"http_remote_001", "action":"TALK", "target":"PROFESSOR"},409),
                ]:
                    try:
                        request("/api/v1/chapter-one/action",changed)
                        raise AssertionError("Invalid request accepted")
                    except HTTPError as error:
                        assert error.code==status, error.code
                with sqlite3.connect(db) as conn:
                    assert list(conn.iterdump())==before
                conn.close()
                print("CHAPTER01_HTTP_OK activation=true retries=idempotent errors=409,422 polling=read_only")
                if "--events" in sys.argv:
                    state = request("/api/v1/player/state")
                    item = state["cafe_events"]["events"][0]
                    command = {"action":"START","data":{"event":item["id"]},"request_id":"http_event_start"}
                    for invalid, status in [
                        ({**command,"actor_id":"AGENT_K"},422),
                        ({**command,"data":{"event":item["id"],"score":"99999"}},409),
                        (command,409),
                    ]:
                        try:
                            request("/api/v1/cafe-events/action",invalid)
                            raise AssertionError("Forged event request accepted")
                        except HTTPError as error:
                            assert error.code == status
                    def move_event(destination):
                        request("/api/v1/player/step",{"action":"MOVE","target":destination})
                        return request("/api/v1/player/state")
                    move_event("APARTMENT_DISTRICT")
                    state = move_event("CAFE")
                    if "--arcade" in sys.argv:
                        practice=request("/api/v1/workshop/action",{"action":"ARCADE_START","data":{"game":"signal_snake"},"request_id":"http_snake_practice"})
                        result=request("/api/v1/workshop/action",{"action":"ARCADE_FINISH","data":{"run_id":practice["result"]["run_id"],"moves":"RRRRRDDDLLDLLDL"},"request_id":"http_snake_finish"})
                        assert result["result"]["won"]
                        assert result["state"]["workshop"]["snake_best_score"]==570
                        assert len(result["state"]["workshop"]["assets"])==2
                        assert result["state"]["workshop"]["best_score"]==0
                    while state["minute"] < item["opens"] or state["player"]["location"] != "CAFE":
                        state = move_event("APARTMENT_DISTRICT" if state["player"]["location"] == "CAFE" else "CAFE")
                    run = request("/api/v1/cafe-events/action", command)["result"]
                    # Five-package path, independently checked by the actual server.
                    sys.path.insert(0,str(ROOT))
                    from tests.test_cafe_events import route
                    moves="RRRRRDDDLLDLLDL" if run["board"].get("game_id")=="signal_snake" else route(run["board"])
                    finish = {"action":"FINISH","data":{"run_id":run["run_id"],"moves":moves},"request_id":"http_event_finish"}
                    result = request("/api/v1/cafe-events/action",finish)
                    assert result["result"]["won"]
                    assert not result["state"]["cafe_events"]["events"][0]["won"]
                    assert request("/api/v1/cafe-events/action",finish)["result"] == result["result"]
                    state = result["state"]
                    while state["minute"] < item["closes"]:
                        state = move_event("APARTMENT_DISTRICT" if state["player"]["location"] == "CAFE" else "CAFE")
                    closed = next(e for e in state["cafe_events"]["events"] if e["id"] == item["id"])
                    assert closed["won"] and closed["settled"]
                    if state["player"]["location"] == "CAFE":
                        move_event("APARTMENT_DISTRICT")
                    move_event("APARTMENT")
                    compiled = request("/api/v1/workshop/action",{"action":"COMPILE","data":{"source":'use("routing")\nuse("buffer")\n'},"request_id":"http_event_compile"})
                    assert compiled["result"]["passed"]
                    with sqlite3.connect(db) as conn: before=list(conn.iterdump())
                    conn.close()
                    request("/api/v1/player/state")
                    with sqlite3.connect(db) as conn: assert list(conn.iterdump())==before
                    conn.close()
                    print("CAFE_EVENTS_HTTP_OK calendar=true location=true score=replayed reward=once compilation=true")
                    if "--arcade" in sys.argv:
                        print("ARCADE_CATALOG_HTTP_OK custom_catalog=true snake_replay=true practice_has_no_prize=true")
                    if "--exchange" in sys.argv:
                        def trade(action, data, key):
                            return request("/api/v1/code-exchange/action",{"action":action,"data":data,"request_id":key})
                        for destination in ["APARTMENT_DISTRICT","NIGHTCLUB"]: move_event(destination)
                        trade("CONTACT",{"peer":"RYOKO"},"http_exchange_ryoko")
                        for destination in ["APARTMENT_DISTRICT","CAFE"]: move_event(destination)
                        trade("CONTACT",{"peer":"KISSA_TECH"},"http_exchange_tech")
                        command={"action":"ACCEPT","data":{"offer":"ryoko_scan_v1","asset":"event_"+item["id"]},"request_id":"http_exchange_accept"}
                        for invalid,status in [({**command,"actor_id":"AGENT_K"},422),(command,409),
                            ({**command,"data":{"offer":"ryoko_scan_v1","asset":True}},422)]:
                            try:
                                request("/api/v1/code-exchange/action",invalid)
                                raise AssertionError("Invalid exchange accepted")
                            except HTTPError as error: assert error.code==status
                        for destination in ["APARTMENT_DISTRICT","APARTMENT"]: move_event(destination)
                        result=request("/api/v1/code-exchange/action",command)
                        assert result["result"]["sent"]["source"].startswith("Kissa")
                        assert result["result"]["received"]["model"]=="scan"
                        with sqlite3.connect(db) as conn: before=list(conn.iterdump())
                        conn.close()
                        assert request("/api/v1/code-exchange/action",command)["result"]==result["result"]
                        request("/api/v1/player/state")
                        with sqlite3.connect(db) as conn: assert list(conn.iterdump())==before
                        conn.close()
                        second=trade("ACCEPT",{"offer":"kissa_shield_v1","asset":result["result"]["received"]["asset"]},"http_exchange_second")
                        assert second["result"]["sent"]["source"]==result["result"]["received"]["source"]
                        assets=second["state"]["workshop"]["assets"]
                        assert {"event_"+item["id"],"exchange_ryoko_scan_v1","exchange_kissa_shield_v1"} <= {a["id"] for a in assets}
                        assert second["state"]["workshop"]["modules"]==["routing","buffer"]
                        assert len(second["state"]["code_exchange"]["history"])==2
                        print("CODE_EXCHANGE_HTTP_OK prize_to_copy=true two_contacts=true provenance=true retries=once own_program=preserved")
                if "--network" in sys.argv:
                    for destination in ["APARTMENT_DISTRICT","STATION"]:
                        request("/api/v1/player/step",{"action":"MOVE","target":destination})
                    command={"action":"INSPECT","relay":"RELAY_STATION","request_id":"http_network_inspect"}
                    request("/api/v1/network/action",command)
                    command.update(action="CLAIM",request_id="http_network_claim")
                    result=request("/api/v1/network/action",command)
                    assert len(result["state"]["network_conflict"]["pending"])==1
                    with sqlite3.connect(db) as conn:
                        before=list(conn.iterdump())
                    conn.close()
                    assert request("/api/v1/network/action",command)["result"]==result["result"]
                    try:
                        request("/api/v1/network/action",{**command,"actor_id":"AGENT_K"})
                        raise AssertionError("Client-selected identity accepted")
                    except HTTPError as error:
                        assert error.code==422
                    request("/api/v1/player/state")
                    with sqlite3.connect(db) as conn:
                        assert list(conn.iterdump())==before
                    conn.close()
                    print("CONFLICT01_HTTP_OK movement=authoritative identity=server_bound retry=idempotent")
                if "--noema" in sys.argv:
                    for destination in ["APARTMENT_DISTRICT","SCHOOL","SCHOOL_LAB"]:
                        request("/api/v1/player/step",{"action":"MOVE","target":destination})
                    counter=0
                    def network(action, faction="KAGAMI"):
                        nonlocal counter
                        counter+=1
                        command={"action":action,"relay":"RELAY_SCHOOL","faction":faction,
                                 "request_id":f"http_noema_{counter:04}"}
                        response=request("/api/v1/network/action",command)
                        assert request("/api/v1/network/action",command)["result"]==response["result"]
                        return response
                    network("INSPECT")
                    network("CLAIM","NOEMA")
                    # Movement advances the authoritative clock without changing it in SQL.
                    for destination in ["SCHOOL","SCHOOL_LAB"]:
                        request("/api/v1/player/step",{"action":"MOVE","target":destination})
                    network("CLAIM","KAGAMI")
                    network("INSPECT")
                    response=network("TALK","NOEMA")
                    assert len(response["state"]["network_conflict"]["pending"])==2
                    response=network("EXPOSE","NOEMA")
                    pending=response["state"]["network_conflict"]["pending"]
                    assert len(pending)==1 and pending[0]["operator"]=="KAGAMI"
                    relay=next(r for r in response["state"]["network_conflict"]["relays"] if r["id"]=="RELAY_SCHOOL")
                    assert relay["mine"]==40
                    assert sum(r["control"] for r in relay["controllers"])+relay["mine"]==100
                    with sqlite3.connect(db) as conn:
                        before=list(conn.iterdump())
                    conn.close()
                    for invalid, status in [
                        ({"action":"CLAIM","relay":"RELAY_SCHOOL","faction":"NOEMA",
                          "request_id":"http_noema_forged","actor_id":"AGENT_K"},422),
                        ({"action":"CLAIM","relay":"RELAY_SCHOOL","faction":"MISSING",
                          "request_id":"http_noema_invalid"},409),
                    ]:
                        try:
                            request("/api/v1/network/action",invalid)
                            raise AssertionError("Invalid corporate request accepted")
                        except HTTPError as error:
                            assert error.code==status
                    request("/api/v1/player/state")
                    with sqlite3.connect(db) as conn:
                        assert list(conn.iterdump())==before
                    conn.close()
                    print("NOEMA01_HTTP_OK two_orders=true scoped_exposure=true control=conserved retries=idempotent")
                if "--circles" in sys.argv:
                    counter=0
                    def move(*destinations):
                        for destination in destinations:
                            request("/api/v1/player/step",{"action":"MOVE","target":destination})
                    def action(system, verb, **data):
                        nonlocal counter
                        counter+=1
                        command={"action":verb,"request_id":f"http_circles_{counter:04}"}
                        if system=="network": command.update(data)
                        else: command["data"]=data
                        endpoint=f"/api/v1/{system}/action"
                        response=request(endpoint,command)
                        assert request(endpoint,command)["result"]==response["result"]
                        return response
                    move("APARTMENT_DISTRICT","SCHOOL","SCHOOL_LAB")
                    action("workshop","LESSON")
                    move("SCHOOL","APARTMENT_DISTRICT","APARTMENT")
                    source="def next_cell(alive, neighbors):\n    return neighbors == 3 or (alive and neighbors == 2)\n"
                    assert action("workshop","TEST_LIFE",source=source)["result"]["passed"]
                    action("workshop","DEVICE",id="life_matrix",active=True)
                    action("circles","CREATE",name="Círculo HTTP")
                    for ident in ["home_navi","first_connection","life_matrix","life_shield"]:
                        action("circles","CONTRIBUTE",id=ident,active=True)
                    move("APARTMENT_DISTRICT","NIGHTCLUB")
                    action("circles","CONTACT",target="RYOKO")
                    move("APARTMENT_DISTRICT","APARTMENT")
                    action("circles","INVITE",target="RYOKO")
                    response=action("circles","COMPILE",source='use("routing")\nuse("shield")\nuse("scan")')
                    assert response["result"]["passed"]
                    assert response["state"]["circles"]["group"]["capacity"]==11
                    assert response["state"]["workshop"]["modules"]==["routing"]
                    move("APARTMENT_DISTRICT","SCHOOL","SCHOOL_LAB")
                    action("network","INSPECT",relay="RELAY_SCHOOL")
                    action("network","CLAIM",relay="RELAY_SCHOOL",faction="NOEMA")
                    move("SCHOOL","SCHOOL_LAB")
                    action("network","PROGRAM_SHIELD",relay="RELAY_SCHOOL")
                    move("SCHOOL","APARTMENT_DISTRICT","APARTMENT")
                    assert "NOEMA" in action("workshop","SCAN",relay="RELAY_SCHOOL")["result"]["text"]
                    response=action("circles","REMOVE",target="RYOKO")
                    assert response["state"]["workshop"]["shared_modules"]==[]
                    assert response["state"]["circles"]["group"]["draft"]
                    with sqlite3.connect(db) as conn: before=list(conn.iterdump())
                    conn.close()
                    for endpoint, invalid, status in [
                        ("circles",{"action":"CREATE","data":{"name":"Falso"},"actor_id":"AGENT_K","request_id":"circles_forged_01"},422),
                        ("circles",{"action":"CONTRIBUTE","data":{"id":"home_navi","active":1},"request_id":"circles_invalid_01"},422),
                        ("workshop",{"action":"SCAN","data":{"relay":"RELAY_SCHOOL"},"request_id":"circles_revoked_01"},409),
                    ]:
                        try:
                            request(f"/api/v1/{endpoint}/action",invalid)
                            raise AssertionError("Invalid or revoked action accepted")
                        except HTTPError as error:
                            assert error.code==status
                    request("/api/v1/player/state")
                    with sqlite3.connect(db) as conn: assert list(conn.iterdump())==before
                    conn.close()
                    print("CIRCLES01_HTTP_OK consent=true capacity=11 shared_defense=true shared_scan=true revocation=true")
                if "--workshop" in sys.argv:
                    counter=0
                    def workshop(action, **data):
                        nonlocal counter
                        counter+=1
                        return request("/api/v1/workshop/action",{"action":action,"data":data,"request_id":f"http_workshop_{counter:04}"})
                    for destination in ["APARTMENT_DISTRICT","SCHOOL","SCHOOL_LAB"]:
                        request("/api/v1/player/step",{"action":"MOVE","target":destination})
                    workshop("LESSON")
                    for destination in ["SCHOOL","APARTMENT_DISTRICT","APARTMENT"]:
                        request("/api/v1/player/step",{"action":"MOVE","target":destination})
                    source="def next_cell(alive, neighbors):\n    return neighbors == 3 or (alive and neighbors == 2)\n"
                    result=workshop("TEST_LIFE",source=source)
                    assert result["result"]["passed"]
                    workshop("DEVICE",id="life_matrix",active=True)
                    assert workshop("COMPILE",source='use("routing")\nuse("shield")')["result"]["passed"]
                    for destination in ["APARTMENT_DISTRICT","CAFE"]:
                        request("/api/v1/player/step",{"action":"MOVE","target":destination})
                    start=workshop("ARCADE_START")["result"]
                    result=workshop("ARCADE_FINISH",run_id=start["run_id"],moves="DDRDRRRRRDDDDR")
                    assert result["result"]["won"]
                    for invalid in [
                        {"action":"ARCADE_START","data":{},"request_id":"http_fake_actor","actor_id":"AGENT_K"},
                        {"action":"TEST_LIFE","data":{"source":[]},"request_id":"http_fake_source"},
                    ]:
                        try:
                            request("/api/v1/workshop/action",invalid)
                            raise AssertionError("Invalid workshop request accepted")
                        except HTTPError as error:
                            assert error.code==422
                    print("WORKSHOP01_HTTP_OK lesson=true build=true arcade=true identity=server_bound")
            finally:
                if os.name=="nt":
                    # The Windows venv launcher spawns a child interpreter.
                    # Stop only this disposable process tree, not other servers.
                    subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],
                                   capture_output=True, check=True)
                else:
                    process.terminate()
                process.wait(timeout=20)


if __name__=="__main__":
    main()
