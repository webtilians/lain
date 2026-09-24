"""Chapter 1: a bounded, authored investigation owned by World Core.

Testimony, document timestamps and hypotheses are NOT world facts. Every
mutation is transactional and idempotent; projections never advance the case.
NPC context contains only that NPC's recollections or explicitly received reports.
"""
import json
import os
import re

from .database import get_connection

PLAYER = "PLAYER_1"
HARUTO = "RESIDENT_001"
AIKO = "RESIDENT_006"
PEOPLE = {HARUTO: "Haruto", AIKO: "Aiko", "PROFESSOR": "Profesor", "RYOKO": "Ryoko"}
PLACES = {HARUTO: "APARTMENT_DISTRICT", AIKO: "APARTMENT_DISTRICT",
          "PROFESSOR": "SCHOOL_LAB", "RYOKO": "NIGHTCLUB"}
TITLE = "Ya habías estado aquí"


def initialize_chapter() -> None:
    with get_connection() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS chapter_one (
                player_id TEXT PRIMARY KEY, started_minute INTEGER NOT NULL,
                connection_minute INTEGER NOT NULL, decision TEXT,
                decided_minute INTEGER, hypothesis TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS chapter_one_evidence (
                player_id TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL,
                kind TEXT NOT NULL, source_id TEXT NOT NULL, source_label TEXT NOT NULL,
                text TEXT NOT NULL, acquired_minute INTEGER NOT NULL,
                claimed_time TEXT NOT NULL, event_id INTEGER,
                PRIMARY KEY(player_id,id));
            CREATE TABLE IF NOT EXISTS chapter_one_links (
                player_id TEXT NOT NULL, first_id TEXT NOT NULL, second_id TEXT NOT NULL,
                relation TEXT NOT NULL, minute INTEGER NOT NULL,
                PRIMARY KEY(player_id,first_id,second_id,relation));
            CREATE TABLE IF NOT EXISTS chapter_one_knowledge (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
                text TEXT NOT NULL, source_id TEXT NOT NULL, minute INTEGER NOT NULL,
                PRIMARY KEY(player_id,actor_id,evidence_id));
            CREATE TABLE IF NOT EXISTS chapter_one_relationships (
                player_id TEXT NOT NULL, actor_id TEXT NOT NULL, stance TEXT NOT NULL,
                reason TEXT NOT NULL, source_id TEXT NOT NULL, minute INTEGER NOT NULL,
                PRIMARY KEY(player_id,actor_id));
            CREATE TABLE IF NOT EXISTS chapter_one_requests (
                player_id TEXT NOT NULL, request_id TEXT NOT NULL,
                command TEXT NOT NULL, response TEXT NOT NULL,
                PRIMARY KEY(player_id,request_id));
        """)
    activate_chapter()


def _exists(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='chapter_one'").fetchone() is not None


def _evidence(c, player, eid, title, kind, source, label, text, minute,
              claimed="Fecha no comprobada", event_id=None):
    c.execute("""INSERT OR IGNORE INTO chapter_one_evidence
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (player, eid, title, kind, source, label, text, minute, claimed, event_id))


def _learn(c, player, actor, eid, text, source, minute):
    c.execute("INSERT OR IGNORE INTO chapter_one_knowledge VALUES(?,?,?,?,?,?)",
              (player, actor, eid, text, source, minute))


