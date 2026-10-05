"""The watcher: real headlines become research calls on their own; the owner deletes the ones that are wrong."""
import json
import re
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from fastapi import HTTPException

from server import api
from server.world_core import admin, i18n, research, watch
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection
from server.world_core.player_view import build_player_snapshot
from tests.test_institute import OTHERS, PLAYER, lab, sh  # noqa: F401 (fixtures)
from tests.test_layer_three import game  # noqa: F401 (fixture)

ARXIV = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>http://arxiv.org/abs/2610.00001v1</id><title>Error-corrected logical qubits
  below threshold</title><link href="http://arxiv.org/abs/2610.00001v1" rel="alternate"/></entry>
</feed>"""
HN = json.dumps({"hits": [
    {"title": "QUIC is now half of the web's traffic", "url": "https://example.org/quic", "objectID": "1"},
    {"title": "Ask HN: what are you reading?", "url": None, "objectID": "2"},
    {"title": "A link that is not the web", "url": "ftp://example.org/file", "objectID": "3"},
]}).encode()
RFC = b"""<?xml version="1.0"?><rss><channel>
  <item><title>RFC 9999: Post-Quantum Key Exchange for TLS</title><link>https://www.rfc-editor.org/info/rfc9999</link></item>
</channel></rss>"""


def fetch(url):
    if "arxiv" in url:
        return ARXIV
    if "algolia" in url:
        return HN
    return RFC


def reply(**changes):
    data = {
        "headline": 1, "kind": "xor",
        "title_es": "QUIC, la web que ya no espera", "title_en": "QUIC, the web that no longer waits",
        "summary_es": "Medio internet viaja ya sobre QUIC. Ueda quiere entender por qué.",
        "summary_en": "Half of the internet already travels over QUIC. Ueda wants to understand why.",
        "article_es": "QUIC es un protocolo de transporte.\nCifra cada paquete y no espera a los que se pierden.",
        "article_en": "QUIC is a transport protocol.\nIt encrypts every packet and does not wait for the lost ones.",
        "framing_es": "Por debajo de cada paquete cifrado hay operaciones de bits como esta.",
        "framing_en": "Under every encrypted packet there are bit operations like this one.",
        "tech": "QUIC", "tech_text_es": "La Malla habla QUIC: paquetes cifrados que no esperan.",
        "tech_text_en": "The Mesh speaks QUIC: encrypted packets that do not wait.",
        "tech_line_es": "Los armarios ya no se cuelgan esperando a un paquete perdido.",
        "tech_line_en": "The cabinets no longer hang waiting for a lost packet.",
        "memory_es": "Ueda sabe que QUIC cifra cada paquete y no espera a los perdidos.",
    }
    data.update(changes)
    return "```json\n" + json.dumps(data, ensure_ascii=False) + "\n```"


@pytest.fixture
def watcher(lab, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "gemini-test")
    return lab


def publish(kind, centre="archivo"):
    items = watch.headlines(fetch)
    return research.publish(watch.proposal(reply(kind=kind), items, centre))


def solve(sim, statement, player=PLAYER):
    """Work an exercise out the way a player would: only from its statement and the terminal's own tools."""
    if "XOR" in statement:
        a, b = re.findall(r"[ab] = ([01]{8})", statement)
        return f"{int(a, 2) ^ int(b, 2):08b}"
    if "mod" in statement:
        g, x, p = map(int, re.search(r"(\d+)\^(\d+) mod (\d+)", statement).groups())
        return sh(sim, f"powmod {g} {x} {p}", player).split("= ")[-1]
    if "Hamming" in statement:
        bits = re.search(r": ([01]{7})\.", statement).group(1)
        groups = {1: (1, 3, 5, 7), 2: (2, 3, 6, 7), 4: (4, 5, 6, 7)}
        return str(sum(check for check, places in groups.items() if sum(int(bits[i - 1]) for i in places) % 2))
    if "sha256" in statement:
        path, line = re.search(r"sha256 (\S+) (\d+)", statement).groups()
        return sh(sim, f"sha256 {path} {line}", player).split()[0]
    word, path = re.search(r"grep (\S+) (\S+)\.", statement).groups()
    return str(len(sh(sim, f"grep {word} {path}", player).splitlines()))


