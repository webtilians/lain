"""Local NPC circles: individually owned resources, deduplicated shared builds.

The shared program is separate from personal programs; their capacities never
stack. HTTP binds the human identity. No NPC memories enter the shared view.
"""
import json
import os
import re

from .network_conflict import connection

PARTNERS = {
    "RYOKO": {
        "name": "Ryoko", "location": "NIGHTCLUB",
        "condition": "Completa el Juego de la Vida y sigue independiente.",
        "motive": "Quiere que las identidades puedan circular sin depender de un administrador.",
        "assets": [("navi", "DEVICE"), ("interface", "DEVICE"), ("scan", "CODE")],
    },
    "KISSA_TECH": {
        "name": "Técnico de Kissa", "location": "CAFE",
        "condition": "Gana Bit Courier y sigue independiente.",
        "motive": "Quiere mantener las máquinas del café fuera del control corporativo.",
        "assets": [("matrix", "DEVICE"), ("shield", "CODE")],
    },
}


def enabled(c):
    from .workshop import enabled as workshop_enabled
    return (os.getenv("LAIN_CIRCLES", "0") == "1" and workshop_enabled(c)
            and c.execute("SELECT 1 FROM sqlite_master WHERE name='circle_groups'").fetchone() is not None)


def initialize_circles():
    from .workshop import enabled as workshop_enabled
    if os.getenv("LAIN_CIRCLES", "0") != "1": return
    with connection() as c:
        if not workshop_enabled(c): return
        c.executescript("""
        CREATE TABLE IF NOT EXISTS circle_groups (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, leader TEXT NOT NULL,
          created_minute INTEGER NOT NULL, draft TEXT NOT NULL DEFAULT '',
          compiled TEXT NOT NULL DEFAULT '', modules TEXT NOT NULL DEFAULT '[]',
          closed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS circle_members (
          actor TEXT PRIMARY KEY, circle INTEGER NOT NULL, joined_minute INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS circle_contacts (
          actor TEXT NOT NULL, peer TEXT NOT NULL, minute INTEGER NOT NULL, PRIMARY KEY(actor,peer));
        CREATE TABLE IF NOT EXISTS circle_contributions (
          circle INTEGER NOT NULL, actor TEXT NOT NULL, asset TEXT NOT NULL,
          shared_minute INTEGER NOT NULL, PRIMARY KEY(circle,actor,asset));
        CREATE TABLE IF NOT EXISTS circle_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, circle INTEGER NOT NULL,
          minute INTEGER NOT NULL, text TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS circle_requests (
          actor TEXT NOT NULL, id TEXT NOT NULL, command TEXT NOT NULL, result TEXT NOT NULL,
          PRIMARY KEY(actor,id));
        """)


def _member(c, actor):
    return c.execute("""SELECT g.id,g.name,g.leader,g.draft,g.compiled,g.modules
        FROM circle_members m JOIN circle_groups g ON g.id=m.circle
        WHERE m.actor=? AND g.closed=0""", (actor,)).fetchone()


def _independent(c, actor):
    return c.execute("SELECT contract FROM workshop_players WHERE actor=?", (actor,)).fetchone() == ("INDEPENDENT",)


def _human(c, actor):
    return c.execute("""SELECT a.location FROM agents a JOIN workshop_players w ON w.actor=a.id
                         WHERE a.id=? AND a.controller_type='HUMAN'""", (actor,)).fetchone()


def _name(c, actor):
    if actor in PARTNERS: return PARTNERS[actor]["name"]
    row = c.execute("SELECT name FROM agents WHERE id=?", (actor,)).fetchone()
    return row[0] if row else "Miembro"


def _ready(c, actor, peer):
    if not _independent(c, actor): return False
    if peer == "RYOKO":
        return c.execute("SELECT lesson FROM workshop_players WHERE actor=?", (actor,)).fetchone()[0] == 2
    return c.execute("SELECT 1 FROM workshop_assets WHERE actor=? AND id='courier_interface' AND ownership='OWNED'",
                     (actor,)).fetchone() is not None