def activate_chapter(player=PLAYER) -> bool:
    """Called only by bootstrap or an accepted connection, never by GET /state."""
    if os.getenv("LAIN_CHAPTER_ONE", "0") != "1":
        return False
    with get_connection() as c:
        if not _exists(c):
            return False
        connection = c.execute("""SELECT acknowledged_minute FROM world_messages
            WHERE id='MSG_BOOTSTRAP_001' AND recipient_id=? AND acknowledged=1""", (player,)).fetchone()
        if connection is None:
            return False
        minute = c.execute("SELECT minute FROM simulation_state WHERE id=1").fetchone()[0]
        first = connection[0] if connection[0] is not None else minute
        if c.execute("INSERT OR IGNORE INTO chapter_one(player_id,started_minute,connection_minute) VALUES(?,?,?)",
                     (player, minute, first)).rowcount == 0:
            return False
        _evidence(c, player, "RETURN_MESSAGE", "Has vuelto", "MESSAGE", "UNKNOWN_WIRED", "Identidad desconocida · Wired",
                  "Has vuelto.", minute, f"Recibido al abrir este capítulo, minuto {minute}")
        memories = {
            HARUTO: "Creo recordar al jugador en la escuela la noche anterior. No comprobé el reloj ni vi quién abrió la puerta.",
            AIKO: "Recuerdo un ruido de cerrojo y una silueta. Miré el reloj del pabellón: 22:10. No distinguí la cara. Prefiero contarlo en privado.",
            "PROFESSOR": "Recuerdo haber cerrado la escuela la noche anterior. Dejé firmado el parte de cierre. No presencié la noche entera.",
            "RYOKO": "Los registros viejos de la escuela a veces conservan el nombre de una cuenta compartida y un reloj sin sincronizar. No sé quién usó esa cuenta.",
        }
        for actor, memory in memories.items():
            _learn(c, player, actor, "OWN_RECOLLECTION", memory, "OWN_RECOLLECTION", minute)
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'CHAPTER_ONE_STARTED','WIRED','RETURN_MESSAGE')", (minute, player))
        return True


def _known(c, player):
    return {r[0] for r in c.execute("SELECT id FROM chapter_one_evidence WHERE player_id=?", (player,))}


def _choice(label, action, target="", **data):
    return {"text": label, "action": action, "target": target, "data": data}


def _page(speaker, text, choices=()):
    return {"speaker": speaker, "text": text, "choices": list(choices)}


def _colocated(c, player, actor, location):
    if actor not in PLACES or PLACES[actor] != location:
        raise ValueError("CHARACTER_NOT_PRESENT")
    if actor in (HARUTO, AIKO):
        row = c.execute("SELECT location FROM agents WHERE id=?", (actor,)).fetchone()
        if row != (location,):
            raise ValueError("CHARACTER_NOT_PRESENT")


def _share(c, player, actor, eid, minute, source=PLAYER):
    row = c.execute("SELECT text,source_label FROM chapter_one_evidence WHERE player_id=? AND id=?", (player, eid)).fetchone()
    if row is None:
        raise ValueError("EVIDENCE_NOT_KNOWN")
    _learn(c, player, actor, eid, f"Me han comunicado este contenido, atribuido a {row[1]}: {row[0]}", source, minute)