def statements(sim, code, player=PLAYER, command="archivo"):
    shown = sh(sim, f"{command} ver {code}", player)
    return re.search(r"^2\. .*$", shown, re.M).group(0), re.search(r"^3\. .*$", shown, re.M).group(0)


def test_headlines_come_from_the_three_sources_and_only_web_links_stay():
    items = watch.headlines(fetch)
    titles = [item["title"] for item in items]
    assert titles[0] == "Error-corrected logical qubits below threshold", "titles are joined onto one line"
    assert "QUIC is now half of the web's traffic" in titles and "RFC 9999: Post-Quantum Key Exchange for TLS" in titles
    assert any(item["url"] == "https://news.ycombinator.com/item?id=2" for item in items)
    assert all(item["url"].startswith(("http://", "https://")) for item in items)

    def broken(url):
        raise OSError("no network")
    assert watch.headlines(broken) == []


def test_the_watcher_publishes_a_call_on_its_own(watcher):
    sim = watcher
    assert "Sin convocatorias abiertas" in sh(sim, "laboratorio")
    assert watch.due()
    asked = []
    call = watch.run(fetch, lambda messages: asked.append(messages) or reply())
    assert call["id"] == "IA-01" and call["source"]["url"] == "https://example.org/quic", "the emptiest centre first"
    system, prompt = asked[0][0]["content"], json.loads(asked[0][1]["content"])
    assert "Laboratorio de Inteligencias" in prompt["centre"] and "Takeshi Uno" in system and "evita sucesos" in system
    assert set(prompt["kinds"]) == set(research.GENERATORS) and "QB-01: El qubit" in prompt["already_studied"][0]
    assert prompt["recent_kinds"] == []
    assert watch.history(1)[0]["status"] == "PUBLISHED"
    portal = sh(sim, "laboratorio")
    assert portal.startswith("LABORATORIO DE INTELIGENCIAS · laboratorio.malla")
    assert "IA-01  QUIC, la web que ya no espera" in portal and "han terminado 0/3" in portal
    shown = sh(sim, "laboratorio ver IA-01")
    assert "Fuente: Hacker News · QUIC is now half of the web's traffic" in shown
    assert "Por debajo de cada paquete cifrado" in shown and "laboratorio entregar IA-01 <respuesta>" in shown
    assert "https://example.org/quic" in sh(sim, "laboratorio leer ia-01")
    mail = sh(sim, "cat ~/correo/ia-01.eml")
    assert mail.startswith("De: takeshi <takeshi@laboratorio.malla>") and "Empieza con laboratorio ver IA-01." in mail
    assert "QUIC es un protocolo" in sh(sim, "laboratorio leer ia-01")
    assert "IA-01" not in sh(sim, "archivo"), "each centre lists its own calls"
    assert not watch.due(), "one call every few days"
    later = research.last_generated() + watch.days() * 86400 + 1
    assert watch.due(later)
    assert watch.maybe_run() is None


def test_every_exercise_is_solved_with_the_terminal_and_the_players_own_numbers(watcher):
    sim = watcher
    for kind in research.GENERATORS:
        call = publish(kind)
        code = call["id"]
        sh(sim, f"archivo leer {code.lower()}")
        practice, demo = statements(sim, code)
        mine = solve(sim, practice)
        assert "No es eso" in sh(sim, f"archivo entregar {code} 99999999")
        done = sh(sim, f"archivo entregar {code} {mine}")
        assert f"Parte 2 de {code}" in done, (kind, practice, done)
        _practice, demo = statements(sim, code)
        finished = sh(sim, f"archivo entregar {code} {solve(sim, demo)}")
        assert f"CONVOCATORIA {code} COMPLETADA · Archivo de Protocolos" in finished, (kind, demo, finished)
        with get_connection() as c:
            mine, theirs = ((lambda ex: (ex["statement"], ex["files"]))(
                research.exercise(c, player, research.calls(c)[code], "prueba")) for player in (PLAYER, OTHERS[0]))
        assert mine != theirs, "every player gets their own numbers"


