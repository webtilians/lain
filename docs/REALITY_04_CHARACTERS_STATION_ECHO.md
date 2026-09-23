# Reality 0.4 — personajes y «El pulso ausente» (primera situación jugable)

**Rama experimental:** `experiment/reality-0.4-character-sheets-station-echo`,
basada en `experiment/reality-0.3-visual06-integration`.
Se conservan los gráficos y el personaje de Visual 0.6, el reloj del
servidor, las siete entidades existentes, sus IDs, sus memorias y sus
localizaciones. No se hace merge en la rama gráfica ni se borra
`world.db`.

## Bucle jugable del caso 01

1. El jugador se acerca a la fuente física `NODE_07` en `STATION` y
   pulsa **E → Investigar la señal**. Solo la acción `INVESTIGATE`
   validada en World Core desbloquea el expediente; `OBSERVE`, un
   rumor o una petición desde otra localización no sirven. El rastro
   narrativo consiste en **un pulso ausente dentro de la secuencia**
   (no desactiva físicamente el nodo ni altera por sí solo la física
   del mundo existente).
2. En el siguiente contacto con el nodo, el jugador elige entre
   **difundir el rastro** a las entidades generadas que realmente se
   encuentran en la estación *en ese instante*, o **archivarlo**
   sin compartírselo. La elección se persiste y solo puede hacerse
   una vez en esta primera situación; no se ejecuta automáticamente.
3. Si lo difunde, cada destinatario recibe un testimonio identificado
   como `PLAYER_TESTIMONY`. Esto **no** le concede una percepción
   directa de NODE_07 ni conocimientos privados de otro personaje.
   En ciclos posteriores, un destinatario que permanezca en la
   estación ejecuta `RESPOND_TO_TRACE` una sola vez y deja una
   reacción propia de su rol en el expediente. Si el jugador
   archiva el rastro, nadie recibe el testimonio ni se generan
   respuestas por este caso.
4. En cualquier momento, pulsa **J** para consultar tu ficha,
   la de los PNJ presentes y el estado del expediente con las
   respuestas. El diario sigue disponible cuando abandonas
   la estación; las fichas de PNJ solo muestran las presencias
   actualmente visibles. Al marcharse, su información privada
   y ubicación remota no aparecen.

Los siete nombres existentes reciben una asignación *provisional y
persistente* derivada de sus nombres/premisas y objetivos ya guardados:
The Wired → ARCHIVIST, Node 07 → SIGNAL_KEEPER,
New Digital Presence → ORIGIN_SEEKER,
Monitor Entities → MONITOR, Node 07 Explorer → SCOUT,
Node 07 Inquiry → INQUIRER, New Entities Observation → WITNESS.
Una entidad de nombre diferente recibe una inferencia acotada
desde su premisa y objetivo original, con fallback OBSERVER.

Cada rol modifica la cadencia de `WANDER` y el contenido de su
respuesta al rastro. Una fase reproducible asociada al ID del actor
evita que las siete presencias recorran el mismo paso a la vez.
La investigación de una anomalía directamente percibida y la
recuperación de energía siguen teniendo prioridad. Las entidades
**no** adquieren planificación libre, personalidad psicológica
diagnosticada, habilidades de combate, ni conversaciones espontáneas
entre ellas: eso exige sistemas y pruebas adicionales.

## Contrato de las fichas

Persistente en `generated_actor_profiles`:
`actor_id` (clave), `role`, `assignment='ORIGIN_PROVISIONAL'`,
`assigned_minute`. Se crea la tabla con `CREATE TABLE IF NOT EXISTS`
y se migran los IDs antiguos con `INSERT OR IGNORE`. No se
reescriben `agents`, `generated_entities`, `agent_memory` ni sus
tablas de procedencia. Un rol no se asigna por una interpretación
inventada de los recuerdos secretos.

La respuesta `GET /api/v1/player/state` mantiene los campos
existentes y añade:

- `character_sheets.player`: ID, nombre, control exclusivamente
  humano, facción, ubicación, energía, número de nodos conocidos
  y estado de esta investigación.
- `character_sheets.visible_npcs`: solo NPC co-localizados,
  ID, nombre, rol provisional o rol preexistente, foco descriptivo
  y ubicación *observada*. **No** incluye energía, objetivos,
  recuerdos, creencias ni la ubicación de NPC remotos.
- `station_case`: estado UNSEEN / TRACE_FOUND / RESOLVED,
  resultado privado o compartido, cantidad de destinatarios
  de la difusión y reacciones de testigos que realmente
  recibieron el mensaje.

El jugador decide sus acciones manualmente. Su ficha no activa
ningún planificador sobre el usuario. El registro del caso es
server-side y se actualiza bajo el bloqueo de la API, igual que
las demás acciones.

## Probar preservando el Visual 0.6 original

**Detener antes Godot y Uvicorn.** No cambiar de rama en
`C:\Users\ENRIQUE\lain`, que contiene la partida original,
archivos locales modificados y el stash de texturas. La copia
`lain-reality03-visual06` también contiene su propio `world.db`.
En PowerShell, crea **otro worktree** desde la carpeta original:

```powershell
cd C:\Users\ENRIQUE\lain
git fetch origin
git worktree add --detach ..\lain-reality04 origin/experiment/reality-0.4-character-sheets-station-echo
Copy-Item ..\lain-reality03-visual06\world.db ..\lain-reality04\world.db
cd ..\lain-reality04
$env:LAIN_LLM_ENABLED="1"
$env:LAIN_LLM_MODEL="lain-qwen7b"
$env:LAIN_LLM_ENDPOINT="http://127.0.0.1:11434/v1/chat/completions"
$env:LAIN_REALITY_GENERATION="1"
$env:LAIN_WORLD_CLOCK="1"
$env:LAIN_WORLD_TICK_SECONDS="8"
$env:LAIN_WORLD_TRACE="1"
C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m uvicorn server.api:app --host 127.0.0.1 --port 8000
```

En **otra** consola: `cd C:\Users\ENRIQUE\lain-reality04; .\play.ps1`.
No abras dos instancias de servidor contra la misma base, ni
restaures la copia de pruebas encima de tu partida original.
Si la carpeta `lain-reality04` ya existe, comprueba el worktree
antes de reusar la ruta; no la sobrescribas.

Secuencia manual: pulsa **J** para comprobar fichas y siete
identidades conservadas; acércate a NODE_07 y usa **E → Investigar**;
abre J para comprobar TRACE_FOUND; vuelve al nodo, difunde o archiva;
espera varios ciclos autónomos y abre J para observar las respuestas.
En una partida de prueba diferente, elige la otra rama para comprobar
la consecuencia alternativa; no reinicies `world.db` a la fuerza.

## Pruebas reproducibles (no usan la partida)

```powershell
C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m pytest -q
.\play.ps1 -ImportOnly
godot --headless --path client --script res://tools/test_reality03_visual.gd
godot --headless --path client --script res://tools/test_reality04_journal.gd
godot --headless --path client --script res://tools/check_character06.gd
```

El escenario se encuentra en su primera versión jugable: un rastro,
una decisión persistente y reacciones acotadas. No se ha simulado
una desaparición física de la señal ni se pretende que los diálogos
generados tengan ya acceso contextual garantizado al expediente.
Las nuevas escenas, la visualización de roles y el flujo de Godot
requieren validación manual antes de fusionar la PR experimental.
