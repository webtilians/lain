# LAIN — Revisión de Reality 0.4 y prólogo 0.1

**Estado:** rama experimental `experiment/prologue-0.1-school-ryoko-terminal`,
basada en `experiment/reality-0.4-character-sheets-station-echo`. Se ha
revisado el código publicado de esta rama: NO se conocen los cambios locales
sin subir a GitHub en el ordenador del desarrollador. No se ha fusionado
ninguna rama ni se ha modificado el `world.db` de la partida original.

## Revisión de fichas, roles y dinámica anterior

- `character_sheets.py` asigna siete roles **provisionales y persistentes**
  derivados del nombre/premisa/origen de cada entidad. Los IDs y memorias
  siguen siendo los del juego existente. El rol modifica actualmente la
  cadencia local de movimiento y la reacción al caso de NODE_07; **todavía
  no** son personalidades profundas ni planificadores autónomos distintos.
- El diario **J** muestra la ficha del jugador y solo las fichas de NPC
  co-localizados; no expone recuerdos privados, ubicaciones remotas ni
  objetivos secretos. Las fichas del profesor y de Ryoko son deliberadamente
  de tipo `AUTHORED_PROLOGUE`: se trata de los PNJ narrativos de esta
  introducción, con conversación pautada, no de agentes generados con
  memorias inventadas por IA.
- «El pulso ausente» sirve como primer ciclo de investigación y consecuencia,
  con una única elección persistente y respuestas por rol, pero actualmente
  el jugador podía acceder a la estación antes de tener una razón narrativa
  para entrar en la Wired. Además, la terminal antigua incluía un botón
  CONNECT directo. El prólogo hace que una partida NUEVA empiece realmente
  fuera de la red y que la conexión dependa de lo aprendido.

## Primera fase del juego

1. **Apartamento (offline).** Pantalla y HUD indican que el sistema local
   está activo pero la Wired no. El diario **J** te manda a la escuela. Puedes
   explorar el PC local, que abre una consola de aspecto DOS y únicamente
   ofrece comandos locales de orientación. No revela la sintaxis Telnet
   antes de que hables con Ryoko.
2. **Barrio → Escuela → Aula de informática.** Dos entradas físicas y
   señalizadas se añaden al barrio conservando sus gráficos Visual 0.6.
   La escuela es un pasillo 3D visitable; el aula tiene mesas, ordenadores
   CRT y el **profesor**. Al hablar con él, te dice que solo Ryoko, un
   antiguo alumno, parecía conocer la Wired; no sabe dónde está ahora.
   La pista y la progresión quedan registradas en el servidor.
3. **Barrio → Discoteca.** La discoteca es otro escenario 3D visitable.
   Ryoko no revela información si todavía no has hablado con el profesor.
   Después, te da tres datos: el protocolo real **TELNET**, el nombre del
   servidor ficticio **WIRED** y su puerto **23**. No proporciona la
   orden completa: invita a investigar en Internet o preguntar a un asistente
   de programación por la sintaxis de Telnet.
4. **Vuelta al apartamento.** En su ordenador aparece `C:\\>`.
   Puedes escribir `HELP`, `DIR`, `CLS` y `VER` dentro de una
   interfaz DOS **simulada**, pero solo la gramática real del comando
   Telnet con el servidor y puerto correctos resuelve el acertijo.
   World Core analiza texto acotado; no ejecuta comandos del sistema
   operativo, no inicia conexiones telnet reales y no evalúa Python.
   Intentos de saltarse al profesor, Ryoko o la localización del
   ordenador quedan denegados por el servidor.
5. **Primera conexión.** La orden correcta guarda `CONNECTED`,
   acepta la carta inicial de la Wired, concede la primera pista
   habitual del juego y permite viajar a la estación. El prólogo acaba:
   arranca el contenido preexistente de Reality 0.4, sus fichas, sus
   personajes, su memoria y «El pulso ausente».

El arranque no debe spoilear la estación ni mostrar la primera carta de
la Wired antes de superar el prólogo. Los datos se exponen únicamente
en la primera conexión. La progresión se conserva al reiniciar.
`player_prologue` se crea como tabla lateral, sin sobrescribir las
entidades ni sus memorias. Las partidas anteriores (con o sin siete
entidades creadas) **no** entran en el prólogo retroactivamente.

