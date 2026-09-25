"""Local vertical slice: provenance, bounded lessons, builds and café practice.

Identity, ownership, location, rewards and deployment are server-owned. The
feature is opt-in and never executes submitted Python or alters private memory.
"""
import json
import os
import re

from .code_lab import LIFE_TEMPLATE, LIFE_HINT, LessonError, program_modules, test_life
from .network_conflict import connection, report, RELAYS

MODULES = {
    "routing": {"name": "Enrutamiento", "cost": 2, "effect": "Conexión del montaje; conserva las acciones básicas del enlace."},
    "shield": {"name": "Protección", "cost": 4, "effect": "Preparar las dos defensas de un enlace propio con una operación local."},
    "scan": {"name": "Exploración", "cost": 3, "effect": "Desde casa, leer la actividad de un enlace previamente examinado."},
}
DEVICES = {"navi": ("Navi A", 4), "matrix": ("Coprocesador M", 4), "interface": ("Interfaz R", 3)}
ARCADE = {"size": 8, "start": [0, 0], "exit": [7, 7],
          "walls": [[2,0],[2,1],[2,2],[4,2],[5,2],[6,2],[1,4],[2,4],[3,4],[5,4],[5,5],[5,6]],
          "chips": [[1,2],[3,1],[6,3],[2,6],[6,6]], "max_moves": 80, "version": 1}
OFFERS = {
    "KAGAMI": "Contrato local KAGAMI: préstamo de un segundo Navi A y cobertura que absorbe 15 puntos de cada intervención. La copia no duplica capacidad. Reservas 1 unidad de cálculo mientras dure el acuerdo. Puedes terminarlo desde este PC; se retiran préstamo y cobertura. No se envían conversaciones ni recuerdos.",
    "NOEMA": "Contrato local NOEMA: acceso prestado al módulo Exploración. Reserva 1 unidad de cálculo. Los escaneos posteriores entregan a NOEMA únicamente relay, minuto y número de intervenciones sobre tu cuenta. Puedes terminarlo; se retira el permiso, no tus fragmentos propios. No incluye testimonios ni memorias privadas.",
}


def exists(c):
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='workshop_players'").fetchone() is not None


def enabled(c):
    return os.getenv("LAIN_WORKSHOP", "0") == "1" and os.getenv("LAIN_CORPORATION", "0") == "1" and exists(c)


def _grant(c, actor, ident, kind, model, source, now, active=0):
    c.execute("INSERT OR IGNORE INTO workshop_assets VALUES(?,?,?,?,?,?,?,?)",
              (actor, ident, kind, model, source, now, active, "OWNED"))