def _asset(c, actor, ident):
    from .workshop import DEVICES, MODULES
    if actor in PARTNERS:
        for model, kind in PARTNERS[actor]["assets"]:
            if ident == kind + ":" + model:
                return kind, model, "Equipo de " + PARTNERS[actor]["name"], 0, True, ""
        return None
    row = c.execute("""SELECT kind,model,source,minute,active,ownership
                       FROM workshop_assets WHERE actor=? AND id=?""", (actor, ident)).fetchone()
    if not row: return None
    kind, model, source, minute, active, ownership = row
    if kind not in {"CODE", "DEVICE"} or model not in (DEVICES if kind == "DEVICE" else MODULES): return None
    reason = ""
    if ownership != "OWNED": reason = "El préstamo no puede aportarse."
    elif not _independent(c, actor): reason = "Aportación suspendida por contrato corporativo."
    elif kind == "DEVICE" and not active: reason = "Dispositivo desconectado."
    return kind, model, source, minute, not reason, reason


def pool(c, circle):
    from .workshop import DEVICES, MODULES
    contributions = []
    devices, modules = set(), set()
    rows = c.execute("""SELECT p.actor,p.asset,p.shared_minute
        FROM circle_contributions p JOIN circle_members m ON m.actor=p.actor AND m.circle=p.circle
        WHERE p.circle=? ORDER BY p.shared_minute,p.actor,p.asset""", (circle,)).fetchall()
    for actor, ident, shared in rows:
        value = _asset(c, actor, ident)
        if value is None: continue
        kind, model, source, minute, available, reason = value
        seen = devices if kind == "DEVICE" else modules
        counted = available and model not in seen
        if available: seen.add(model)
        contributions.append({
            "actor": actor, "owner": _name(c, actor), "asset": ident, "kind": kind, "model": model,
            "name": DEVICES[model][0] if kind == "DEVICE" else MODULES[model]["name"],
            "source": source, "acquired_minute": minute if actor not in PARTNERS else None,
            "shared_minute": shared, "available": available, "counted": counted,
            "reason": reason or ("" if counted else "Copia: ya está representada en el círculo."),
        })
    return sum(DEVICES[d][1] for d in devices), modules, contributions


def _valid(c, circle, modules):
    from .workshop import MODULES
    capacity, owned, _ = pool(c, circle)
    return (bool(modules) and "routing" in modules
            and all(m in owned and m in MODULES for m in modules)
            and sum(MODULES[m]["cost"] for m in set(modules)) <= capacity)


def shared_modules(c, actor):
    if not enabled(c) or not _human(c, actor) or not _independent(c, actor): return []
    group = _member(c, actor)
    if not group: return []
    modules = json.loads(group[5])
    return modules if _valid(c, group[0], modules) else []


def _event(c, circle, now, text):
    c.execute("INSERT INTO circle_events(circle,minute,text) VALUES(?,?,?)", (circle, now, text))


def revalidate(c, actor, now):
    """In the same transaction as a disconnect, withdrawal or contract change."""
    if not enabled(c): return
    group = _member(c, actor)
    if group and json.loads(group[5]) and not _valid(c, group[0], json.loads(group[5])):
        c.execute("UPDATE circle_groups SET modules='[]',compiled='' WHERE id=?", (group[0],))
        _event(c, group[0], now, "Montaje detenido: faltan recursos o permisos. El borrador se conserva; recompila cuando el círculo esté listo.")


