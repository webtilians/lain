"""The owner's server panel: who is connected, who came and went, and what happened.

Read only. It is served at /admin to loopback requests that did not come
through Caddy (vps.ps1 -Panel opens an SSH tunnel to it), so it is never
public. Chat contents are not shown, only how many messages there are.
"""
import os
import subprocess
import time
from pathlib import Path

from .database import DB_PATH, get_connection
from . import online

STARTED = time.time()
LAYERS = (("layer_one", "01"), ("layer_two", "02"), ("layer_three", "03"), ("layer_four", "04"),
          ("layer_five", "05"), ("layer_six", "06"), ("layer_seven", "07"))
ACTIONS = {
    "LAYER_ONE_DECISION": "Capa 01 · decidió", "LAYER_TWO_DECISION": "Capa 02 · decidió",
    "LAYER_THREE_DECISION": "Capa 03 · decidió", "LAYER_FOUR_DECISION": "Capa 04 · decidió",
    "LAYER_FIVE_DECISION": "Capa 05 · decidió", "LAYER_SIX_DECISION": "Capa 06 · decidió",
    "LAYER_SEVEN_DECISION": "Capa 07 · final", "LAYER_ONE_STARTED": "Capa 01 · empezó",
    "LAYER_TWO_STARTED": "Capa 02 · empezó", "LAYER_THREE_STARTED": "Capa 03 · empezó",
    "LAYER_FOUR_STARTED": "Capa 04 · empezó", "LAYER_FIVE_STARTED": "Capa 05 · empezó",
    "LAYER_SIX_STARTED": "Capa 06 · empezó", "LAYER_SEVEN_STARTED": "Capa 07 · empezó",
    "JOURNAL_RESTORED": "Restauró su diario",
}
_version = None


def local_request(host: str | None, headers) -> bool:
    """Only the SSH tunnel: a loopback client with no proxy headers (Caddy adds them)."""
    proxied = any(name in headers for name in ("x-forwarded-for", "x-forwarded-host", "forwarded", "x-real-ip"))
    return host in ("127.0.0.1", "::1") and not proxied


def _exists(c, table: str) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone() is not None