def _talk(c, player, actor, choice, minute, location, run):
    _colocated(c, player, actor, location)
    known = _known(c, player)
    menus = {
        HARUTO: [("NIGHT", "¿Qué recuerdas de aquella noche?"), ("DETAIL", "¿Con quién me viste hablar?"), ("CLOSURE", "El parte dice que estaba cerrado.")],
        AIKO: [("PRIVATE", "Preguntarle en voz baja por la escuela."), ("CLOCK", "¿Cómo sabes qué hora era?"), ("PUBLIC", "Repetir su testimonio delante de los vecinos.")],
        "PROFESSOR": [("NIGHT", "¿Estuvo abierta la escuela anoche?"), ("LOG", "¿Puedo mirar el registro del ordenador?"), ("REPORT", "Hablar de la copia con mi nombre.")],
        "RYOKO": [("MESSAGE", "Contarle que alguien escribió «Has vuelto»."), ("CLOCK", "¿Una fecha de acceso puede estar equivocada?"), ("REPORT", "Hablar de la copia con mi nombre.")],
    }
    allowed = {"INTRO"} | {item[0] for item in menus[actor]}
    if choice not in allowed:
        raise ValueError("INVALID_CHAPTER_QUESTION")
    name = PEOPLE[actor]
    if actor in (HARUTO, AIKO):
        name = c.execute("SELECT name FROM agents WHERE id=?", (actor,)).fetchone()[0]
    if choice == "REPORT":
        if "IDENTITY_LOG" not in known:
            return _page(name, "«No puedo pronunciarme sobre una copia que todavía no has encontrado.»")
        if run[3]:
            return _decision_response(c, player, actor, run[3])
        if actor == "PROFESSOR":
            return _page(name, "«Puedo incorporarla al archivo con tu nombre. Informaré a Ryoko de la copia; quizá no le guste verse implicada. Tú decides.»", [
                _choice("Entregar la copia y autorizar el aviso a Ryoko.", "DECIDE", actor, decision="DISCLOSE")])
        return _page(name, "«Puedo guardar la copia contigo. Al profesor solo le diré que hay una fecha imposible y que no quieres identificar la cuenta. Perderás su acceso al anexo, pero puedo enseñarte otro paquete.»", [
            _choice("Sellar la copia y avisar solo de la fecha anómala.", "DECIDE", actor, decision="SEAL")])
    if actor == HARUTO:
        if choice in {"INTRO", "NIGHT"}:
            text = "«Ya habías estado aquí. Te vi en la escuela anoche, cuando todo estaba oscuro. Llevabas un papel doblado. O al menos... pensé que eras tú.»"
            _evidence(c, player, "NIGHT_SIGHTING", "Haruto te sitúa en la escuela", "TESTIMONY", actor, name, text, minute, "La noche anterior, según Haruto")
        elif choice == "DETAIL":
            visit = c.execute("SELECT id,minute FROM events WHERE actor_id=? AND action='PROLOGUE_TALK' AND target='PROFESSOR' ORDER BY id LIMIT 1", (player,)).fetchone()
            if visit:
                text = "«El otro día preguntabas por Ryoko. El profesor no estaba; te respondió una alumna desde la puerta.»"
                _evidence(c, player, "WRONG_DETAIL", "Una visita recordada de otra manera", "TESTIMONY", actor, name, text, minute, "La visita del prólogo, según Haruto")
                _evidence(c, player, "MY_VISIT", "Mi conversación con el profesor", "OBSERVATION", player, "Tu experiencia conservada",
                          "Pregunté por el antiguo alumno y fue el profesor quien me dijo el nombre de Ryoko. Estaba presente.", minute,
                          f"Prólogo · minuto {visit[1]}", visit[0])
            else:
                text = "«No llegué a ver con quién hablabas. La puerta me tapaba la mitad del pasillo.»"
        else:
            if not known & {"CLOSURE_SHEET", "PROFESSOR_CLOSED"}:
                raise ValueError("EVIDENCE_NOT_KNOWN")
            eid = "CLOSURE_SHEET" if "CLOSURE_SHEET" in known else "PROFESSOR_CLOSED"
            _share(c, player, actor, eid, minute)
            text = "«Entonces alguien tuvo que abrir. O confundí la noche. No borres lo que te dije solo porque no encaja.»"
    elif actor == AIKO:
        if choice == "INTRO":
            text = "Aiko mira hacia el colegio. «Se oye todo desde este banco. Lo que cuesta es saber de dónde viene.»"
        elif choice == "PRIVATE":
            text = "Baja la voz. «Oí un cerrojo y vi una silueta junto al pabellón. El reloj marcaba 22:10. No le vi la cara. No pongas mi nombre en boca de todos.»"
            _evidence(c, player, "AIKO_PRIVATE", "Aiko: un cerrojo y una silueta", "TESTIMONY", actor, name+" · conversación privada", text, minute, "22:10 según el reloj que miró Aiko")
        elif choice == "CLOCK":
            text = "«Miré el reloj exterior del colegio, no el mío. Lleva días marcando lo mismo. No sé cuánto cambia eso lo que oí.»"
            _evidence(c, player, "CLOCK_ACCOUNT", "La hora de Aiko", "TESTIMONY", actor, name, text, minute)
        else:
            if "AIKO_PRIVATE" not in known:
                raise ValueError("EVIDENCE_NOT_KNOWN")
            text = "Aiko mira a los demás. «Yo no he dicho que viera entrar a nadie. No sé nada de esa noche.» Cuando vuelves a mirarla, aparta los ojos."
            _evidence(c, player, "AIKO_DENIAL", "Aiko lo niega ante los vecinos", "OBSERVATION", actor, "Declaración pública que has presenciado", text, minute, f"Ahora · minuto {minute}")
            _learn(c, player, actor, "EXPOSED", "El jugador repitió mi confidencia delante de los vecinos. No volveré a ampliarla.", player, minute)
    elif actor == "PROFESSOR":
        if choice in {"INTRO", "NIGHT"}:
            text = "«Cerré la escuela anoche. Firmé el parte del pasillo. Nadie tenía permiso para estar dentro. Eso no significa que yo vigilase la puerta toda la noche.»"
            _evidence(c, player, "PROFESSOR_CLOSED", "El profesor afirma haber cerrado", "TESTIMONY", actor, name, text, minute, "La noche anterior, según el profesor")
        else:
            text = "«El tercer ordenador conserva el archivo local. Puedes leer la cabecera; la lista de cuentas necesita una referencia del archivo. El parte del pasillo y la copia de la Wired no siempre coinciden.»"
    else:
        if choice == "INTRO":
            text = "«Te miro y tengo la sensación de que esta conversación ya empezó. ¿Te ha contestado alguien?»"
        elif choice == "MESSAGE":
            _share(c, player, actor, "RETURN_MESSAGE", minute)
            text = "«¿Has vuelto? Eso no prueba que te conozca. Tal vez el mensaje estaba esperando a cualquier persona. Busca la escuela en el archivo de la Wired y fíjate en quién firma los registros.»"
        else:
            text = "«Sí. Algunos ordenadores conservaban el reloj sin sincronizar; otros usaban una cuenta compartida. Un nombre en un registro no es una persona entrando por una puerta.»"
            _evidence(c, player, "RYOKO_CLOCK", "Ryoko: una cuenta no es una persona", "TESTIMONY", actor, name, text, minute)
    if actor == AIKO and choice == "PRIVATE" and c.execute("SELECT 1 FROM chapter_one_knowledge WHERE player_id=? AND actor_id=? AND evidence_id='EXPOSED'", (player, actor)).fetchone():
        text = "«Ya me oyeron todos. No voy a contarte nada más.» Aiko deja un espacio entre tú y el banco."
    if run[3] and actor in ("PROFESSOR", "RYOKO") and choice == "INTRO":
        text = _decision_response(c, player, actor, run[3])["text"]
    for eid, statement in c.execute("SELECT id,text FROM chapter_one_evidence WHERE player_id=? AND source_id=? AND kind='TESTIMONY'", (player,actor)).fetchall():
        _learn(c, player, actor, eid, statement, "OWN_RECOLLECTION", minute)
    choices = []
    for cid, label in menus[actor]:
        if cid == "CLOSURE" and not known & {"CLOSURE_SHEET", "PROFESSOR_CLOSED"}:
            continue
        if cid == "PUBLIC" and "AIKO_PRIVATE" not in _known(c, player):
            continue
        if cid == "REPORT" and "IDENTITY_LOG" not in known:
            continue
        choices.append(_choice(label, "TALK", actor, choice=cid))
    return _page(name, text, choices)