def perform_circle_action(actor, action, data, request_id):
    from .code_lab import program_modules, LessonError
    from .workshop import MODULES
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id): raise ValueError("INVALID_REQUEST_ID")
    schemas = {"CONTACT":{"target":str}, "CREATE":{"name":str}, "INVITE":{"target":str},
               "CONTRIBUTE":{"id":str,"active":bool}, "COMPILE":{"source":str},
               "REMOVE":{"target":str}, "LEAVE":{}}
    if action not in schemas or not isinstance(data, dict) or set(data) != set(schemas[action]):
        raise ValueError("INVALID_CIRCLE_DATA")
    if any(type(data[k]) is not t for k,t in schemas[action].items()) or len(json.dumps(data)) > 12000:
        raise ValueError("INVALID_CIRCLE_DATA")
    command = json.dumps([action,data], sort_keys=True)
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        if not enabled(c): raise ValueError("CIRCLES_DISABLED")
        person = _human(c, actor)
        if not person: raise ValueError("WIRED_CONNECTION_REQUIRED")
        previous = c.execute("SELECT command,result FROM circle_requests WHERE actor=? AND id=?", (actor,request_id)).fetchone()
        if previous:
            if previous[0] != command: raise ValueError("REQUEST_ID_REUSED")
            return json.loads(previous[1])
        now = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        group = _member(c, actor)
        result = {"text":""}
        if action == "CONTACT":
            peer = data["target"]
            if peer not in PARTNERS: raise ValueError("INVALID_PARTNER")
            partner = PARTNERS[peer]
            if person[0] != partner["location"]: raise ValueError("PARTNER_NOT_PRESENT")
            c.execute("INSERT OR IGNORE INTO circle_contacts VALUES(?,?,?)", (actor,peer,now))
            result["text"] = partner["name"] + ": «" + partner["motive"].replace("Quiere","Quiero",1) + "»\n" + partner["condition"]
            result["text"] += "\nAceptará tu invitación desde el PC." if _ready(c,actor,peer) else "\nVuelve al PC cuando cumplas la condición."
        else:
            if person[0] != "APARTMENT": raise ValueError("CIRCLE_PC_REQUIRED")
            if action == "CREATE":
                name = " ".join(data["name"].split())
                if not 1 <= len(name) <= 32 or not all(ch.isprintable() for ch in data["name"]):
                    raise ValueError("INVALID_CIRCLE_NAME")
                if group: raise ValueError("ALREADY_IN_CIRCLE")
                if not _independent(c,actor): raise ValueError("INDEPENDENT_REQUIRED")
                ident = c.execute("INSERT INTO circle_groups(name,leader,created_minute) VALUES(?,?,?)", (name,actor,now)).lastrowid
                c.execute("INSERT INTO circle_members VALUES(?,?,?)", (actor,ident,now))
                _event(c,ident,now,_name(c,actor)+" fundó el círculo. Aún no hay aportaciones ni programa activo.")
                result["text"] = "Círculo creado. Aporta recursos propios y compila un montaje compartido."
            else:
                if not group: raise ValueError("CIRCLE_REQUIRED")
                ident = group[0]
                if action in {"INVITE","REMOVE","COMPILE","LEAVE"} and group[2] != actor:
                    raise ValueError("CIRCLE_LEADER_REQUIRED")
                if action == "INVITE":
                    peer = data["target"]
                    if peer not in PARTNERS: raise ValueError("INVALID_PARTNER")
                    if not c.execute("SELECT 1 FROM circle_contacts WHERE actor=? AND peer=?", (actor,peer)).fetchone():
                        raise ValueError("MEET_PARTNER_FIRST")
                    if not _ready(c,actor,peer): raise ValueError("PARTNER_CONDITION_REQUIRED")
                    if _member(c,peer): raise ValueError("PARTNER_ALREADY_COMMITTED")
                    c.execute("INSERT INTO circle_members VALUES(?,?,?)", (peer,ident,now))
                    for model,kind in PARTNERS[peer]["assets"]:
                        c.execute("INSERT INTO circle_contributions VALUES(?,?,?,?)", (ident,peer,kind+":"+model,now))
                    result["text"] = PARTNERS[peer]["name"]+" acepta y conecta sus recursos. Siguen siendo suyos."
                    _event(c,ident,now,result["text"])
                elif action == "CONTRIBUTE":
                    asset = _asset(c,actor,data["id"])
                    if not asset: raise ValueError("ASSET_NOT_OWNED")
                    if data["active"]:
                        if not asset[4]: raise ValueError("ASSET_NOT_AVAILABLE")
                        c.execute("INSERT OR IGNORE INTO circle_contributions VALUES(?,?,?,?)", (ident,actor,data["id"],now))
                    else:
                        c.execute("DELETE FROM circle_contributions WHERE circle=? AND actor=? AND asset=?", (ident,actor,data["id"]))
                    result["text"] = "Aportación conectada." if data["active"] else "Aportación retirada; conservas el recurso."
                    _event(c,ident,now,_name(c,actor)+": "+result["text"])
                    revalidate(c,actor,now)
                elif action == "COMPILE":
                    source = data["source"]
                    if len(source) > 4000: raise ValueError("INVALID_SOURCE")
                    if not _independent(c,actor): raise ValueError("INDEPENDENT_REQUIRED")
                    c.execute("UPDATE circle_groups SET draft=? WHERE id=?", (source,ident))
                    try:
                        modules = program_modules(source)
                        if not _valid(c,ident,modules):
                            raise LessonError("Faltan fragmentos aportados o capacidad de modelos diferentes.")
                        c.execute("UPDATE circle_groups SET compiled=?,modules=? WHERE id=?",
                                  (source,json.dumps(modules),ident))
                        result = {"text":"Montaje del círculo activo. Sus funciones están disponibles para sus miembros independientes.", "passed":True}
                        _event(c,ident,now,"Montaje compartido compilado: "+", ".join(MODULES[m]["name"] for m in modules)+".")
                    except LessonError as error:
                        result = {"text":str(error)+" El último montaje válido y tu programa personal se conservan.", "passed":False}
                elif action == "REMOVE":
                    peer = data["target"]
                    if peer not in PARTNERS or not c.execute("SELECT 1 FROM circle_members WHERE actor=? AND circle=?", (peer,ident)).fetchone():
                        raise ValueError("INVALID_PARTNER")
                    c.execute("DELETE FROM circle_contributions WHERE circle=? AND actor=?", (ident,peer))
                    c.execute("DELETE FROM circle_members WHERE actor=? AND circle=?", (peer,ident))
                    result["text"] = PARTNERS[peer]["name"]+" sale con sus recursos. Conservas los tuyos."
                    _event(c,ident,now,result["text"])
                    revalidate(c,actor,now)
                else:
                    c.execute("DELETE FROM circle_contributions WHERE circle=?", (ident,))
                    c.execute("DELETE FROM circle_members WHERE circle=?", (ident,))
                    c.execute("UPDATE circle_groups SET closed=1,modules='[]',compiled='' WHERE id=?", (ident,))
                    result["text"] = "Círculo disuelto. Cada miembro conserva sus recursos; tu montaje personal sigue disponible."
                    _event(c,ident,now,result["text"])
        c.execute("INSERT INTO circle_requests VALUES(?,?,?,?)", (actor,request_id,command,json.dumps(result,ensure_ascii=False)))
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'CIRCLE',?,?)",
                  (now,actor,action,"Acción del círculo registrada"))
        return result


