"""Shared, server-owned relay control; private discoveries and finite reprisals.

This is a local playable slice, not multiplayer authentication. Trusted server
code may enroll multiple HUMAN actors; HTTP always binds the current player.
"""
import json
import os
import re
from contextlib import closing, contextmanager

from .database import get_connection
from . import corporate_factions as factions

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
        factions.initialize(c,RELAYS)
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
        faction=factions.operation_faction(c,op)
        strength=20 if faction==factions.NOEMA else 30
        row=c.execute("SELECT amount,defense FROM network_influence WHERE relay=? AND actor_id=?",(relay,actor)).fetchone()
        amount,defense=row or (0,0)
        loss=min(amount,max(0,strength-defense*15-corporate_cover(c,actor)))
        c.execute("UPDATE network_influence SET amount=amount-?,defense=0 WHERE relay=? AND actor_id=?",(loss,relay,actor))
        factions.add_control(c,relay,faction,loss)
        c.execute("UPDATE network_operations SET status='RESOLVED' WHERE id=?",(op,))
        c.execute("UPDATE network_players SET trace=max(0,trace-20) WHERE actor_id=?",(actor,))
        report(c,actor,now,"RELAY_TELEMETRY",f"{RELAYS[relay][0]}: intervención ejecutada. {faction} recuperó {loss} puntos de tu control. Las defensas utilizadas se agotaron.")


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


def _option(label, action, relay, rival="", faction="KAGAMI"):
    result={"text":label,"action":action,"relay":relay,"rival":rival}
    if faction!="KAGAMI": result["faction"]=faction
    return result


def _menu(c, actor, relay, text):
    from .workshop import has_module
    if c.execute("SELECT location FROM agents WHERE id=?",(actor,)).fetchone()!=(RELAYS[relay][1],):
        return _page(text)
    amount,defense=_own(c,relay,actor)
    choices=[_option("Examinar contratos y tráfico del enlace.","INSPECT",relay)]
    if c.execute("SELECT 1 FROM network_discoveries WHERE actor_id=? AND relay=?",(actor,relay)).fetchone():
        for faction in [factions.KAGAMI,factions.NOEMA] if factions.active(c) else [factions.KAGAMI]:
            if factions.discovery(c,actor,relay,faction) and factions.balance(c,relay,faction)>0:
                choices.append(_option(f"Disputar 20 puntos a {faction} · deja rastro.","CLAIM",relay,faction=faction))
        if amount>0:
            if defense<2:
                choices.append(_option("Preparar una defensa del enlace.","FORTIFY",relay))
                if has_module(c,actor,"shield"):
                    choices.append(_option("Ejecutar Protección · completar ambas defensas.","PROGRAM_SHIELD",relay))
            choices.append(_option("Ocultar mi enlace · ceder hasta 5 puntos.","GO_DARK",relay))
        if c.execute("SELECT 1 FROM network_influence WHERE relay=? AND actor_id!=? AND amount>0",(relay,actor)).fetchone():
            choices.append(_option("Ver a los rivales de este enlace.","RIVALS",relay))
    return _page(text,choices)


def _schedule(c, actor, relay, now, faction="KAGAMI"):
    trace=c.execute("SELECT trace FROM network_players WHERE actor_id=?",(actor,)).fetchone()[0]
    until=factions.suppressed_until(c,relay,faction)
    if trace<30 or until>now or factions.pending_operations(c,relay,faction,actor):
        return
    delay=80 if faction==factions.NOEMA else 100
    op=c.execute("INSERT INTO network_operations(relay,target,created_minute,due_minute,status) VALUES(?,?,?,?,'PENDING')",(relay,actor,now,now+delay)).lastrowid
    if faction==factions.NOEMA:
        c.execute("INSERT INTO network_operation_factions VALUES(?,'NOEMA')",(op,))
    technique="reescritura de permisos (hasta 20 puntos)" if faction==factions.NOEMA else "intervención técnica (hasta 30 puntos)"
    report(c,actor,now,"RELAY_TELEMETRY",f"{RELAYS[relay][0]}: {factions.label(c,actor,relay,faction)} prepara una {technique}. Tienes {delay} minutos del mundo para defenderte, ocultar tu enlace o examinar el tráfico y contrastar la credencial de su personal.")


