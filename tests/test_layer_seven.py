"""Capa 07 · Aplicación: DNS, HTTP virtual hosts, Basic auth and the three endings, from game output."""
import base64
import re

import pytest

from server.world_core import i18n, layer_seven
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.database import get_connection
from tests.test_chapter_one import move
from tests.test_layer_five import archive  # noqa: F401 (fixture)
from tests.test_layer_four import PLAYER, connected, layer_three_game, out  # noqa: F401 (fixtures)
from tests.test_layer_six import SPOOL, VIDEO, club, read  # noqa: F401 (fixture)


def finish_layer_six(sim, word):
    faces = read(sim)
    authentic = next(letter for letter, face in faces.items() if face["key"] == word and face["signed"])
    out(sim, f"xor {SPOOL}/{authentic}.pkt {word}", host=VIDEO)
    assert "CAPA 06 COMPLETADA" in out(sim, "keep", host=VIDEO)


@pytest.fixture
def node(monkeypatch, club):
    monkeypatch.setenv("LAIN_LAYER_SEVEN", "1")
    layer_seven.initialize_layer_seven()
    sim, word = club
    assert layer_seven.layer_snapshot(PLAYER) == {"active": False}
    finish_layer_six(sim, word)
    move(sim, "APARTMENT")
    name = re.match(r"(.+?) · ", out(sim, "whoami")).group(1)
    return sim, word, name


def address(sim):
    """The node's real address: ask every nameserver of the zone until one knows the name."""
    servers = re.findall(r"IN\tNS\t(\S+)\.", out(sim, "dig NS indara"))
    for server in servers:
        found = re.search(r"nodo07\.indara\.\t\d+\tIN\tA\t(\S+)", out(sim, f"dig @{server} nodo07.indara"))
        if found:
            return found.group(1)
    raise AssertionError("no nameserver knows nodo07.indara")


def curl(sim, request):
    return out(sim, "curl " + request)


def inside(sim, word, name):
    ip = address(sim)
    auth = f'--resolve nodo07.indara:80:{ip} -u "{name}:{word}"'
    listing = curl(sim, f"{auth} http://nodo07.indara/sesiones")
    s0 = re.search(r"(s0-[0-9a-f]{6})", listing).group(1)
    s1 = re.search(r"(s1-[0-9a-f]{6})", listing).group(1)
    return auth, s0, s1


def test_starts_after_capa_06_and_the_name_does_not_resolve(node):
    sim, word, name = node
    snapshot = layer_seven.layer_snapshot(PLAYER)
    assert snapshot["active"] and snapshot["fragments"] == 4 and "NODO_07" in snapshot["goal"]
    assert "servidor de nombres" in out(sim, "cat ~/correo/nodo07.eml") and "10.0.0.53" in out(sim, "cat /etc/resolv.conf")
    assert "NXDOMAIN" in out(sim, "dig nodo07.indara") and "ns.noema.indara" in out(sim, "dig nodo07.indara")
    assert len(re.findall(r"IN\tNS", out(sim, "dig NS indara"))) == 3
    assert "Could not resolve host: nodo07.indara" in curl(sim, "http://nodo07.indara/")
    assert "Host" in out(sim, "man host") and "base64" in out(sim, "man auth") and "421" in out(sim, "man http")


def test_the_networks_former_name_still_answers(node):
    sim, word, name = node
    # Whoever learnt the names before the network became Indara is not stuck halfway.
    assert len(re.findall(r"IN	NS", out(sim, "dig NS malla"))) == 3
    ip = address(sim)
    assert re.search(r"nodo07\.indara\.	\d+	IN	A", out(sim, "dig @ns.circulos.malla nodo07.malla"))
    page = curl(sim, f'--resolve nodo07.malla:80:{ip} -u "{name}:{word}" http://nodo07.malla/sesiones')
    assert re.search(r"s0-[0-9a-f]{6}", page), page