def circle_snapshot(actor="PLAYER_1"):
    from .workshop import MODULES
    with connection() as c:
        if not enabled(c) or not _human(c, actor): return {"active":False}
        group = _member(c,actor)
        contacts = []
        for peer,p in PARTNERS.items():
            met = c.execute("SELECT minute FROM circle_contacts WHERE actor=? AND peer=?", (actor,peer)).fetchone()
            contacts.append({"id":peer,"name":p["name"],"location":p["location"],"condition":p["condition"],
                             "motive":p["motive"],"met":met is not None,"met_minute":met[0] if met else None,
                             "ready":bool(met and _ready(c,actor,peer)),
                             "available":_member(c,peer) is None,"kind":"NPC"})
        result = {"active":True,"session_mode":"LOCAL_NPC","contacts":contacts,
                  "independent":_independent(c,actor),"group":None}
        if not group: return result
        capacity,available,contributions = pool(c,group[0])
        modules = shared_modules(c,actor)
        eligible = []
        for (ident,) in c.execute("SELECT id FROM workshop_assets WHERE actor=? AND ownership='OWNED' ORDER BY id",(actor,)):
            value = _asset(c,actor,ident)
            if value:
                eligible.append({"id":ident,"kind":value[0],"model":value[1],"available":value[4],"reason":value[5],
                                 "shared":any(p["actor"]==actor and p["asset"]==ident for p in contributions)})
        result["group"] = {
            "id":group[0],"name":group[1],"leader":group[2],"draft":group[3],"compiled":group[4],
            "modules":modules,"capacity":capacity,"cost":sum(MODULES[m]["cost"] for m in modules),
            "library":[{"id":m,**MODULES[m]} for m in MODULES if m in available],
            "contributions":contributions,"eligible":eligible,
            "members":[{"id":a,"name":_name(c,a),"kind":"NPC" if a in PARTNERS else "HUMAN","joined_minute":minute}
                       for a,minute in c.execute("SELECT actor,joined_minute FROM circle_members WHERE circle=? ORDER BY joined_minute,actor",(group[0],))],
            "events":[{"minute":minute,"text":text} for minute,text in c.execute(
                "SELECT minute,text FROM circle_events WHERE circle=? ORDER BY id DESC LIMIT 30",(group[0],))],
        }
        return result