def test_a_watcher_call_changes_the_malla_for_everyone_at_three(watcher):
    sim = watcher
    call = publish("powmod", centre="laboratorio")
    code = call["id"]
    assert code == "IA-01"
    for player in [PLAYER] + OTHERS[:2]:
        sh(sim, f"lab read {code}", player)
        for part in (0, 1):
            statement = statements(sim, code, player, "laboratorio")[part]
            last = sh(sim, f"laboratorio entregar {code} {solve(sim, statement, player)}", player)
    assert "LA MALLA APRENDE · QUIC entra en la Malla para todos." in last
    assert "Los armarios ya no se cuelgan" in last
    assert "QUIC (desde el minuto" in sh(sim, "archivo") and "QUIC ya está en la Malla" in sh(sim, "laboratorio")
    snapshot = build_player_snapshot(PLAYER)["research"]
    assert {"id": "ia-01", "name": "QUIC", "about": "La Malla habla QUIC: paquetes cifrados que no esperan.",
            "next": "Los armarios ya no se cuelgan esperando a un paquete perdido."} in snapshot["unlocked"]
    assert snapshot["completed"][0]["centre"] == "Laboratorio de Inteligencias"
    director = AgentContextBuilder().build(research.CENTRES["laboratorio"]["director"])["chapter_memory"]["memories"]
    assert any("Ueda sabe que QUIC" in memory["text"] for memory in director)
    assert any("QUIC ya está en la Malla" in memory["text"] for memory in director)


def test_bad_answers_from_the_ai_publish_nothing(watcher):
    items = watch.headlines(fetch)
    for broken, centre, reason in ((reply(), "cocina", "UNKNOWN_CENTRE"), (reply(kind="test"), "archivo", "UNKNOWN_KIND"),
                                   (reply(headline=99), "archivo", "UNKNOWN_HEADLINE"),
                                   (reply(title_en=""), "archivo", "EMPTY_FIELD"), ("no sé", "archivo", "NO_JSON")):
        with pytest.raises(ValueError, match=reason):
            watch.proposal(broken, items, centre)
    assert watch.proposal(reply(centre="instituto"), items, "archivo")["centre"] == "archivo", "the code picks the centre"
    long = watch.proposal(reply(article_es="x" * 5000), items, "archivo")
    assert len(long["article"]["es"]) == watch.LIMITS["article"]
    assert watch.run(fetch, lambda messages: reply(kind="test")) is None
    assert watch.history(1)[0]["status"] == "FAILED" and "UNKNOWN_KIND" in watch.history(1)[0]["detail"]

    def down(messages):
        raise HTTPError("https://ai.example", 503, "busy", {}, None)
    assert watch.run(fetch, down) is None and watch.history(1)[0]["detail"] == "IA HTTP 503"
    assert watch.run(lambda url: b"", reply) is None and "sin titulares" in watch.history(1)[0]["detail"]
    assert research.last_generated() is None
    failed = watch.history(1)[0]["at"]
    assert not watch.due(failed + 60) and watch.due(failed + watch.RETRY + 1), "a failure tries again in hours, not days"


def test_without_the_ai_the_watcher_waits(lab, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LAIN_LLM_ENABLED", "0")
    assert watch.maybe_run() is None
    assert watch.run(fetch, reply) is None and watch.history(1)[0]["status"] == "SKIPPED"


def tunnel(headers=None):
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers=headers or {})


def test_the_owner_sees_and_deletes_watcher_calls_from_the_panel(watcher, monkeypatch):
    sim = watcher
    call = publish("contar")
    code = call["id"]
    assert sh(sim, f"cat /malla/archivo/{code.lower()}/prueba.txt").startswith("01 ")
    panel = admin.overview()["research"]
    assert panel["calls"][0]["id"] == code and panel["calls"][0]["status"] == "open" and panel["ai"]
    assert "Convocatorias del vigía" in admin.PAGE
    with pytest.raises(HTTPException):
        api.admin_delete_research(code, tunnel())
    with pytest.raises(HTTPException):
        api.admin_delete_research(code, tunnel({"x-lain-admin": "1", "origin": "https://evil.example"}))
    with pytest.raises(HTTPException):
        api.admin_delete_research(code, tunnel({"x-lain-admin": "1", "x-forwarded-for": "203.0.113.9"}))
    assert api.admin_delete_research(code.lower(), tunnel({"x-lain-admin": "1"})) == {"deleted": code}
    with pytest.raises(HTTPException):
        api.admin_delete_research(code, tunnel({"x-lain-admin": "1"}))
    assert code not in sh(sim, "archivo") and "No hay ninguna convocatoria" in sh(sim, f"archivo ver {code}")
    assert code.lower() not in sh(sim, "ls /malla/archivo")
    assert admin.overview()["research"]["calls"][0]["status"] == "deleted"
    assert publish("xor")["id"] == "PR-02", "a deleted code is never reused"
    ran = []
    monkeypatch.setattr(watch, "run", lambda: ran.append(1))
    assert api.admin_watch_now(tunnel({"x-lain-admin": "1"})) == {"started": True}
    with pytest.raises(HTTPException):
        api.admin_watch_now(tunnel())