def test_dns_virtual_host_and_basic_auth_lead_inside_then_persist(node):
    sim, word, name = node
    ip = address(sim)
    assert "421 Misdirected Request" in curl(sim, f"-i http://{ip}/")
    denied = curl(sim, f'-i -H "Host: nodo07.indara" http://{ip}/')
    assert "401 Unauthorized" in denied and 'WWW-Authenticate: Basic realm="NODO_07"' in denied
    assert "401" in curl(sim, f'-i -H "Host: nodo07.indara" -u "{name}:nada" http://{ip}/')
    verbose = curl(sim, f'-v -H "Host: nodo07.indara" -u "{name}:{word}" http://{ip}/')
    assert f"> Authorization: Basic {base64.b64encode(f'{name}:{word}'.encode()).decode()}" in verbose
    assert "< HTTP/1.1 200 OK" in verbose and "PUT    /registro/<nombre>" in verbose
    auth = f'--resolve nodo07.indara:80:{ip} -u "{name}:{word}"'
    assert "Primero entra" in curl(sim, f"-X PUT {auth} http://nodo07.indara/registro/{name}")
    listing = curl(sim, f"{auth} http://nodo07.indara/sesiones")
    s0, s1 = re.search(r"(s0-\w+)", listing).group(1), re.search(r"(s1-\w+)", listing).group(1)
    assert "sesiones sin nombre" in listing and "Estás en NODO_07" in layer_seven.layer_snapshot(PLAYER)["goal"]
    assert "¿Quieres quedarte?" in curl(sim, f"{auth} http://nodo07.indara/sesiones/{s0}")
    assert "403" in curl(sim, f"-i -X PUT {auth} http://nodo07.indara/registro/Otra%20persona")
    ending = curl(sim, f"-i -X PUT {auth} http://nodo07.indara/registro/{name}")
    assert "201 Created" in ending and "Fragmentos recuperados: 5/7" in ending
    assert re.search(rf"0001 \|\s+\d+ \| prev 00000000 \| [0-9a-f]{{8}} \| {name}", curl(sim, f"{auth} http://nodo07.indara/registro"))
    assert "409" in curl(sim, f"-i -X DELETE {auth} http://nodo07.indara/sesiones/{s1}")
    assert "persistente" in out(sim, "whoami") and layer_seven.layer_snapshot(PLAYER)["fragments"] == 5
    nora = AgentContextBuilder().build("AGENT_NORA")["chapter_memory"]["memories"]
    assert any("registro de NODO_07" in memory["text"] for memory in nora)


def test_kagami_answers_the_same_name_with_a_copy_and_replicates(node):
    sim, word, name = node
    mirror = out(sim, "dig @ns.kagami.indara nodo07.indara")
    assert "CNAME\tespejo.kagami.indara." in mirror
    mirror_ip = re.search(r"espejo\.kagami\.indara\.\t\d+\tIN\tA\t(\S+)", mirror).group(1)
    assert "copia de KAGAMI" in curl(sim, f"--resolve nodo07.indara:80:{mirror_ip} http://nodo07.indara/")
    assert "Primero entra" in curl(sim, "-X POST http://espejo.kagami.indara/replicas")
    inside(sim, word, name)
    assert "405" in curl(sim, "-i http://espejo.kagami.indara/replicas")
    assert "Copia restaurada" in curl(sim, "-X POST http://espejo.kagami.indara/replicas")
    assert out(sim, "cat ~/diario").startswith("Copia restaurada · minuto")
    assert "Me guardé lo que decía su último paquete." in out(sim, "cat ~/diario")
    assert "copia restaurada" in out(sim, "whoami")
    assert "Ya elegiste" in curl(sim, "-X POST http://espejo.kagami.indara/replicas")