def _contradiction(c, player):
    pairs = [{"NIGHT_SIGHTING", "CLOSURE_SHEET"}, {"NIGHT_SIGHTING", "PROFESSOR_CLOSED"}, {"WRONG_DETAIL", "MY_VISIT"}]
    return any({a,b} in pairs for a,b in c.execute("SELECT first_id,second_id FROM chapter_one_links WHERE player_id=? AND relation='CONTRADICTS'", (player,)))


def _reconstruct(c, player, minute, run):
    if not _contradiction(c, player) or not _known(c, player) & {"LOCAL_LOG", "WIRED_MIRROR"}:
        return _page("Archivo de acceso", "La cabecera no basta para identificar la cuenta. Necesitas contrastar al menos dos versiones en tu archivo J y conservar una referencia del registro, local o remota.")
    name = c.execute("SELECT name FROM agents WHERE id=?", (player,)).fetchone()[0]
    text = (f"CUENTA: {name}\nMARCA LOCAL: minuto {run[2]-60}\n"
            f"PRIMERA CONEXIÓN CONSERVADA: minuto {run[2]}\n"
            "El archivo fecha ese acceso 60 minutos antes de tu primera conexión conservada. "
            "No hay firma verificable ni prueba de quién utilizó la cuenta. El reloj local puede estar equivocado.")
    _evidence(c, player, "IDENTITY_LOG", "Tu nombre antes de la primera conexión", "RECORD", "SCHOOL_ARCHIVE", "Registro reconstruido · firma no verificada", text, minute,
              f"El documento afirma minuto {run[2]-60}; autenticidad pendiente")
    return _page("Un nombre que ya estaba escrito", text+"\n\nPuedes conservar la copia, enseñársela al profesor o hablar con Ryoko. Nadie sabe todavía si es un registro falso, otra persona o un recuerdo incompleto.")