def initialize_workshop():
    if os.getenv("LAIN_WORKSHOP", "0") != "1" or os.getenv("LAIN_CORPORATION", "0") != "1": return
    with connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS workshop_players (
          actor TEXT PRIMARY KEY, lesson INTEGER NOT NULL DEFAULT 0, life_source TEXT NOT NULL,
          draft TEXT NOT NULL, compiled TEXT NOT NULL, modules TEXT NOT NULL DEFAULT '[]',
          contract TEXT NOT NULL DEFAULT 'INDEPENDENT', best_score INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS workshop_assets (
          actor TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL, model TEXT NOT NULL,
          source TEXT NOT NULL, minute INTEGER NOT NULL, active INTEGER NOT NULL, ownership TEXT NOT NULL,
          PRIMARY KEY(actor,id));
        CREATE TABLE IF NOT EXISTS workshop_requests (
          actor TEXT NOT NULL, id TEXT NOT NULL, command TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(actor,id));
        CREATE TABLE IF NOT EXISTS workshop_runs (
          actor TEXT NOT NULL, id TEXT NOT NULL, minute INTEGER NOT NULL, status TEXT NOT NULL,
          moves TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(actor,id));
        CREATE TABLE IF NOT EXISTS workshop_contract_reports (
          actor TEXT NOT NULL, recipient TEXT NOT NULL, relay TEXT NOT NULL, minute INTEGER NOT NULL,
          pending INTEGER NOT NULL);
        """)
    enroll_workshop()


def enroll_workshop():
    with connection() as c:
        if not enabled(c): return
        c.execute("BEGIN IMMEDIATE")
        now = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        for (actor,) in c.execute("SELECT actor_id FROM network_players JOIN agents ON agents.id=actor_id WHERE controller_type='HUMAN'").fetchall():
            created = c.execute("INSERT OR IGNORE INTO workshop_players(actor,life_source,draft,compiled,modules) VALUES(?,?,?,?,?)",
                (actor,LIFE_TEMPLATE,'use("routing")\n','use("routing")\n','["routing"]')).rowcount
            if created:
                _grant(c,actor,"home_navi","DEVICE","navi","Ordenador de casa",now,1)
                _grant(c,actor,"first_connection","CODE","routing","Tu primera conexión a la Wired",now)
                report(c,actor,now,"WORKSHOP","El PC dispone de un taller de código. En Kissa Café han instalado un terminal: su técnico busca ayuda para comprobar un coprocesador.")


def resources(c, actor):
    devices = {model for (model,) in c.execute("SELECT model FROM workshop_assets WHERE actor=? AND kind='DEVICE' AND active=1",(actor,))}
    owned = {model for (model,) in c.execute("SELECT model FROM workshop_assets WHERE actor=? AND kind='CODE'",(actor,))}
    row = c.execute("SELECT contract FROM workshop_players WHERE actor=?",(actor,)).fetchone()
    contract = row[0] if row else "INDEPENDENT"
    if contract == "NOEMA": owned.add("scan")
    capacity = max(0,sum(DEVICES[d][1] for d in devices) - (contract != "INDEPENDENT"))
    return capacity, owned


def _build_valid(c, actor, modules):
    capacity, owned = resources(c,actor)
    if any(m not in owned or m not in MODULES for m in modules): return False
    return sum(MODULES[m]["cost"] for m in set(modules)) <= capacity


def has_module(c, actor, module):
    if not enabled(c): return False
    row = c.execute("SELECT modules FROM workshop_players WHERE actor=?",(actor,)).fetchone()
    if not row: return False
    modules = json.loads(row[0])
    return module in modules and _build_valid(c,actor,modules)


def corporate_cover(c, actor):
    if not enabled(c): return 0
    row=c.execute("SELECT contract FROM workshop_players WHERE actor=?",(actor,)).fetchone()
    return 15 if row == ("KAGAMI",) else 0


def _repair_build(c, actor):
    row=c.execute("SELECT modules FROM workshop_players WHERE actor=?",(actor,)).fetchone()
    if not _build_valid(c,actor,json.loads(row[0])):
        c.execute("UPDATE workshop_players SET modules='[\"routing\"]',compiled=? WHERE actor=?",('use("routing")\n',actor))
        return " El montaje activo ha vuelto a Enrutamiento porque faltan recursos o permisos; tu borrador sigue guardado."
    return ""


def arcade_replay(moves):
    if not isinstance(moves,str) or len(moves)>ARCADE["max_moves"] or any(ch not in "UDLR" for ch in moves):
        raise ValueError("INVALID_ARCADE_MOVES")
    x,y=ARCADE["start"]
    collected=set()
    walls={tuple(p) for p in ARCADE["walls"]}
    chips={tuple(p) for p in ARCADE["chips"]}
    finished=False
    for index,direction in enumerate(moves):
        if finished: raise ValueError("ARCADE_ALREADY_FINISHED")
        dx,dy={"U":(0,-1),"D":(0,1),"L":(-1,0),"R":(1,0)}[direction]
        nx,ny=x+dx,y+dy
        if 0<=nx<8 and 0<=ny<8 and (nx,ny) not in walls: x,y=nx,ny
        if (x,y) in chips: collected.add((x,y))
        finished=[x,y]==ARCADE["exit"]
    score=max(0,len(collected)*100-len(moves)*2) if finished else 0
    return {"score":score,"collected":len(collected),"finished":finished,"won":finished and len(collected)>=3}


def perform_workshop_action(actor, action, data, request_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}",request_id): raise ValueError("INVALID_REQUEST_ID")
    if not isinstance(data,dict) or len(json.dumps(data))>12000: raise ValueError("INVALID_WORKSHOP_DATA")
    command=json.dumps([action,data],sort_keys=True)
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        if not enabled(c): raise ValueError("WORKSHOP_DISABLED")
        player=c.execute("SELECT lesson,contract FROM workshop_players WHERE actor=?",(actor,)).fetchone()
        if not player: raise ValueError("WIRED_CONNECTION_REQUIRED")
        old=c.execute("SELECT command,result FROM workshop_requests WHERE actor=? AND id=?",(actor,request_id)).fetchone()
        if old:
            if old[0]!=command: raise ValueError("REQUEST_ID_REUSED")
            return json.loads(old[1])
        location=c.execute("SELECT location FROM agents WHERE id=? AND controller_type='HUMAN'",(actor,)).fetchone()
        if not location: raise ValueError("HUMAN_PLAYER_REQUIRED")
        location=location[0]
        places={"LESSON":"SCHOOL_LAB","TECHNICIAN":"CAFE","ARCADE_START":"CAFE","ARCADE_FINISH":"CAFE"}
        if location!=places.get(action,"APARTMENT"): raise ValueError("WORKSHOP_WRONG_LOCATION")
        now=c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        result={"text":""}
        if action=="TECHNICIAN":
            _grant(c,actor,"cafe_routing_copy","CODE","routing","Copia del técnico de Kissa Café",now)
            result["text"]="Técnico: «Este coprocesador será tuyo si haces funcionar el Juego de la Vida. El profesor tiene las reglas en el aula de informática. Te dejo otra copia de Enrutamiento: no duplica potencia. En este terminal también puedes practicar Bit Courier.»"
        elif action=="LESSON":
            c.execute("UPDATE workshop_players SET lesson=max(1,lesson) WHERE actor=?",(actor,))
            result["text"]="Profesor: «Una célula nace con tres vecinas. Si ya vive, sobrevive con dos o tres. Las demás mueren. En tu PC completa next_cell(alive, neighbors); el tablero contará los ocho vecinos. Puedes consultar las reglas fuera del juego.»"
        elif action in {"SAVE_LIFE","TEST_LIFE"}:
            if player[0]<1: raise ValueError("LESSON_REQUIRED")
            source=data.get("source","")
            if not isinstance(source,str) or len(source)>4000: raise ValueError("INVALID_SOURCE")
            c.execute("UPDATE workshop_players SET life_source=? WHERE actor=?",(source,actor))
            if action=="SAVE_LIFE": result["text"]="Ejercicio guardado."
            else:
                result=test_life(source)
                if result["passed"]:
                    c.execute("UPDATE workshop_players SET lesson=2 WHERE actor=?",(actor,))
                    _grant(c,actor,"life_matrix","DEVICE","matrix","Juego de la Vida · validado en el PC",now)
                    _grant(c,actor,"life_shield","CODE","shield","Juego de la Vida · módulo del coprocesador",now)
                    result["text"]+=" Coprocesador M y Protección disponibles. Conecta el equipo en Dispositivos e integra el módulo en Código."
        elif action in {"SAVE_PROGRAM","COMPILE"}:
            source=data.get("source","")
            if not isinstance(source,str) or len(source)>4000: raise ValueError("INVALID_SOURCE")
            c.execute("UPDATE workshop_players SET draft=? WHERE actor=?",(source,actor))
            result["text"]="Borrador guardado."
            if action=="COMPILE":
                try:
                    modules=program_modules(source)
                    capacity,owned=resources(c,actor)
                    if any(m not in owned for m in modules): raise LessonError("Incluyes un módulo que todavía no posees. Revisa la biblioteca.")
                    cost=sum(MODULES[m]["cost"] for m in modules)
                    if cost>capacity: raise LessonError(f"El montaje necesita {cost} unidades y tienes {capacity}. Conecta equipos o reduce módulos.")
                    c.execute("UPDATE workshop_players SET compiled=?,modules=? WHERE actor=?",(source,json.dumps(modules),actor))
                    result={"text":f"Montaje validado y activo · consumo {cost}/{capacity}. Las líneas repetidas cuentan una vez.","passed":True}
                except LessonError as error:
                    result={"text":str(error)+" La última versión válida sigue activa.","passed":False}
        elif action=="DEVICE":
            ident=data.get("id","")
            active=data.get("active")
            if type(active) is not bool: raise ValueError("INVALID_DEVICE_STATE")
            if ident=="home_navi" and not active: raise ValueError("BASE_DEVICE_REQUIRED")
            if c.execute("UPDATE workshop_assets SET active=? WHERE actor=? AND id=? AND kind='DEVICE'",(int(active),actor,ident)).rowcount!=1: raise ValueError("DEVICE_NOT_OWNED")
            result["text"]="Conexión de dispositivo guardada."+_repair_build(c,actor)
        elif action=="CONTRACT":
            faction=data.get("faction")
            if faction not in {"KAGAMI","NOEMA","INDEPENDENT"}: raise ValueError("INVALID_CONTRACT")
            if player[0]<2: raise ValueError("OFFERS_NOT_AVAILABLE")
            c.execute("DELETE FROM workshop_assets WHERE actor=? AND ownership='LOAN'",(actor,))
            c.execute("UPDATE workshop_players SET contract=? WHERE actor=?",(faction,actor))
            if faction=="KAGAMI":
                c.execute("INSERT INTO workshop_assets VALUES(?,?,?,?,?,?,?,?)",(actor,"kagami_loan","DEVICE","navi","Préstamo de KAGAMI",now,1,"LOAN"))
            result["text"]=("Sigues por tu cuenta." if faction=="INDEPENDENT" else "Acuerdo activo. "+OFFERS[faction])+_repair_build(c,actor)
            report(c,actor,now,"WORKSHOP","Decisión contractual registrada: "+faction)
        elif action=="SCAN":
            relay=data.get("relay")
            if relay not in RELAYS: raise ValueError("INVALID_RELAY")
            if not has_module(c,actor,"scan"): raise ValueError("SCAN_MODULE_REQUIRED")
            if not c.execute("SELECT 1 FROM network_discoveries WHERE actor_id=? AND relay=?",(actor,relay)).fetchone(): raise ValueError("INSPECT_RELAY_FIRST")
            ops=c.execute("SELECT due_minute FROM network_operations WHERE target=? AND relay=? AND status='PENDING' ORDER BY due_minute",(actor,relay)).fetchall()
            result["text"]=RELAYS[relay][0]+": "+("intervención sobre tu cuenta en "+str(max(0,ops[0][0]-now))+" min del mundo." if ops else "sin intervenciones pendientes sobre tu cuenta.")
            protection=c.execute("SELECT suppressed_until FROM network_relays WHERE id=?",(relay,)).fetchone()[0]
            result["text"]+=f" Suspensión de nuevas órdenes: {max(0,protection-now)} min."
            report(c,actor,now,"WORKSHOP_SCAN",result["text"])
            if player[1]=="NOEMA":
                c.execute("INSERT INTO workshop_contract_reports VALUES(?,?,?,?,?)",(actor,"NOEMA",relay,now,len(ops)))
                result["text"]+=" NOEMA recibió: identificador del enlace, minuto y número de intervenciones sobre tu cuenta."
        elif action=="ARCADE_START":
            c.execute("UPDATE workshop_runs SET status='ABANDONED' WHERE actor=? AND status='OPEN'",(actor,))
            c.execute("INSERT INTO workshop_runs(actor,id,minute,status) VALUES(?,?,?,'OPEN')",(actor,request_id,now))
            result={"text":"BIT COURIER · Práctica local. Recoge al menos tres paquetes y llega a la salida en un máximo de 80 movimientos. Las paredes también consumen un movimiento. Sin clasificación online.","run_id":request_id,"board":ARCADE}
        elif action=="ARCADE_FINISH":
            run=data.get("run_id","")
            row=c.execute("SELECT status,moves,result FROM workshop_runs WHERE actor=? AND id=?",(actor,run)).fetchone()
            if not row or row[0]=="ABANDONED": raise ValueError("ARCADE_RUN_REQUIRED")
            moves=data.get("moves","")
            if row[0]=="FINISHED":
                if row[1]!=moves: raise ValueError("ARCADE_ALREADY_FINISHED")
                result=json.loads(row[2])
            else:
                replay=arcade_replay(moves)
                if not replay["finished"] and len(moves)<80: raise ValueError("ARCADE_NOT_FINISHED")
                c.execute("UPDATE workshop_players SET best_score=max(best_score,?) WHERE actor=?",(replay["score"],actor))
                result={**replay,"text":f"Puntuación verificada: {replay['score']} · paquetes: {replay['collected']}/5."}
                if replay["won"]:
                    _grant(c,actor,"courier_interface","DEVICE","interface","Bit Courier · desafío local completado",now)
                    _grant(c,actor,"courier_scan","CODE","scan","Bit Courier · desafío local completado",now)
                    result["text"]+=" Interfaz R y Exploración disponibles en tu PC. La recompensa se obtiene una vez."
                c.execute("UPDATE workshop_runs SET status='FINISHED',moves=?,result=? WHERE actor=? AND id=?",(moves,json.dumps(result),actor,run))
        else: raise ValueError("INVALID_WORKSHOP_ACTION")
        c.execute("INSERT INTO workshop_requests VALUES(?,?,?,?)",(actor,request_id,command,json.dumps(result,ensure_ascii=False)))
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'WORKSHOP',?,?)",(now,actor,action,result["text"]))
        return result


def workshop_snapshot(actor="PLAYER_1"):
    with connection() as c:
        if not enabled(c): return {"active":False}
        row=c.execute("SELECT lesson,life_source,draft,compiled,modules,contract,best_score FROM workshop_players WHERE actor=?",(actor,)).fetchone()
        if not row: return {"active":False}
        capacity,owned=resources(c,actor)
        assets=[dict(zip(["id","kind","model","source","minute","active","ownership"],a)) for a in c.execute("SELECT id,kind,model,source,minute,active,ownership FROM workshop_assets WHERE actor=? ORDER BY minute,id",(actor,))]
        for a in assets:
            a["name"]=DEVICES[a["model"]][0] if a["kind"]=="DEVICE" else MODULES[a["model"]]["name"]
            a["capacity"]=DEVICES[a["model"]][1] if a["kind"]=="DEVICE" else 0
        return {"active":True,"lesson":row[0],"life_source":row[1],"draft":row[2],"compiled":row[3],"modules":json.loads(row[4]),"contract":row[5],"best_score":row[6],"capacity":capacity,
                "cost":sum(MODULES[m]["cost"] for m in json.loads(row[4])),"assets":assets,"library":[{"id":m,**MODULES[m]} for m in MODULES if m in owned],
                "offers":OFFERS if row[0]>=2 else {},"life_hint":LIFE_HINT if row[0]>=1 else "","session_mode":"LOCAL"}