def perform_network_action(actor, action, relay, rival, request_id, faction="KAGAMI"):
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}",request_id):
        raise ValueError("INVALID_REQUEST_ID")
    # Keep the existing request fingerprints valid on upgraded saves.
    command=json.dumps([action,relay,rival] if faction=="KAGAMI" else [action,relay,rival,faction])
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
        factions.validate(c,faction)
        if faction!="KAGAMI" and action not in {"CLAIM","TALK","EXPOSE"}:
            raise ValueError("INVALID_NETWORK_ACTION")
        location=c.execute("SELECT location FROM agents WHERE id=? AND controller_type='HUMAN'",(actor,)).fetchone()
        if location!=(RELAYS[relay][1],) and not (action=="GO_DARK" and location==("APARTMENT",)):
            raise ValueError("RELAY_NOT_PRESENT")
        now=c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        _advance(c,now)
        discovered=factions.discovery(c,actor,relay,faction)
        known=(discovered[1],discovered[2]) if discovered else None
        amount,defense=_own(c,relay,actor)
        if action in {"CLAIM","FORTIFY","GO_DARK","CONTEST","PROGRAM_SHIELD"}:
            if known is None: raise ValueError("INSPECT_RELAY_FIRST")
            last=c.execute("SELECT last_action FROM network_players WHERE actor_id=?",(actor,)).fetchone()[0]
            if now-last<10: raise ValueError("NETWORK_COOLDOWN")
        if action=="OPEN":
            operators=" · ".join(f"{row['name']}: {row['control']}%" for row in factions.controllers(c,actor,relay))
            result=_menu(c,actor,relay,f"{RELAYS[relay][0]}\n{operators}\nTu control: {amount}% · Defensas: {defense}/2\n\nExamina los contratos y el tráfico antes de intervenir. Cada operador mantiene órdenes y credenciales diferentes.")
        elif action=="INSPECT":
            op=factions.inspect(c,actor,relay,factions.KAGAMI,now)
            text="CONTRATO DE CESIÓN · El protocolo y sus primeras comunidades son anteriores a KAGAMI. El consorcio adquirió los puntos de acceso y sustituyó las claves de administración; no creó la Wired."
            if op: text+="\n\nTRÁFICO ACTUAL · La orden de intervención comparte la credencial del personal de mantenimiento presente. Puedes contrastarla hablando con esa persona."
            if factions.active(c):
                noema_op=factions.inspect(c,actor,relay,factions.NOEMA,now)
                text+="\n\nANEXO DE REGISTROS · NOEMA adquirió permisos sobre identidades y archivos; tampoco creó la Wired. Controla una cuota distinta a la de KAGAMI."
                if noema_op:
                    text+="\n\nORDEN DE REESCRITURA · Su firma coincide con la credencial del personal de registros presente. Contrástala antes de que venza la orden."
            report(c,actor,now,relay,text)
            result=_menu(c,actor,relay,text)
        elif action in {"TALK","EXPOSE"}:
            identity=RELAYS[relay]
            if faction==factions.NOEMA:
                person=factions.PERSONNEL[relay]
                identity=(identity[0],identity[1],person[0],person[1],person[2])
            if action=="TALK":
                choices=[]
                text=(f"«Soy {identity[3]}. Solo comparo fichas. A veces un nombre figura donde no debería.»" if faction==factions.NOEMA else f"«Soy {identity[3]}. Solo reviso las líneas. Si se cae una conexión, será un problema técnico.»")
                if known and known[1]:
                    text=("«NOEMA decide qué registro tiene validez. Puedes abrir una conexión; nosotros podemos cambiar quién figura como su titular.»" if faction==factions.NOEMA else "«Sabes para quién trabajo. KAGAMI permite usuarios, no nuevos administradores. Seguiremos recuperando lo que intentéis controlar.»")
                if factions.current_proof(c,actor,relay,faction):
                    choices=[_option("Contrastar su credencial con la orden interceptada.","EXPOSE",relay,faction=faction)]
                result=_page(text,choices,identity[3])
            else:
                if not factions.current_proof(c,actor,relay,faction):
                    raise ValueError("CURRENT_PROOF_REQUIRED")
                factions.reveal(c,actor,relay,faction)
                for pending_op,_,_ in factions.pending_operations(c,relay,faction):
                    c.execute("UPDATE network_operations SET status='INTERRUPTED' WHERE id=?",(pending_op,))
                factions.suppress(c,relay,faction,now+120)
                other,shift=factions.rival_opportunity(c,relay,faction)
                for (recipient,) in c.execute("SELECT actor_id FROM network_players").fetchall():
                    public_name=factions.label(c,recipient,relay,faction)
                    report(c,recipient,now,"RELAY_TELEMETRY",f"{identity[0]}: órdenes de {public_name} suspendidas durante 120 minutos del mundo. Las órdenes del otro operador, si las hay, siguen activas.")
                    if shift:
                        report(c,recipient,now,"RELAY_TELEMETRY",f"{identity[0]}: {factions.label(c,recipient,relay,other)} aprovechó la suspensión y tomó {shift} puntos al otro operador. Las cuotas de los usuarios no cambiaron.")
                text=f"La credencial coincide con {faction}. Has detenido sus órdenes en este enlace para todos los usuarios durante 120 minutos del mundo."
                if factions.active(c):
                    text+=" Las órdenes de la otra corporación siguen activas."
                    if shift: text+=f" {other} aprovechó la caída para tomar {shift} puntos a {faction}."
                result=_page(text,speaker=identity[3])
        elif action=="RIVALS":
            choices=[_option(f"Disputar 15 puntos a {name}.","CONTEST",relay,rid) for rid,name in c.execute("SELECT i.actor_id,a.name FROM network_influence i JOIN agents a ON a.id=i.actor_id WHERE relay=? AND i.actor_id!=? AND amount>0 ORDER BY amount DESC,i.actor_id LIMIT 8",(relay,actor))]
            result=_page("Cada cuenta conserva su control. Atacar a un rival transfiere parte de su cuota hacia ti y deja un rastro mayor ante KAGAMI.",choices)
        else:
            if action=="CLAIM":
                available=factions.balance(c,relay,faction)
                if available==0: raise ValueError("NO_CORPORATE_CONTROL")
                gain=min(20,available)
                factions.add_control(c,relay,faction,-gain)
                c.execute("INSERT INTO network_influence(relay,actor_id,amount) VALUES(?,?,?) ON CONFLICT(relay,actor_id) DO UPDATE SET amount=amount+excluded.amount",(relay,actor,gain))
                c.execute("UPDATE network_players SET trace=min(100,trace+30) WHERE actor_id=?",(actor,))
                _schedule(c,actor,relay,now,faction)
                text=f"Has tomado {gain} puntos de control a {faction}. Tu actividad ha dejado un rastro; consulta las intervenciones en el archivo de la red [J]."
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
                text=f"Ocultaste tu enlace y cediste {loss} puntos a KAGAMI. Todas las intervenciones dirigidas a tu conexión en este enlace quedan anuladas; las de otras cuentas siguen activas."
            c.execute("UPDATE network_players SET last_action=? WHERE actor_id=?",(now,actor))
            result=_menu(c,actor,relay,text)
        c.execute("INSERT INTO network_requests VALUES(?,?,?,?)",(actor,request_id,command,json.dumps(result,ensure_ascii=False)))
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'NETWORK_CONFLICT',?,?)",(now,actor,relay,action if faction=="KAGAMI" else action+":"+faction))
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
        dual=factions.active(c)
        for relay,(name,place,civil_id,civil_name,cover) in RELAYS.items():
            corp,until=c.execute("SELECT corporation,suppressed_until FROM network_relays WHERE id=?",(relay,)).fetchone()
            mine,defense=_own(c,relay,actor)
            known=c.execute("SELECT acquired_minute,proof_operation,revealed FROM network_discoveries WHERE actor_id=? AND relay=?",(actor,relay)).fetchone()
            relay_view={"id":relay,"name":name,"location":place,"corporation":corp,"mine":mine,"defense":defense,"suppressed_until":until,"inspected":known is not None}
            if dual: relay_view["controllers"]=factions.controllers(c,actor,relay)
            relays.append(relay_view)
            if place==location:
                operatives.append({"id":civil_id,"relay":relay,"name":civil_name,"role":"Agente de KAGAMI · credencial comprobada" if known and known[2] else cover,"slot":"LINES"})
                if dual:
                    noema_known=factions.discovery(c,actor,relay,factions.NOEMA)
                    ident,title,job,focus=factions.PERSONNEL[relay]
                    operatives.append({"id":ident,"relay":relay,"name":title,"role":"Agente de NOEMA · credencial comprobada" if noema_known and noema_known[2] else job,"slot":"RECORDS","focus":focus})
        rankings=[{"actor_id":aid,"name":name,"control":round(total/len(RELAYS),1)} for aid,name,total in c.execute("SELECT p.actor_id,a.name,coalesce(sum(i.amount),0) FROM network_players p JOIN agents a ON a.id=p.actor_id LEFT JOIN network_influence i ON i.actor_id=p.actor_id GROUP BY p.actor_id,a.name ORDER BY sum(i.amount) DESC,p.actor_id")]
        pending=[]
        for op,r,due in c.execute("SELECT id,relay,due_minute FROM network_operations WHERE target=? AND status='PENDING' ORDER BY due_minute,id",(actor,)):
            row={"relay":r,"due_minute":due,"remaining":max(0,due-now)}
            if dual:
                faction=factions.operation_faction(c,op)
                row.update(operator=factions.label(c,actor,r,faction),
                           kind="Reescritura de permisos" if faction==factions.NOEMA else "Intervención técnica",
                           max_loss=20 if faction==factions.NOEMA else 30)
            pending.append(row)
        reports=[{"id":i,"minute":m,"source":s,"text":t} for i,m,s,t in c.execute("SELECT id,minute,source,text FROM network_reports WHERE recipient=? ORDER BY id DESC LIMIT 25",(actor,))]
        enemy_known=c.execute("SELECT 1 FROM network_discoveries WHERE actor_id=?",(actor,)).fetchone() is not None
        total=sum(sum(operator["control"] for operator in row["controllers"]) if dual else row["corporation"] for row in relays)
        return {"active":True,"multiple_operators":dual,"corporation":"Administradores de la Wired" if dual else (CORPORATION if enemy_known else "Administrador desconocido"),"corporate_control":round(total/len(RELAYS),1),"trace":player[0],"ready_in":max(0,10-(now-player[1])),"relays":relays,"rankings":rankings,"pending":pending,"reports":reports,"visible_personnel":operatives,"session_mode":"LOCAL"}