def _examine(c, player, target, choice, minute, location, run):
    expected = {"CLOSURE_SHEET": "SCHOOL", "SCHOOL_CLOCK": "SCHOOL", "SCHOOL_PC": "SCHOOL_LAB"}
    if target not in expected or expected[target] != location:
        raise ValueError("OBJECT_NOT_PRESENT")
    if choice not in {"OPEN", "RECONSTRUCT", "APPENDIX"} or (choice != "OPEN" and target != "SCHOOL_PC"):
        raise ValueError("INVALID_CHAPTER_ACTION")
    if target == "CLOSURE_SHEET":
        text = "PARTE DE CIERRE · NOCHE ANTERIOR\nPabellón B cerrado. Llave entregada. Firma: profesor de informática.\nLa hoja está sujeta con una grapa nueva. El texto declara un cierre; no demuestra que nadie entrara después."
        _evidence(c, player, target, "El parte de cierre", "DOCUMENT", "CLOSURE_SHEET", "Hoja del pasillo · firmada por el profesor", text, minute, "Noche anterior, según el documento")
        return _page("Parte en el pasillo", text)
    if target == "SCHOOL_CLOCK":
        text = "El reloj del pabellón marca 22:10. El segundero no avanza. Hay una nota de mantenimiento: «Pila pendiente». Esto no permite fechar lo que vio Aiko."
        _evidence(c, player, target, "El reloj está detenido", "OBSERVATION", target, "Reloj que has examinado", text, minute, f"Observado ahora · minuto {minute}")
        return _page("22:10", text)
    if choice == "RECONSTRUCT":
        return _reconstruct(c, player, minute, run)
    if choice == "APPENDIX":
        if run[3] != "DISCLOSE":
            raise ValueError("APPENDIX_NOT_AVAILABLE")
        text = "El profesor ha adjuntado una hoja: «El reloj se reajustó desde una copia externa. No consta quién solicitó el cambio». La casilla del operador está recortada."
        _evidence(c, player, "MAINTENANCE_APPENDIX", "Un cambio de reloj sin operador", "DOCUMENT", "PROFESSOR", "Anexo facilitado por el profesor", text, minute)
        return _page("Anexo nuevo", text)
    text = "ARCHIVO LOCAL · CABECERA 04-17\nCuenta: [índice pendiente]\nProcedencia: restauración externa\nEstado: firma ausente\nUn margen escrito a mano dice: «No confundas una cuenta con quien la recuerda»."
    _evidence(c, player, "LOCAL_LOG", "Cabecera del ordenador de la escuela", "RECORD", target, "Archivo local del tercer ordenador", text, minute, "Reloj local sin verificar")
    choices = [_choice("Contrastar las referencias y leer la cuenta.", "EXAMINE", target, choice="RECONSTRUCT")]
    if run[3] == "DISCLOSE":
        choices.append(_choice("Leer el anexo que dejó el profesor.", "EXAMINE", target, choice="APPENDIX"))
    if run[3] == "SEAL":
        text += "\n\nEl índice nominal está ahora sellado. Tu copia personal sigue en J."
    return _page("Ordenador de la escuela", text, choices)


