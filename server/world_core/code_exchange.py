"""Consensual NPC code copies, with actor-scoped receipts and no memory access."""
import json
import os
import re

from .network_conflict import connection, report
from . import workshop as ws
from .circles import PARTNERS

# Versioned offers describe deliberate consent, not arbitrary access to NPC assets.
OFFERS = {
    "ryoko_scan_v1": {"peer": "RYOKO", "wanted": "buffer", "given": "scan",
        "motive": "Necesito amortiguar las interrupciones de mi enlace. A cambio te paso mi módulo de Exploración."},
    "kissa_shield_v1": {"peer": "KISSA_TECH", "wanted": "scan", "given": "shield",
        "motive": "Quiero detectar intervenciones sobre las máquinas del café. Te cambio Exploración por una copia de Protección."},
}


def enabled(c):
    return (os.getenv("LAIN_CODE_EXCHANGE", "0") == "1" and ws.enabled(c)
            and c.execute("SELECT 1 FROM sqlite_master WHERE name='code_exchange_contacts'").fetchone() is not None)


def initialize_exchange():
    if os.getenv("LAIN_CODE_EXCHANGE", "0") != "1": return
    with connection() as c:
        if not ws.enabled(c): return
        c.executescript("""
        CREATE TABLE IF NOT EXISTS code_exchange_contacts (
          actor TEXT NOT NULL, peer TEXT NOT NULL, minute INTEGER NOT NULL, PRIMARY KEY(actor,peer));
        CREATE TABLE IF NOT EXISTS code_exchange_deals (
          actor TEXT NOT NULL, offer TEXT NOT NULL, minute INTEGER NOT NULL, receipt TEXT NOT NULL,
          PRIMARY KEY(actor,offer));
        CREATE TABLE IF NOT EXISTS code_exchange_requests (
          actor TEXT NOT NULL, id TEXT NOT NULL, command TEXT NOT NULL, result TEXT NOT NULL,
          PRIMARY KEY(actor,id));
        """)


def _human(c, actor):
    return c.execute("""SELECT a.location,w.contract FROM agents a JOIN workshop_players w ON a.id=w.actor
        WHERE a.id=? AND a.controller_type='HUMAN'""", (actor,)).fetchone()


def _copies(c, actor, model):
    return [dict(id=r[0], source=r[1], minute=r[2]) for r in c.execute("""SELECT id,source,minute
        FROM workshop_assets WHERE actor=? AND kind='CODE' AND model=? AND ownership='OWNED'
        ORDER BY minute,id""", (actor,model))]


