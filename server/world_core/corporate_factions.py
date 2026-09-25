"""Additive NOEMA save migration and faction-scoped evidence/operations.

Legacy KAGAMI tables retain their meaning. Every NOEMA percentage is transferred
from corporate control, never minted or taken from a player's migration balance.
"""
import os

KAGAMI = "KAGAMI"
NOEMA = "NOEMA"
PERSONNEL = {
    "RELAY_STATION": ("CIVIL_201", "Mika Senda", "Encuestadora de transporte",
                      "Dice que compara horarios y registros de paso."),
    "RELAY_SCHOOL": ("CIVIL_202", "Ren Fujimoto", "Revisor del archivo escolar",
                     "Dice que revisa las autorizaciones del aula."),
    "RELAY_VIDEO": ("CIVIL_203", "Aya Morita", "Catalogadora de cintas",
                    "Dice que comprueba las fichas de préstamo."),
}
SEED_CONTROL = {"RELAY_STATION": 20, "RELAY_SCHOOL": 30, "RELAY_VIDEO": 45}


def active(c):
    return (c.execute("SELECT 1 FROM sqlite_master WHERE name='network_noema_relays'").fetchone() is not None
            and c.execute("SELECT 1 FROM network_noema_relays LIMIT 1").fetchone() is not None)


def initialize(c, relays):
    if os.getenv("LAIN_NOEMA", "0") != "1": return
    # Schema creation may commit, so the ownership transfer starts a separate
    # explicit transaction. A failed transfer rolls back all relay allocations.
    c.executescript("""
    CREATE TABLE IF NOT EXISTS network_noema_relays (
      relay TEXT PRIMARY KEY, amount INTEGER NOT NULL CHECK(amount BETWEEN 0 AND 100),
      suppressed_until INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS network_operation_factions (
      operation_id INTEGER PRIMARY KEY, faction TEXT NOT NULL CHECK(faction='NOEMA'));
    CREATE TABLE IF NOT EXISTS network_noema_discoveries (
      actor TEXT NOT NULL, relay TEXT NOT NULL, acquired_minute INTEGER NOT NULL,
      proof_operation INTEGER, revealed INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(actor,relay));
    """)
    c.execute("BEGIN IMMEDIATE")
    for relay in relays:
        if c.execute("SELECT 1 FROM network_noema_relays WHERE relay=?",(relay,)).fetchone(): continue
        old=c.execute("SELECT corporation FROM network_relays WHERE id=?",(relay,)).fetchone()[0]
        amount=min(old,SEED_CONTROL[relay])
        c.execute("INSERT INTO network_noema_relays(relay,amount) VALUES(?,?)",(relay,amount))
        c.execute("UPDATE network_relays SET corporation=corporation-? WHERE id=?",(amount,relay))


def validate(c, faction):
    if faction not in {KAGAMI, NOEMA} or (faction==NOEMA and not active(c)):
        raise ValueError("INVALID_CORPORATION")


def balance(c, relay, faction):
    if faction==KAGAMI:
        return c.execute("SELECT corporation FROM network_relays WHERE id=?",(relay,)).fetchone()[0]
    return c.execute("SELECT amount FROM network_noema_relays WHERE relay=?",(relay,)).fetchone()[0]


def add_control(c, relay, faction, amount):
    if faction==KAGAMI:
        c.execute("UPDATE network_relays SET corporation=corporation+? WHERE id=?",(amount,relay))
    else:
        c.execute("UPDATE network_noema_relays SET amount=amount+? WHERE relay=?",(amount,relay))


def suppressed_until(c, relay, faction):
    if faction==KAGAMI:
        return c.execute("SELECT suppressed_until FROM network_relays WHERE id=?",(relay,)).fetchone()[0]
    return c.execute("SELECT suppressed_until FROM network_noema_relays WHERE relay=?",(relay,)).fetchone()[0]


def suppress(c, relay, faction, until):
    if faction==KAGAMI:
        c.execute("UPDATE network_relays SET suppressed_until=? WHERE id=?",(until,relay))
    else:
        c.execute("UPDATE network_noema_relays SET suppressed_until=? WHERE relay=?",(until,relay))


def operation_faction(c, operation):
    if active(c) and c.execute("SELECT 1 FROM network_operation_factions WHERE operation_id=?",(operation,)).fetchone():
        return NOEMA
    return KAGAMI


def pending_operations(c, relay, faction, actor=None):
    rows=c.execute("SELECT id,target,due_minute FROM network_operations WHERE relay=? AND status='PENDING' ORDER BY id",(relay,)).fetchall()
    return [row for row in rows if (actor is None or row[1]==actor) and operation_faction(c,row[0])==faction]


def discovery(c, actor, relay, faction):
    if faction==KAGAMI:
        return c.execute("SELECT acquired_minute,proof_operation,revealed FROM network_discoveries WHERE actor_id=? AND relay=?",(actor,relay)).fetchone()
    if not active(c): return None
    return c.execute("SELECT acquired_minute,proof_operation,revealed FROM network_noema_discoveries WHERE actor=? AND relay=?",(actor,relay)).fetchone()


def inspect(c, actor, relay, faction, now):
    operations=pending_operations(c,relay,faction)
    op=operations[0][0] if operations else None
    if faction==KAGAMI:
        c.execute("""INSERT INTO network_discoveries(actor_id,relay,acquired_minute,proof_operation) VALUES(?,?,?,?)
          ON CONFLICT(actor_id,relay) DO UPDATE SET proof_operation=excluded.proof_operation""",(actor,relay,now,op))
    else:
        c.execute("""INSERT INTO network_noema_discoveries(actor,relay,acquired_minute,proof_operation) VALUES(?,?,?,?)
          ON CONFLICT(actor,relay) DO UPDATE SET proof_operation=excluded.proof_operation""",(actor,relay,now,op))
    return op


def reveal(c, actor, relay, faction):
    if faction==KAGAMI:
        c.execute("UPDATE network_discoveries SET revealed=1 WHERE actor_id=? AND relay=?",(actor,relay))
    else:
        c.execute("UPDATE network_noema_discoveries SET revealed=1 WHERE actor=? AND relay=?",(actor,relay))


def current_proof(c, actor, relay, faction):
    known=discovery(c,actor,relay,faction)
    return bool(known and known[1] is not None and any(op[0]==known[1] for op in pending_operations(c,relay,faction)))


def label(c, actor, relay, faction):
    if discovery(c,actor,relay,faction): return faction
    return "Administrador de registros" if faction==NOEMA else "Administrador de líneas"


def controllers(c, actor, relay):
    result=[]
    for faction in [KAGAMI,NOEMA] if active(c) else [KAGAMI]:
        result.append({"slot":"RECORDS" if faction==NOEMA else "LINES",
                       "name":label(c,actor,relay,faction),"control":balance(c,relay,faction),
                       "suppressed_until":suppressed_until(c,relay,faction)})
    return result


def rival_opportunity(c, relay, exposed):
    """A bounded response to an exposed agent; never touches human ownership."""
    if not active(c): return "",0
    rival=NOEMA if exposed==KAGAMI else KAGAMI
    amount=min(5,balance(c,relay,exposed))
    add_control(c,relay,exposed,-amount)
    add_control(c,relay,rival,amount)
    return rival,amount