def _wired(c, player, target, minute, location, run):
    if location != "APARTMENT":
        raise ValueError("TERMINAL_NOT_PRESENT")
    if target not in {"OPEN", "REPLY", "SEARCH", "RECONSTRUCT", "PACKET"}:
        raise ValueError("INVALID_CHAPTER_ACTION")
    if target == "RECONSTRUCT":
        return _reconstruct(c, player, minute, run)
    if target == "PACKET":
        if run[3] != "SEAL":
            raise ValueError("PACKET_NOT_AVAILABLE")
        text = "Paquete de Ryoko: otra cabecera 04-17. El campo de cuenta está vacío, pero tiene el mismo sello de restauración. Alguien conservó también la versión sin tu nombre."
        _evidence(c, player, "UNDATED_PACKET", "Otra copia sin nombre", "RECORD", "RYOKO", "Paquete que te envió Ryoko", text, minute, "Sin fecha verificable")
        return _page("Paquete sellado", text)
    if target == "REPLY":
        text = "TÚ: ¿Quién eres? ¿Por qué dices que he vuelto?\n\n???: No sé quién eres ahora. La escuela conserva una entrada. No todas las copias recuerdan lo mismo."
        _evidence(c, player, "UNKNOWN_REPLY", "Una entrada que conserva la escuela", "MESSAGE", "UNKNOWN_WIRED", "Respuesta de identidad desconocida", text, minute)
    elif target == "SEARCH":
        text = "BÚSQUEDA: ESCUELA / PABELLÓN B\nUna copia remota devuelve la cabecera 04-17, anterior al índice actual. No declara quién la subió. Conserva una cuenta oculta y la nota «restauración externa». El reloj del archivo no está sincronizado."
        _evidence(c, player, "WIRED_MIRROR", "El espejo del archivo escolar", "RECORD", "UNKNOWN_MIRROR", "Copia remota · autor desconocido", text, minute, "Reloj del archivo sin sincronizar")
    else:
        text = "BUZÓN · IDENTIDAD DESCONOCIDA\n\n«Has vuelto».\n\nEl mensaje no incluye una firma. La conexión sigue abierta."
    choices = [_choice("Responder: «¿Quién eres?»", "WIRED", "REPLY"),
               _choice("Buscar la escuela en el archivo remoto.", "WIRED", "SEARCH")]
    if _known(c, player) & {"WIRED_MIRROR", "LOCAL_LOG"}:
        choices.append(_choice("Contrastar referencias y reconstruir la cuenta.", "WIRED", "RECONSTRUCT"))
    if run[3] == "SEAL":
        choices.append(_choice("Abrir el paquete de Ryoko.", "WIRED", "PACKET"))
    return _page("THE WIRED · ARCHIVO", text, choices)