def test_a_deleted_call_takes_its_technology_away(watcher):
    sim = watcher
    code = publish("xor")["id"]
    for player in [PLAYER] + OTHERS[:2]:
        sh(sim, f"archivo leer {code}", player)
        for part in (0, 1):
            sh(sim, f"archivo entregar {code} {solve(sim, statements(sim, code, player)[part], player)}", player)
    assert [item["id"] for item in build_player_snapshot(PLAYER)["research"]["unlocked"]] == [code.lower()]
    research.delete(code)
    snapshot = build_player_snapshot(PLAYER)["research"]
    assert snapshot["unlocked"] == [] and snapshot["completed"] == []
    assert "nada nuevo todavía" in sh(sim, "archivo")
    nora = AgentContextBuilder().build("AGENT_NORA").get("chapter_memory") or {"memories": []}
    assert not any("QUIC" in memory["text"] for memory in nora["memories"])


def test_watcher_calls_in_english(watcher):
    sim = watcher
    codes = [publish(kind)["id"] for kind in research.GENERATORS]
    spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|tus|está|hay|desde|canal|entrega|"
                         r"líneas|cuántas)\b", re.I)
    token = i18n.set_language("en")
    try:
        texts = [sh(sim, "archive"), sh(sim, "archive registry"), sh(sim, "lab"), sh(sim, "archive read nothing"),
                 sh(sim, f"cat ~/correo/{codes[0].lower()}.eml"),
                 sh(sim, "man archive"), sh(sim, "archive submit"), sh(sim, "lab submit")]
        for code in codes:
            texts += [sh(sim, f"archive show {code}"), sh(sim, f"archive read {code}"),
                      sh(sim, f"archive submit {code} 0")]
            practice, _demo = statements(sim, code, command="archive")
            texts.append(sh(sim, f"archive submit {code} {solve(sim, practice)}"))
            texts.append(sh(sim, f"archive submit {code}"))
        for text in texts:
            lines = [line for line in text.splitlines() if spanish.search(line)
                     and not re.search(r"archivo\.malla|laboratorio\.malla|/malla/", line)]
            assert not lines, lines[:3]
        assert "QUIC, the web that no longer waits" in sh(sim, "archive")
    finally:
        i18n.reset(token)


def test_codes_can_be_written_loosely_and_qb01_keeps_its_channel_form(watcher):
    sim = watcher
    assert publish("xor", centre="instituto")["id"] == "QB-02", "the institute's watcher calls follow QB-01"
    assert publish("xor", centre="laboratorio")["id"] == "IA-01"
    assert sh(sim, "laboratorio ver ia1").startswith("IA-01 · ") and sh(sim, "lab ver IA-01").startswith("IA-01 · ")
    assert "QUIC es un protocolo" in sh(sim, "laboratorio leer ia01")
    assert "Primero saca la clave: bb84 medir a" in sh(sim, "instituto entregar a 0110"), "a channel means QB-01"
    assert "No es eso" in sh(sim, "instituto entregar 0110"), "otherwise the newest call still open"
    assert "QB-02  QUIC" in sh(sim, "instituto") and "QB-01  El qubit" in sh(sim, "instituto")


def test_every_centre_gets_its_turn_and_exercises_vary(watcher):
    assert watch.target_centre() == "laboratorio", "the institute already has QB-01"
    publish("xor", centre="laboratorio")
    assert watch.target_centre() == "archivo"
    publish("hamming", centre="archivo")
    assert watch.target_centre() == "instituto", "a tie goes to the first centre"
    assert research.recent_kinds() == ["hamming", "xor"]
    research.delete("PR-01")
    assert watch.target_centre() == "archivo", "a deleted call leaves room in its centre"