def version() -> str:
    global _version
    if _version is None:
        try:
            root = Path(__file__).resolve().parents[2]
            # The service user does not own the checkout; tell git it is safe to read.
            _version = subprocess.run(["git", "-c", f"safe.directory={root}", "-C", str(root), "log", "-1",
                                       "--format=%h %s"], capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            _version = ""
    return _version


def _progress(c, player: str) -> dict:
    decided, active = [], None
    for table, label in LAYERS:
        if not _exists(c, table):
            continue
        row = c.execute(f"SELECT decision FROM {table} WHERE player_id=?", (player,)).fetchone()
        if row and row[0]:
            decided.append(label)
        elif row and active is None:
            active = label
    return {"decided": decided, "active": active, "fragments": len(decided)}


def overview() -> dict:
    now = time.time()
    with get_connection() as c:
        sessions_table = _exists(c, "online_sessions")
        players = []
        for player, name, location in c.execute(
                "SELECT id, name, location FROM agents WHERE controller_type='HUMAN' ORDER BY name").fetchall():
            entry = {"id": player, "name": name, "location": location, **_progress(c, player),
                     "last_seen": None, "sessions": 0, "minutes": 0}
            if sessions_table:
                count, seconds, last = c.execute(
                    "SELECT COUNT(*), COALESCE(SUM(last_seen - started), 0), MAX(last_seen) FROM online_sessions "
                    "WHERE player_id=?", (player,)).fetchone()
                entry.update(sessions=count, minutes=round(seconds / 60), last_seen=last)
            players.append(entry)
        names = {player["id"]: player["name"] for player in players}
        recent = []
        if sessions_table:
            for player, started, last in c.execute(
                    "SELECT player_id, started, last_seen FROM online_sessions ORDER BY id DESC LIMIT 30").fetchall():
                recent.append({"name": names.get(player, player), "started": started, "last_seen": last,
                               "minutes": round((last - started) / 60), "open": now - last < online.SESSION_GAP})
        events = []
        humans = tuple(names) or ("",)
        marks = ",".join("?" * len(humans))
        for created, minute, actor, action, target, details in c.execute(
                f"SELECT created_at, minute, actor_id, action, target, details FROM events WHERE actor_id IN ({marks}) "
                "ORDER BY id DESC LIMIT 40", humans).fetchall():
            events.append({"at": created, "minute": minute, "name": names.get(actor, actor),
                           "what": ACTIONS.get(action, action.replace("_", " ").lower()),
                           "detail": " ".join(str(part) for part in (target, details) if part)})
        signups = []
        if _exists(c, "online_logins"):
            # Names and dates only; password salts and hashes are never read here.
            signups = [{"name": name, "at": created} for name, created in c.execute(
                "SELECT a.name, l.created_at FROM online_logins l JOIN agents a ON a.id=l.actor_id "
                "ORDER BY l.created_at DESC LIMIT 8").fetchall()]
        minute = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()
    connected = []
    with online._lock:
        present = [dict(item) for item in online._presence.values() if time.monotonic() - item["at"] < online.PRESENCE_TTL]
    started = {entry["name"]: entry["started"] for entry in reversed(recent) if entry["open"]}
    for item in sorted(present, key=lambda item: item["name"]):
        connected.append({"name": item["name"], "location": item["location"], "x": round(item["x"], 1),
                          "z": round(item["z"], 1), "since": started.get(item["name"])})
    database = Path(DB_PATH)
    return {
        "now": now,
        "connected": connected,
        "players": players,
        "sessions": recent,
        "events": events,
        "signups": signups,
        "server": {
            "version": version(),
            "world_minute": minute[0] if minute else None,
            "uptime_minutes": round((now - STARTED) / 60),
            "ai": os.getenv("LAIN_LLM_MODEL", "") if os.getenv("LAIN_LLM_ENABLED") == "1" else "",
            "database_mb": round(database.stat().st_size / 1e6, 2) if database.exists() else None,
            "chat_messages": len(online._chat),
        },
    }


PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Panel de LAIN</title>
<style>
:root{--bg:#14161c;--panel:#1d2029;--line:#2c303c;--text:#dfe3ea;--muted:#8d95a5;--accent:#7fd6c2;--warn:#e7b35a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{display:flex;flex-wrap:wrap;gap:16px;align-items:baseline;padding:18px 20px;border-bottom:1px solid var(--line)}
h1{font-size:18px;margin:0;letter-spacing:.04em}h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 10px}
.meta{color:var(--muted);font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px;padding:16px 20px}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;overflow-x:auto}
table{width:100%;border-collapse:collapse}td,th{padding:5px 6px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:500;font-size:12px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--accent);margin-right:6px}
.empty{color:var(--muted)}.big{font-size:28px;font-weight:600;color:var(--accent)}.chips span{display:inline-block;border:1px solid var(--line);border-radius:6px;padding:0 5px;margin:1px;font-size:12px}
.open{color:var(--accent)}.stat{display:flex;gap:22px;flex-wrap:wrap}.stat div{min-width:90px}
</style></head><body>
<header><h1>LAIN · panel del servidor</h1><span class="meta" id="status">cargando…</span></header>
<div class="grid">
<section><h2>Conectados ahora</h2><div class="big" id="count">–</div><table id="connected"></table></section>
<section><h2>Servidor</h2><div class="stat" id="server"></div></section>
<section style="grid-column:1/-1"><h2>Jugadores</h2><table id="players"></table></section>
<section><h2>Conexiones recientes</h2><table id="sessions"></table></section>
<section><h2>Qué está pasando</h2><table id="events"></table></section>
<section><h2>Registros nuevos</h2><table id="signups"></table></section>
</div>
<script>
const PLACES={APARTMENT:"Casa",APARTMENT_DISTRICT:"Barrio",STATION:"Estación",SCHOOL:"Escuela",SCHOOL_LAB:"Aula de informática",
NIGHTCLUB:"Sótano Azul",IZAKAYA:"Izakaya",GROCERY:"Tienda",VIDEO_CLUB:"Videoclub",BOOKSHOP:"Librería",ARCADE:"Recreativos",CAFE:"Kissa"};
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const place=p=>PLACES[p]||p||"";
const ago=(t,now)=>{if(!t)return"nunca";const m=Math.round((now-t)/60);return m<1?"ahora":m<60?`hace ${m} min`:m<1440?`hace ${Math.round(m/60)} h`:`hace ${Math.round(m/1440)} d`};
const clock=t=>t?new Date(t*1000).toLocaleString("es-ES",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"";
function rows(id,head,items,cells,empty){const el=document.getElementById(id);
 el.innerHTML=items.length?"<tr>"+head.map(h=>`<th>${h}</th>`).join("")+"</tr>"+items.map(i=>"<tr>"+cells(i).map(c=>`<td>${c}</td>`).join("")+"</tr>").join(""):`<tr><td class="empty">${empty}</td></tr>`}
async function refresh(){
 try{const r=await fetch("/admin/data",{cache:"no-store"});const d=await r.json();const now=d.now;
  document.getElementById("count").textContent=d.connected.length;
  rows("connected",["Jugador","Dónde","Posición","Desde"],d.connected,c=>[`<span class="dot"></span>${esc(c.name)}`,esc(place(c.location)),`${c.x}, ${c.z}`,c.since?ago(c.since,now):""],"Nadie conectado ahora mismo.");
  const s=d.server;document.getElementById("server").innerHTML=[["Minuto del mundo",s.world_minute],["Encendido",`${s.uptime_minutes} min`],["IA",s.ai||"desactivada"],["Base de datos",`${s.database_mb} MB`],["Mensajes de chat",s.chat_messages],["Versión",esc(s.version)]].map(([k,v])=>`<div><div class="meta">${k}</div><div>${esc(v)}</div></div>`).join("");
  rows("players",["Jugador","Dónde","Capa actual","Capas hechas","Fragmentos","Última vez","Sesiones","Minutos"],d.players,p=>[esc(p.name),esc(place(p.location)),p.active?`Capa ${p.active}`:(p.fragments?"—":"prólogo"),`<span class="chips">${p.decided.map(x=>`<span>${x}</span>`).join("")}</span>`,`${p.fragments}/7`,ago(p.last_seen,now),p.sessions,p.minutes],"Todavía no hay jugadores.");
  rows("sessions",["Jugador","Entró","Duración",""],d.sessions,x=>[esc(x.name),clock(x.started),`${x.minutes} min`,x.open?'<span class="open">conectado</span>':""],"Sin conexiones registradas todavía.");
  rows("events",["Cuándo","Jugador","Qué",""],d.events,e=>[esc(e.at),esc(e.name),esc(e.what),esc(e.detail)],"Nada todavía.");
  rows("signups",["Nombre","Cuándo"],d.signups,u=>[esc(u.name),clock(u.at)],"Sin registros con contraseña.");
  document.getElementById("status").textContent="actualizado "+new Date().toLocaleTimeString("es-ES")+" · se refresca cada 5 s";
 }catch(e){document.getElementById("status").textContent="sin conexión con el servidor (¿sigue abierto el túnel?)"}}
refresh();setInterval(refresh,5000);
</script></body></html>"""
