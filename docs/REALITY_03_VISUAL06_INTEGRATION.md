# Reality 0.3 sobre Visual 0.6 — integración experimental

Base: `experiment/visual-0.6-slender-character`. Esta rama conserva
sus modelos, shaders, escenas, personaje esbelto y ambientación visual.
No incorpora las escenas de Visual 0.5; Visual 0.6 solo tiene
APARTMENT, APARTMENT_DISTRICT y STATION en el enrutador actual.

## Qué se integra

- Reloj World Core autónomo: un tick de simulación cada 8 segundos,
  independientemente de las acciones humanas; el GET de estado no genera
  ninguna acción. Parámetros `LAIN_WORLD_CLOCK=1`,
  `LAIN_WORLD_TICK_SECONDS=8` y `LAIN_WORLD_TRACE=1`.
- El reloj no se detiene por filas de conversación OPEN abandonadas tras
  reiniciar. Se pausa solo si Godot envía la señal temporal de diálogo
  visible y además la conversación sigue realmente OPEN.
- Entidades GENERADAS con decisiones y energía preexistentes: las que no
  estén investigando ni viajando pueden realizar `WANDER` local;
  cada paso aceptado cambia un waypoint persistido junto con el evento.
  Godot consulta el servidor cada 1,5 segundos y anima el paso aceptado.
  Los actores conservan su ID para conversar; el jugador no puede ejecutar
  WANDER ni modificar la localización de un NPC.
- Visual 0.6 conserva íntegramente su arte. Se añade la representación
  de actores al apartamento (antes no había nodo Actors), además del
  movimiento en el distrito y en la estación.
- Las entidades con objetivos SEEK_CREATOR/EXPLORE pueden viajar entre
  localizaciones semánticas como ya hacían; la animación `WANDER`
  representa un circuito pequeño dentro de la escena, NO navegación por
  todo el mapa ni evasión de obstáculos. No se ha añadido planificación
  libre ni conversaciones espontáneas entre NPC.

## Probar sin tocar tu partida ni los cambios locales de Visual 0.6

1. Detén el servidor con Ctrl+C y cierra Godot. **No cambies de rama en
   `C:\Users\ENRIQUE\lain`**, donde conservas `world.db`, las
   modificaciones de importación y tu stash. Nunca ejecutes
   `git reset --hard`, `git clean` ni `git stash pop` para esta prueba.
2. Desde PowerShell en `C:\Users\ENRIQUE\lain` y con el servidor
   detenido, crea un worktree separado:

```powershell
cd C:\Users\ENRIQUE\lain
git fetch origin
git worktree add ..\lain-reality03-visual06 origin/experiment/reality-0.3-visual06-integration
Copy-Item .\world.db ..\lain-reality03-visual06\world.db
cd ..\lain-reality03-visual06
$env:LAIN_LLM_ENABLED="1"
$env:LAIN_LLM_MODEL="lain-qwen7b"
$env:LAIN_LLM_ENDPOINT="http://127.0.0.1:11434/v1/chat/completions"
$env:LAIN_REALITY_GENERATION="1"
$env:LAIN_WORLD_CLOCK="1"
$env:LAIN_WORLD_TICK_SECONDS="8"
$env:LAIN_WORLD_TRACE="1"
C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m uvicorn server.api:app --host 127.0.0.1 --port 8000
```

La copia de `world.db` se modifica solo en ese worktree de prueba; la
partida de `lain` permanece intacta. No lances simultáneamente dos
servidores contra la misma copia de `world.db`. No copies de vuelta la
base de pruebas sobre tu partida sin reconciliar los cambios.

3. En otro PowerShell ejecuta el juego DESDE el worktree NUEVO:
`cd C:\Users\ENRIQUE\lain-reality03-visual06; .\play.ps1`.
Si arrancas `play.ps1` desde la carpeta original, ejecutarás el cliente
Visual 0.6 **sin** el sondeo animado de Reality 0.3.

4. En la consola del servidor verifica
`WORLD CLOCK // STARTED interval=8s` y después
`WORLD CLOCK // TICK_MINUTE_...`. Mira una entidad presente en el
distrito o la estación sin abrir el diálogo. Verás un desplazamiento
corto cuando World Core acepte WANDER. Si está en un objetivo de
investigación, viajando a otro mapa o descansando, esa acción puede
tener prioridad y no habrá una caminata local en ese intervalo.

5. Si sigue sin moverse, con el juego abierto en una localización donde
ves una entidad, consulta solo lectura:

```powershell
$first = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/player/state"
Start-Sleep -Seconds 12
$second = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/player/state"
"Minuto: $($first.minute) -> $($second.minute)"
$first.visible_actors | Format-Table id,name,patrol_step
$second.visible_actors | Format-Table id,name,patrol_step
```

Si cambia `patrol_step` pero no cambia visualmente el modelo, el fallo
se encuentra entre snapshot, spawner y animación de Godot. Si cambia el
minuto pero no hay WANDER, revisar objetivos/energía/ubicaciones/eventos
del servidor, no los gráficos. Un `patrol_step` omitido equivale a 0.

## Pruebas

```powershell
C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m pytest -q
.\play.ps1 -ImportOnly
godot --headless --path client --script res://tools/test_reality03_visual.gd
godot --headless --path client --script res://tools/check_character06.gd
```

El script visual offline comprueba aparición y animación, ID de contacto
y retirada de entidades en las TRES escenas de Visual 0.6 sin consultar
ni cambiar `world.db`. La verificación visual final y sus posibles
problemas de colisión deben realizarse en el equipo del usuario.
La PR es experimental y no debe fusionarse antes de validarla.