def _decision_response(c, player, actor, decision):
    lines = {
        ("PROFESSOR", "DISCLOSE"): "El profesor aparta una silla. «Has dejado constancia con tu nombre. Confío en que leas también lo que no encaja: he puesto el anexo junto al tercer ordenador.»",
        ("RYOKO", "DISCLOSE"): "Ryoko guarda su disquete. «El profesor me envió la copia que autorizaste. Ahora mi nombre también circula. Seguiré hablando contigo, pero el otro paquete me lo quedo.»",
        ("PROFESSOR", "SEAL"): "El profesor cierra su carpeta. «Ryoko me avisó de una fecha anómala y de que has ocultado la cuenta. Puedes consultar la cabecera, pero no te daré mi anexo sin saber qué estás comparando.»",
        ("RYOKO", "SEAL"): "Ryoko deja un disquete a tu alcance. «Has confiado en mí. Guardé la copia y avisé al profesor solo de la fecha. Te he enviado otro paquete a tu terminal; míralo cuando vuelvas.»",
    }
    return _page(PEOPLE[actor], lines[(actor, decision)])


def _decide(c, player, actor, decision, minute, location, run):
    _colocated(c, player, actor, location)
    if decision not in {"DISCLOSE", "SEAL"} or actor != ("PROFESSOR" if decision == "DISCLOSE" else "RYOKO"):
        raise ValueError("INVALID_CHAPTER_DECISION")
    if run[3]:
        raise ValueError("CHAPTER_DECISION_ALREADY_MADE")
    if "IDENTITY_LOG" not in _known(c, player):
        raise ValueError("EVIDENCE_NOT_KNOWN")
    c.execute("UPDATE chapter_one SET decision=?,decided_minute=? WHERE player_id=? AND decision IS NULL", (decision, minute, player))
    _share(c, player, actor, "IDENTITY_LOG", minute)
    if decision == "DISCLOSE":
        _share(c, player, "RYOKO", "IDENTITY_LOG", minute, source="PROFESSOR")
    else:
        _learn(c, player, "PROFESSOR", "REDACTED_NOTICE", "Ryoko me comunicó una fecha de acceso anómala y que el jugador reserva la identidad. No recibí la cuenta ni el documento íntegro.", "RYOKO", minute)
    for recipient in ("PROFESSOR", "RYOKO"):
        stance = "TRUSTING" if recipient == actor else "GUARDED"
        source = player if recipient == actor else actor
        c.execute("INSERT INTO chapter_one_relationships VALUES(?,?,?,?,?,?)",
                  (player, recipient, stance, decision, source, minute))
    return _decision_response(c, player, actor, decision)


