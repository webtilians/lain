"""Shared, server-owned relay control; private discoveries and finite reprisals.

This is a local playable slice, not multiplayer authentication. Trusted server
code may enroll multiple HUMAN actors; HTTP always binds the current player.
"""
import json
import os
import re
from contextlib import closing, contextmanager

from .database import get_connection

CORPORATION = "Consorcio KAGAMI"
RELAYS = {
    "RELAY_STATION": ("Enlace del andén", "STATION", "CIVIL_101", "Daichi Kurose", "Técnico de telefonía"),
    "RELAY_SCHOOL": ("Enlace del pabellón B", "SCHOOL_LAB", "CIVIL_102", "Reina Asano", "Consultora de equipos"),
    "RELAY_VIDEO": ("Enlace del videoclub", "VIDEO_CLUB", "CIVIL_103", "Shin Okabe", "Supervisor de mantenimiento"),
}


@contextmanager
def connection():
    with closing(get_connection()) as c:
        with c:
            yield c


def exists(c):
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='network_relays'").fetchone() is not None


def initialize_conflict():
    if os.getenv("LAIN_CORPORATION", "0") != "1":
        return
    with connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS network_relays (
            id TEXT PRIMARY KEY, corporation INTEGER NOT NULL CHECK(corporation BETWEEN 0 AND 100),
            suppressed_until INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS network_players (
            actor_id TEXT PRIMARY KEY, trace INTEGER NOT NULL DEFAULT 0 CHECK(trace BETWEEN 0 AND 100),
            last_action INTEGER NOT NULL DEFAULT -100, joined_minute INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS network_influence (
            relay TEXT NOT NULL, actor_id TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount BETWEEN 0 AND 100),
            defense INTEGER NOT NULL DEFAULT 0 CHECK(defense BETWEEN 0 AND 2), PRIMARY KEY(relay,actor_id));
        CREATE TABLE IF NOT EXISTS network_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, relay TEXT NOT NULL, target TEXT NOT NULL,
            created_minute INTEGER NOT NULL, due_minute INTEGER NOT NULL, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS network_discoveries (
            actor_id TEXT NOT NULL, relay TEXT NOT NULL, acquired_minute INTEGER NOT NULL,
            proof_operation INTEGER, revealed INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(actor_id,relay));
        CREATE TABLE IF NOT EXISTS network_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, recipient TEXT NOT NULL, minute INTEGER NOT NULL,
            source TEXT NOT NULL, text TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS network_requests (
            actor_id TEXT NOT NULL, request_id TEXT NOT NULL, command TEXT NOT NULL, response TEXT NOT NULL,
            PRIMARY KEY(actor_id,request_id));
        """)
        for relay in RELAYS:
            c.execute("INSERT OR IGNORE INTO network_relays(id,corporation) VALUES(?,100)",(relay,))
    enroll_connected_players()


def enroll_player(actor_id):
    """Trusted server entry for a verified HUMAN session. No HTTP enrollment."""
    with connection() as c:
        if not exists(c):
            return False
        actor=c.execute("SELECT controller_type FROM agents WHERE id=?",(actor_id,)).fetchone()
        if actor != ("HUMAN",):
            raise ValueError("HUMAN_PLAYER_REQUIRED")
        now=c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        return c.execute("INSERT OR IGNORE INTO network_players(actor_id,joined_minute) VALUES(?,?)",(actor_id,now)).rowcount==1


def enroll_connected_players():
    with connection() as c:
        if not exists(c):
            return
        rows=c.execute("""SELECT DISTINCT a.id FROM agents a JOIN world_messages m ON m.recipient_id=a.id
            WHERE a.controller_type='HUMAN' AND m.id='MSG_BOOTSTRAP_001' AND m.acknowledged=1""").fetchall()
    for (actor,) in rows:
        enroll_player(actor)


def report(c, actor, now, source, text):
    c.execute("INSERT INTO network_reports(recipient,minute,source,text) VALUES(?,?,?,?)",(actor,now,source,text))


def _advance(c, now):
    from .workshop import corporate_cover
    for op,relay,actor in c.execute("SELECT id,relay,target FROM network_operations WHERE status='PENDING' AND due_minute<=? ORDER BY due_minute,id",(now,)).fetchall():
        row=c.execute("SELECT amount,defense FROM network_influence WHERE relay=? AND actor_id=?",(relay,actor)).fetchone()
        amount,defense=row or (0,0)
        loss=min(amount,max(0,30-defense*15-corporate_cover(c,actor)))
        c.execute("UPDATE network_influence SET amount=amount-?,defense=0 WHERE relay=? AND actor_id=?",(loss,relay,actor))
        c.execute("UPDATE network_relays SET corporation=corporation+? WHERE id=?",(loss,relay))
        c.execute("UPDATE network_operations SET status='RESOLVED' WHERE id=?",(op,))
        c.execute("UPDATE network_players SET trace=max(0,trace-20) WHERE actor_id=?",(actor,))
        report(c,actor,now,"RELAY_TELEMETRY",f"{RELAYS[relay][0]}: intervención ejecutada. KAGAMI recuperó {loss} puntos de tu control. Las defensas utilizadas se agotaron.")


def advance_conflict(now):
    """Only the authoritative tick calls this; no offline catch-up or GET writes."""
    with connection() as c:
        if exists(c):
            c.execute("BEGIN IMMEDIATE")
            _advance(c,now)


def _own(c, relay, actor):
    return c.execute("SELECT amount,defense FROM network_influence WHERE relay=? AND actor_id=?",(relay,actor)).fetchone() or (0,0)


def _page(text, choices=(), speaker="WIRED · CONTROL DE ENLACES"):
    return {"speaker":speaker,"text":text,"choices":list(choices)}


def _option(label, action, relay, rival=""):
    return {"text":label,"action":action,"relay":relay,"rival":rival}


def _menu(c, actor, relay, text):
    from .workshop import has_module
    if c.execute("SELECT location FROM agents WHERE id=?",(actor,)).fetchone()!=(RELAYS[relay][1],):
        return _page(text)
    amount,defense=_own(c,relay,actor)
    choices=[_option("Examinar contratos y tráfico del enlace.","INSPECT",relay)]
    if c.execute("SELECT 1 FROM network_discoveries WHERE actor_id=? AND relay=?",(actor,relay)).fetchone():
        if c.execute("SELECT corporation FROM network_relays WHERE id=?",(relay,)).fetchone()[0]>0:
            choices.append(_option("Disputar 20 puntos a KAGAMI · deja rastro.","CLAIM",relay))
        if amount>0:
            if defense<2:
                choices.append(_option("Preparar una defensa del enlace.","FORTIFY",relay))
                if has_module(c,actor,"shield"):
                    choices.append(_option("Ejecutar Protección · completar ambas defensas.","PROGRAM_SHIELD",relay))
            choices.append(_option("Ocultar mi enlace · ceder hasta 5 puntos.","GO_DARK",relay))
        if c.execute("SELECT 1 FROM network_influence WHERE relay=? AND actor_id!=? AND amount>0",(relay,actor)).fetchone():
            choices.append(_option("Ver a los rivales de este enlace.","RIVALS",relay))
    return _page(text,choices)


def _schedule(c, actor, relay, now):
    trace=c.execute("SELECT trace FROM network_players WHERE actor_id=?",(actor,)).fetchone()[0]
    until=c.execute("SELECT suppressed_until FROM network_relays WHERE id=?",(relay,)).fetchone()[0]
    if trace<30 or until>now or c.execute("SELECT 1 FROM network_operations WHERE relay=? AND target=? AND status='PENDING'",(relay,actor)).fetchone():
        return
    c.execute("INSERT INTO network_operations(relay,target,created_minute,due_minute,status) VALUES(?,?,?,?,'PENDING')",(relay,actor,now,now+100))
    report(c,actor,now,"RELAY_TELEMETRY",f"{RELAYS[relay][0]}: tráfico de intervención detectado. Tienes 100 minutos del mundo para defenderte, ocultar tu enlace o examinar el tráfico y contrastar la credencial de quien lo mantiene.")


def perform_network_action(actor, action, relay, rival, request_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}",request_id):
        raise ValueError("INVALID_REQUEST_ID")
    command=json.dumps([action,relay,rival])
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        if not exists(c) or not c.execute("SELECT 1 FROM network_players WHERE actor_id=?",(actor,)).fetchone():
            raise ValueError("WIRED_CONNECTION_REQUIRED")
        previous=c.execute("SELECT command,response FROM network_requests WHERE actor_id=? AND request_id=?",(actor,request_id)).fetchone()
        if previous:
            if previous[0]!=command: raise ValueError("REQUEST_ID_REUSED")
            return json.loads(previous[1])
        if action not in {"OPEN","INSPECT","CLAIM","FORTIFY","GO_DARK","TALK","EXPOSE","RIVALS","CONTEST","PROGRAM_SHIELD"} or relay not in RELAYS:
            raise ValueError("INVALID_NETWORK_ACTION")
        location=c.execute("SELECT location FROM agents WHERE id=? AND controller_type='HUMAN'",(actor,)).fetchone()
        if location!=(RELAYS[relay][1],) and not (action=="GO_DARK" and location==("APARTMENT",)):
            raise ValueError("RELAY_NOT_PRESENT")
        now=c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        _advance(c,now)
        known=c.execute("SELECT proof_operation,revealed FROM network_discoveries WHERE actor_id=? AND relay=?",(actor,relay)).fetchone()
        amount,defense=_own(c,relay,actor)
        if action in {"CLAIM","FORTIFY","GO_DARK","CONTEST","PROGRAM_SHIELD"}:
            if known is None: raise ValueError("INSPECT_RELAY_FIRST")
            last=c.execute("SELECT last_action FROM network_players WHERE actor_id=?",(actor,)).fetchone()[0]
            if now-last<10: raise ValueError("NETWORK_COOLDOWN")
        if action=="OPEN":
            corp=c.execute("SELECT corporation FROM network_relays WHERE id=?",(relay,)).fetchone()[0]
            operator="KAGAMI" if known else "Administrador desconocido"
            result=_menu(c,actor,relay,f"{RELAYS[relay][0]}\n{operator}: {corp}% · Tu control: {amount}% · Defensas: {defense}/2\n\nEste armario controla un enlace de la Wired. Conserva contratos antiguos y tráfico de administración. Puedes examinarlos antes de intervenir.")
        elif action=="INSPECT":
            op=c.execute("SELECT id FROM network_operations WHERE relay=? AND status='PENDING' ORDER BY id LIMIT 1",(relay,)).fetchone()
            c.execute("INSERT INTO network_discoveries(actor_id,relay,acquired_minute,proof_operation) VALUES(?,?,?,?) ON CONFLICT(actor_id,relay) DO UPDATE SET proof_operation=excluded.proof_operation",(actor,relay,now,op[0] if op else None))
            text="CONTRATO DE CESIÓN · El protocolo y sus primeras comunidades son anteriores a KAGAMI. El consorcio adquirió los puntos de acceso y sustituyó las claves de administración; no creó la Wired."
            if op: text+="\n\nTRÁFICO ACTUAL · La orden de intervención comparte la credencial del personal de mantenimiento presente. Puedes contrastarla hablando con esa persona."
            report(c,actor,now,relay,text)
            result=_menu(c,actor,relay,text)
        elif action in {"TALK","EXPOSE"}:
            identity=RELAYS[relay]
            if action=="TALK":
                choices=[]
                text=f"«Soy {identity[3]}. Solo reviso las líneas. Si se cae una conexión, será un problema técnico.»"
                if known and known[1]: text="«Sabes para quién trabajo. KAGAMI permite usuarios, no nuevos administradores. Seguiremos recuperando lo que intentéis controlar.»"
                if known and known[0] is not None and c.execute("SELECT 1 FROM network_operations WHERE id=? AND status='PENDING'",(known[0],)).fetchone():
                    choices=[_option("Contrastar su credencial con la orden interceptada.","EXPOSE",relay)]
                result=_page(text,choices,identity[3])
            else:
                if not known or known[0] is None or not c.execute("SELECT 1 FROM network_operations WHERE id=? AND relay=? AND status='PENDING'",(known[0],relay)).fetchone():
                    raise ValueError("CURRENT_PROOF_REQUIRED")
                c.execute("UPDATE network_discoveries SET revealed=1 WHERE actor_id=? AND relay=?",(actor,relay))
                c.execute("UPDATE network_operations SET status='INTERRUPTED' WHERE relay=? AND status='PENDING'",(relay,))
                c.execute("UPDATE network_relays SET suppressed_until=? WHERE id=?",(now+120,relay))
                for (recipient,) in c.execute("SELECT actor_id FROM network_players").fetchall():
                    report(c,recipient,now,"RELAY_TELEMETRY",f"{identity[0]}: intervención suspendida. El enlace queda sin nuevas operaciones corporativas durante 120 minutos del mundo.")
                result=_page("La credencial coincide. Guarda la herramienta y corta su transmisión. «El consorcio volverá a intentarlo.» Has interrumpido las intervenciones de este enlace para todos sus usuarios.",speaker=identity[3])
        elif action=="RIVALS":
            choices=[_option(f"Disputar 15 puntos a {name}.","CONTEST",relay,rid) for rid,name in c.execute("SELECT i.actor_id,a.name FROM network_influence i JOIN agents a ON a.id=i.actor_id WHERE relay=? AND i.actor_id!=? AND amount>0 ORDER BY amount DESC,i.actor_id LIMIT 8",(relay,actor))]
            result=_page("Cada cuenta conserva su control. Atacar a un rival transfiere parte de su cuota hacia ti y deja un rastro mayor ante KAGAMI.",choices)
        else:
            if action=="CLAIM":
                available=c.execute("SELECT corporation FROM network_relays WHERE id=?",(relay,)).fetchone()[0]
                if available==0: raise ValueError("NO_CORPORATE_CONTROL")
                gain=min(20,available)
                c.execute("UPDATE network_relays SET corporation=corporation-? WHERE id=?",(gain,relay))
                c.execute("INSERT INTO network_influence(relay,actor_id,amount) VALUES(?,?,?) ON CONFLICT(relay,actor_id) DO UPDATE SET amount=amount+excluded.amount",(relay,actor,gain))
                c.execute("UPDATE network_players SET trace=min(100,trace+30) WHERE actor_id=?",(actor,))
                _schedule(c,actor,relay,now)
                text=f"Has tomado {gain} puntos de control a KAGAMI. Tu actividad ha dejado un rastro; consulta las intervenciones en el archivo de la red [J]."
            elif action=="CONTEST":
                if rival==actor: raise ValueError("INVALID_RIVAL")
                available=_own(c,relay,rival)[0]
                if available==0: raise ValueError("INVALID_RIVAL")
                gain=min(15,available)
                c.execute("UPDATE network_influence SET amount=amount-? WHERE relay=? AND actor_id=?",(gain,relay,rival))
                c.execute("INSERT INTO network_influence(relay,actor_id,amount) VALUES(?,?,?) ON CONFLICT(relay,actor_id) DO UPDATE SET amount=amount+excluded.amount",(relay,actor,gain))
                c.execute("UPDATE network_players SET trace=min(100,trace+40) WHERE actor_id=?",(actor,))
                report(c,rival,now,"RELAY_TELEMETRY",f"Otra cuenta disputó {gain} puntos de tu control en {RELAYS[relay][0]}.")
                _schedule(c,actor,relay,now)
                text=f"Has transferido {gain} puntos del rival hacia tu cuenta. KAGAMI puede aprovechar vuestra rivalidad."
            elif action in {"FORTIFY","PROGRAM_SHIELD"}:
                if amount==0 or defense>=2: raise ValueError("DEFENSE_NOT_AVAILABLE")
                if action=="PROGRAM_SHIELD":
                    from .workshop import has_module
                    if not has_module(c,actor,"shield"): raise ValueError("SHIELD_MODULE_REQUIRED")
                c.execute("UPDATE network_influence SET defense=? WHERE relay=? AND actor_id=?",(2 if action=="PROGRAM_SHIELD" else defense+1,relay,actor))
                text="Defensa preparada. Cada defensa absorbe 15 puntos de la próxima intervención; se consume cuando llega. Dos defensas detienen una intervención completa."
            else:
                if amount==0: raise ValueError("NO_PLAYER_CONTROL")
                loss=min(5,amount)
                c.execute("UPDATE network_influence SET amount=amount-? WHERE relay=? AND actor_id=?",(loss,relay,actor))
                c.execute("UPDATE network_relays SET corporation=corporation+? WHERE id=?",(loss,relay))
                c.execute("UPDATE network_players SET trace=max(0,trace-30) WHERE actor_id=?",(actor,))
                c.execute("UPDATE network_operations SET status='EVADED' WHERE target=? AND relay=? AND status='PENDING'",(actor,relay))
                text=f"Ocultaste tu enlace y cediste {loss} puntos. La intervención dirigida a tu conexión queda anulada; las de otras cuentas siguen activas."
            c.execute("UPDATE network_players SET last_action=? WHERE actor_id=?",(now,actor))
            result=_menu(c,actor,relay,text)
        c.execute("INSERT INTO network_requests VALUES(?,?,?,?)",(actor,request_id,command,json.dumps(result,ensure_ascii=False)))
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'NETWORK_CONFLICT',?,?)",(now,actor,relay,action))
        return result


def network_snapshot(actor="PLAYER_1"):
    with connection() as c:
        if not exists(c): return {"active":False}
        player=c.execute("SELECT trace,last_action FROM network_players WHERE actor_id=?",(actor,)).fetchone()
        if player is None: return {"active":False}
        now=c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        location=c.execute("SELECT location FROM agents WHERE id=?",(actor,)).fetchone()[0]
        relays=[]
        operatives=[]
        for relay,(name,place,civil_id,civil_name,cover) in RELAYS.items():
            corp,until=c.execute("SELECT corporation,suppressed_until FROM network_relays WHERE id=?",(relay,)).fetchone()
            mine,defense=_own(c,relay,actor)
            known=c.execute("SELECT acquired_minute,proof_operation,revealed FROM network_discoveries WHERE actor_id=? AND relay=?",(actor,relay)).fetchone()
            relays.append({"id":relay,"name":name,"location":place,"corporation":corp,"mine":mine,"defense":defense,"suppressed_until":until,"inspected":known is not None})
            if place==location:
                operatives.append({"id":civil_id,"relay":relay,"name":civil_name,"role":"Agente de KAGAMI · credencial comprobada" if known and known[2] else cover})
        rankings=[{"actor_id":aid,"name":name,"control":round(total/len(RELAYS),1)} for aid,name,total in c.execute("SELECT p.actor_id,a.name,coalesce(sum(i.amount),0) FROM network_players p JOIN agents a ON a.id=p.actor_id LEFT JOIN network_influence i ON i.actor_id=p.actor_id GROUP BY p.actor_id,a.name ORDER BY sum(i.amount) DESC,p.actor_id")]
        pending=[{"relay":r,"due_minute":due,"remaining":max(0,due-now)} for r,due in c.execute("SELECT relay,due_minute FROM network_operations WHERE target=? AND status='PENDING' ORDER BY due_minute,id",(actor,))]
        reports=[{"id":i,"minute":m,"source":s,"text":t} for i,m,s,t in c.execute("SELECT id,minute,source,text FROM network_reports WHERE recipient=? ORDER BY id DESC LIMIT 25",(actor,))]
        enemy_known=c.execute("SELECT 1 FROM network_discoveries WHERE actor_id=?",(actor,)).fetchone() is not None
        return {"active":True,"corporation":CORPORATION if enemy_known else "Administrador desconocido","corporate_control":round(sum(r["corporation"] for r in relays)/len(RELAYS),1),"trace":player[0],"ready_in":max(0,10-(now-player[1])),"relays":relays,"rankings":rankings,"pending":pending,"reports":reports,"visible_personnel":operatives,"session_mode":"LOCAL"}