def test_disconnecting_leaves_an_echo_other_players_find(node):
    sim, word, name = node
    with get_connection() as c:
        c.execute("INSERT INTO agents(id,name,faction,location,goal,energy,controller_type) "
                  "VALUES('PLAYER_OTHER','Ana','UNALIGNED','APARTMENT','UNKNOWN',1,'HUMAN')")
        c.execute("INSERT INTO layer_three(player_id, started_minute, connection_minute, decision) "
                  "VALUES('PLAYER_OTHER', 1, 1, 'FORWARD')")
        c.execute("INSERT INTO layer_seven(player_id, started_minute, language, previous, inside, decision) "
                  "VALUES('PLAYER_OTHER', 1, 'es', 'KEEP', 1, 'DISCONNECT')")
    auth, s0, s1 = inside(sim, word, name)
    assert "Ana · eco" in curl(sim, f"{auth} http://nodo07.indara/sesiones")
    echo = curl(sim, f"{auth} http://nodo07.indara/ecos/ana")
    assert echo.startswith("Eco de ana:") and "Reenvié el paquete" in echo and "alguien me recibe" in echo
    assert "403" in curl(sim, f"-i -X DELETE {auth} http://nodo07.indara/sesiones/{s0}")
    assert "descansa" in curl(sim, f"-X DELETE {auth} http://nodo07.indara/sesiones/{s1}")
    assert s0 not in curl(sim, f"{auth} http://nodo07.indara/sesiones")
    assert "Me guardé" in curl(sim, f"{auth} http://nodo07.indara/ecos/{name}") and "eco" in out(sim, "whoami")
    k = AgentContextBuilder().build("AGENT_K")["chapter_memory"]["memories"]
    assert any("Una sesión menos" in memory["text"] for memory in k)


def test_bad_requests_are_explained(node):
    sim, word, name = node
    ip = address(sim)
    assert 'Protocol "https" not supported' in curl(sim, f"https://{ip}/")
    assert "opción desconocida" in curl(sim, f"--compressed http://{ip}/") and "Uso" in curl(sim, "-i")
    assert "Connection refused" in curl(sim, f"http://{ip}:8080/") and "Connection refused" in curl(sim, "http://10.1.2.3/")
    assert "timed out" in out(sim, "dig @ns.nadie.indara nodo07.indara") and "Uso" in out(sim, "dig")
    auth = f'--resolve nodo07.indara:80:{ip} -u "{name}:{word}"'
    assert "405" in curl(sim, f"-i -X PATCH {auth} http://nodo07.indara/sesiones")
    assert "404" in curl(sim, f"-i {auth} http://nodo07.indara/nada")


def test_each_player_gets_their_own_addresses():
    stories = [layer_seven.Story(f"PLAYER_{n:032x}", "Ana", "faro") for n in range(100)]
    assert len({s.node_ip for s in stories}) > 90 and len({s.s0 for s in stories}) == 100
    assert all(s.node_ip != s.mirror_ip and s.s0[3:] != s.s1[3:] for s in stories)


def test_english_player_reads_the_layer_in_english(node):
    sim, word, name = node
    token = i18n.set_language("en")
    try:
        ip = address(sim)
        auth = f'--resolve nodo07.indara:80:{ip} -u "{name}:{word}"'
        spanish = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|está|hay|sesiones|nombre)\b", re.I)
        listing = curl(sim, f"{auth} http://nodo07.indara/sesiones")
        s0 = re.search(r"(s0-\w+)", listing).group(1)
        for command in ("help", "man dns", "man dig", "man http", "man curl", "man host", "man auth",
                        "cat ~/correo/nodo07.eml", "cat /etc/resolv.conf", "dig TXT wired", "dig", "curl -i",
                        f"curl -i http://{ip}/", f'curl -i -H "Host: nodo07.indara" http://{ip}/',
                        f"curl -i {auth} http://nodo07.indara/", f"curl {auth} http://nodo07.indara/sesiones",
                        f"curl -i {auth} http://nodo07.indara/sesiones/{s0}", f"curl -i {auth} http://nodo07.indara/registro",
                        f"curl -i -X PATCH {auth} http://nodo07.indara/", "curl http://espejo.kagami.indara/",
                        f"curl -i -X PUT {auth} http://nodo07.indara/registro/{name}", "whoami"):
            text = out(sim, command).replace("/sesiones", "").replace("/registro", "")
            lines = [line for line in text.splitlines() if spanish.search(line)]
            assert not lines, (command, lines[:3])
        snapshot = i18n.payload(layer_seven.layer_snapshot(PLAYER))
        assert not spanish.search(snapshot["goal"] + snapshot["mail"]["body"] + snapshot["title"] + snapshot["mail"]["subject"])
    finally:
        i18n.reset(token)