def perform_chapter_action(player: str, action: str, target: str, data: dict,
                           minute: int, request_id: str) -> dict:
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
        raise ValueError("INVALID_REQUEST_ID")
    if not isinstance(data, dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in data.items()) or len(json.dumps(data)) > 3000:
        raise ValueError("INVALID_CHAPTER_DATA")
    command = json.dumps([action, target, data], sort_keys=True, ensure_ascii=False)
    with get_connection() as c:
        c.execute("BEGIN IMMEDIATE")
        if not _exists(c):
            raise ValueError("CHAPTER_NOT_STARTED")
        run = c.execute("SELECT player_id,started_minute,connection_minute,decision FROM chapter_one WHERE player_id=?", (player,)).fetchone()
        if run is None:
            raise ValueError("CHAPTER_NOT_STARTED")
        old = c.execute("SELECT command,response FROM chapter_one_requests WHERE player_id=? AND request_id=?", (player, request_id)).fetchone()
        if old:
            if old[0] != command:
                raise ValueError("REQUEST_ID_REUSED")
            return json.loads(old[1])
        location = c.execute("SELECT location FROM agents WHERE id=?", (player,)).fetchone()[0]
        if action == "TALK":
            result = _talk(c, player, target, data.get("choice", "INTRO"), minute, location, run)
        elif action == "EXAMINE":
            result = _examine(c, player, target, data.get("choice", "OPEN"), minute, location, run)
        elif action == "WIRED":
            result = _wired(c, player, target, minute, location, run)
        elif action == "DECIDE":
            result = _decide(c, player, target, data.get("decision"), minute, location, run)
        elif action == "LINK":
            a, b, relation = data.get("first"), data.get("second"), data.get("relation")
            known = _known(c, player)
            if not isinstance(a, str) or not isinstance(b, str) or a == b or not {a,b} <= known or relation not in {"CONTRADICTS", "SUPPORTS", "RELATED"}:
                raise ValueError("INVALID_EVIDENCE_LINK")
            a,b = sorted((a,b))
            c.execute("INSERT OR IGNORE INTO chapter_one_links VALUES(?,?,?,?,?)", (player,a,b,relation,minute))
            result = _page("Archivo personal", "Relación guardada como interpretación tuya. No establece qué fuente tiene razón.")
        elif action == "HYPOTHESIS":
            note = data.get("text")
            if not isinstance(note, str) or not 1 <= len(note.strip()) <= 500 or any(ord(char)<32 and char!='\n' for char in note):
                raise ValueError("INVALID_HYPOTHESIS")
            c.execute("UPDATE chapter_one SET hypothesis=? WHERE player_id=?", (note.strip(), player))
            result = _page("Hipótesis personal", "Guardada. Sigue sin verificar; nadie la conoce por el mero hecho de escribirla.")
        else:
            raise ValueError("INVALID_CHAPTER_ACTION")
        c.execute("INSERT INTO chapter_one_requests VALUES(?,?,?,?)", (player,request_id,command,json.dumps(result,ensure_ascii=False)))
        c.execute("INSERT INTO events(minute,actor_id,action,target,details) VALUES(?,?,'CHAPTER_ONE_ACTION',?,?)", (minute,player,target,action))
        return result


def chapter_snapshot(player=PLAYER) -> dict:
    with get_connection() as c:
        if not _exists(c):
            return {"active": False}
        run = c.execute("SELECT started_minute,connection_minute,decision,hypothesis FROM chapter_one WHERE player_id=?", (player,)).fetchone()
        if run is None:
            return {"active": False}
        columns = ["id","title","kind","source_id","source_label","text","acquired_minute","claimed_time","event_id"]
        evidence = [dict(zip(columns,row)) for row in c.execute("SELECT id,title,kind,source_id,source_label,text,acquired_minute,claimed_time,event_id FROM chapter_one_evidence WHERE player_id=? ORDER BY acquired_minute,rowid", (player,))]
        links = [{"first":a,"second":b,"relation":rel,"minute":when} for a,b,rel,when in c.execute("SELECT first_id,second_id,relation,minute FROM chapter_one_links WHERE player_id=? ORDER BY minute,rowid",(player,))]
        return {"active": True, "title": TITLE, "started_minute":run[0], "connection_minute":run[1],
                "decision":run[2], "hypothesis":run[3], "hypothesis_status":"UNVERIFIED",
                "evidence":evidence, "links":links, "contradiction_linked":_contradiction(c,player),
                "characters":list(PEOPLE), "notification":"Has vuelto"}


def chapter_actor_context(actor: str) -> dict | None:
    """Server-only, per-recipient memory. Never expose the player's archive here."""
    with get_connection() as c:
        if not _exists(c):
            return None
        rows = c.execute("SELECT evidence_id,text,source_id,minute FROM chapter_one_knowledge WHERE actor_id=? AND player_id=? ORDER BY minute,rowid", (actor,PLAYER)).fetchall()
        if not rows:
            return None
        relation = c.execute("SELECT stance,reason,source_id,minute FROM chapter_one_relationships WHERE actor_id=? AND player_id=?", (actor,PLAYER)).fetchone()
    return {"memories":[{"id":r[0],"text":r[1],"source":r[2],"learned_minute":r[3]} for r in rows],
            "relationship":dict(zip(("stance","reason","source","learned_minute"),relation)) if relation else None,
            "limits":"These are my recollections and received reports, not verified world facts. I do not know the player's private notes or other characters' memories."}