**Alcance visual:** escuela, aula y discoteca usan una primera maqueta
3D funcional con materiales sobrios, pasillos, puertas y personajes
visibles. El prólogo está diseñado para poder probar ya sus mecánicas;
no contiene aún arte final, animaciones narrativas, música, horarios,
multitudes ni voces. No confundas esta primera integración con una
secuencia cinematográfica acabada.

## Cómo probar sin tocar ninguna partida existente

1. Detén Godot y Uvicorn. Conserva intactos
   `C:\Users\ENRIQUE\lain\world.db` y
   `C:\Users\ENRIQUE\lain-reality04\world.db`. Nunca uses
   `git reset --hard`, `git clean` ni `git stash pop` para esta
   prueba. La partida original y los cuatro archivos guardados en el
   stash de Visual 0.6 siguen siendo independientes.
2. Crea un **worktree nuevo**, sin copiar ninguna base de datos:

```powershell
cd C:\Users\ENRIQUE\lain
git fetch origin
git worktree add --detach ..\lain-prologue01 origin/experiment/prologue-0.1-school-ryoko-terminal
cd ..\lain-prologue01
```

3. Inicia el servidor **desde esa carpeta** con una base de datos
   separada (`prologue-newgame.db`); las variables se deben establecer
   ANTES de arrancar Python:

```powershell
$env:LAIN_WORLD_DB="prologue-newgame.db"
$env:LAIN_PROLOGUE_ENABLED="1"
$env:LAIN_LLM_ENABLED="1"
$env:LAIN_LLM_MODEL="lain-qwen7b"
$env:LAIN_LLM_ENDPOINT="http://127.0.0.1:11434/v1/chat/completions"
$env:LAIN_REALITY_GENERATION="1"
$env:LAIN_WORLD_CLOCK="1"
$env:LAIN_WORLD_TICK_SECONDS="8"
$env:LAIN_WORLD_TRACE="1"
C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m uvicorn server.api:app --host 127.0.0.1 --port 8000
```

4. En otra consola: `cd C:\Users\ENRIQUE\lain-prologue01; .\play.ps1`.
   La conexión HTTP del juego con el servidor local es distinta de
   la conexión narrativa del personaje a la Wired. Espera ver la
   ubicación `APARTMENT`, `prologue.stage=FIND_TEACHER` y
   `wired.connected=false` al iniciar la partida nueva.

5. Usa **WASD** para caminar, **E** para interactuar, **J** para tu
   ficha/objetivo y **ESC** para cerrar el diálogo/terminal. Ve a la
   escuela, entra al aula, habla con el profesor, encuentra a Ryoko en
   la discoteca y regresa al PC. Investiga la sintaxis de Telnet fuera
   del juego, introduce la orden en la terminal y vuelve al mundo
   existente. Comprueba que la partida reanudada mantiene el progreso.

**No elimines `prologue-newgame.db` para reintentar el acertijo**.
Si necesitas una segunda prueba desde cero, crea un worktree o un archivo
nuevo con otro nombre, sin reemplazar la partida ya iniciada.

## Comprobaciones automáticas

```powershell
C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m pytest -q
godot --headless --path client --editor --import --quit
godot --headless --path client --script res://tools/test_prologue01_visual.gd
```

Las pruebas de Python emplean bases de datos temporales y cubren:
la creación del prólogo solo para una partida virgen, el bloqueo de
la estación y del viejo CONNECT, la localización real del profesor y
de Ryoko, el orden de los testimonios, el comando de red validado sin
ejecución del SO, el reinicio, el progreso idempotente y el
mantenimiento de partidas antiguas. El smoke test de Godot verifica
importación, escenas, puertas, personajes y consola sin conectarse
al servidor. No sustituye la prueba interactiva en Windows.

## Próximos pasos de diseño (fuera del alcance de este commit)

- Ambientación de la escuela/discoteca con arte 3D propio, cartel
  diegético y sonidos; siluetas secundarias y expresiones del profesor.
- Introducción breve en el apartamento y una reacción audiovisual al
  primer enlace; la sorpresa debe manifestarse en el entorno físico,
  no limitarse a una línea de consola.
- Evolución real de los roles de PNJ: intereses y comportamientos
  distintos que afecten a nuevas misiones, sin atribuirles información
  que no hayan adquirido legítimamente.