def perform_exchange_action(actor, action, data, request_id):
    if type(request_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}",request_id):
        raise ValueError("INVALID_REQUEST_ID")
    fields = {"CONTACT": {"peer"}, "ACCEPT": {"offer","asset"}}
    if (type(action) is not str or action not in fields or type(data) is not dict
            or set(data) != fields[action] or any(type(v) is not str or not 1 <= len(v) <= 100 for v in data.values())):
        raise ValueError("INVALID_EXCHANGE_DATA")
    command = json.dumps([action,data],sort_keys=True)
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        if not enabled(c): raise ValueError("EXCHANGE_DISABLED")
        human = _human(c,actor)
        if not human: raise ValueError("WIRED_CONNECTION_REQUIRED")
        previous = c.execute("SELECT command,result FROM code_exchange_requests WHERE actor=? AND id=?",(actor,request_id)).fetchone()
        if previous:
            if previous[0] != command: raise ValueError("REQUEST_ID_REUSED")
            return json.loads(previous[1])
        now = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        if action == "CONTACT":
            peer = data["peer"]
            offer = next((o for o in OFFERS.values() if o["peer"] == peer),None)
            if offer is None: raise ValueError("INVALID_EXCHANGE_PEER")
            partner = PARTNERS[peer]
            if human[0] != partner["location"]: raise ValueError("PARTNER_NOT_PRESENT")
            c.execute("INSERT OR IGNORE INTO code_exchange_contacts VALUES(?,?,?)",(actor,peer,now))
            result = {"text":partner["name"] + ": «" + offer["motive"] + "»\nLa propuesta está en PC → Intercambios. Compartimos copias; ambos conservamos nuestros originales. Solo mientras sigas independiente."}
        else:
            ident = data["offer"]
            offer = OFFERS.get(ident)
            if offer is None: raise ValueError("INVALID_EXCHANGE_OFFER")
            if human[0] != "APARTMENT": raise ValueError("EXCHANGE_PC_REQUIRED")
            completed = c.execute("SELECT receipt FROM code_exchange_deals WHERE actor=? AND offer=?",(actor,ident)).fetchone()
            if completed:
                result = json.loads(completed[0])
            else:
                if human[1] != "INDEPENDENT": raise ValueError("INDEPENDENT_REQUIRED")
                peer = offer["peer"]
                if not c.execute("SELECT 1 FROM code_exchange_contacts WHERE actor=? AND peer=?",(actor,peer)).fetchone():
                    raise ValueError("MEET_EXCHANGE_PEER_FIRST")
                supplied = next((a for a in _copies(c,actor,offer["wanted"]) if a["id"] == data["asset"]),None)
                if supplied is None: raise ValueError("EXCHANGE_OWNED_CODE_REQUIRED")
                if (offer["given"],"CODE") not in PARTNERS[peer]["assets"]:
                    raise ValueError("EXCHANGE_OFFER_UNAVAILABLE")
                name = PARTNERS[peer]["name"]
                received = "exchange_" + ident
                source = f"Copia compartida por {name} · {ws.MODULES[offer['given']]['name']}"
                ws._grant(c,actor,received,"CODE",offer["given"],source,now)
                # Both directions keep an acquisition receipt. The NPC receives only
                # the explicitly selected fragment and its provenance, never player memory.
                result = {"text":f"{name} recibió tu copia de {ws.MODULES[offer['wanted']]['name']}. Recibiste {ws.MODULES[offer['given']]['name']}. Ambos conserváis los originales. Insértalo y compílalo en Código; no se activa solo.",
                    "offer":ident,"peer":peer,"peer_name":name,"minute":now,
                    "sent":{"owner":actor,"asset":supplied["id"],"model":offer["wanted"],"name":ws.MODULES[offer["wanted"]]["name"],"source":supplied["source"],"acquired_minute":supplied["minute"]},
                    "received":{"owner":actor,"asset":received,"model":offer["given"],"name":ws.MODULES[offer["given"]]["name"],"source":source,"acquired_minute":now,"from":peer,"original_acquired_minute":None}}
                c.execute("INSERT INTO code_exchange_deals VALUES(?,?,?,?)",(actor,ident,now,json.dumps(result,ensure_ascii=False)))
                report(c,actor,now,"CODE_EXCHANGE",result["text"])
        c.execute("INSERT INTO code_exchange_requests VALUES(?,?,?,?)",(actor,request_id,command,json.dumps(result,ensure_ascii=False)))
        return result


def exchange_snapshot(actor="PLAYER_1"):
    with connection() as c:
        if not enabled(c) or not (human := _human(c,actor)): return {"active":False}
        offers, history = [], []
        for ident,offer in OFFERS.items():
            peer = offer["peer"]
            partner = PARTNERS[peer]
            contact = c.execute("SELECT minute FROM code_exchange_contacts WHERE actor=? AND peer=?",(actor,peer)).fetchone()
            deal = c.execute("SELECT receipt FROM code_exchange_deals WHERE actor=? AND offer=?",(actor,ident)).fetchone()
            copies = _copies(c,actor,offer["wanted"]) if contact else []
            reason = ("Intercambio completado." if deal else "Habla de intercambiar código con esta persona primero." if not contact
                else "Termina tu contrato corporativo para intercambiar." if human[1] != "INDEPENDENT"
                else "Necesitas una copia propia del fragmento solicitado; préstamos y aportaciones ajenas no sirven." if not copies
                else "Confirma el intercambio desde el PC de casa." if human[0] != "APARTMENT" else "")
            offers.append(dict(id=ident,peer=peer,name=partner["name"],location=partner["location"],kind="NPC",
                met=contact is not None,met_minute=contact[0] if contact else None,completed=bool(deal),ready=not reason,reason=reason,
                wanted=offer["wanted"] if contact else "",wanted_name=ws.MODULES[offer["wanted"]]["name"] if contact else "",
                given=offer["given"] if contact else "",given_name=ws.MODULES[offer["given"]]["name"] if contact else "",
                motive=offer["motive"] if contact else "",copies=copies))
            if deal: history.append(json.loads(deal[0]))
        history.sort(key=lambda r:(r["minute"],r["offer"]),reverse=True)
        return dict(active=True,session_mode="LOCAL_NPC",offers=offers,history=history)
