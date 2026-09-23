# Reality 0.3 — mundo autonomo y movimiento observable

Rama experimental: `experiment/reality-0.3-autonomous-world`, creada desde
`experiment/visual-0.5-illustrated-reality`. No sustituye ni fusiona los
cambios graficos ya presentes en Visual 0.5. No borrar `world.db`: la
tabla `generated_actor_motion` se añade de forma compatible y comienza en
el punto 0 para las entidades existentes.

## Contrato del hito

- El servidor FastAPI inicia un **unico reloj** al arrancar. Cada 8 segundos
  reales (configurable) llama a World Core `Simulation.tick()` con bloqueo
  de las mutaciones del jugador: el mundo avanza sin que el jugador camine,
  converse, pulse REST o haga peticiones de movimiento. Leer `GET /state`
  **no cambia el mundo**, y salir de Godot no crea un segundo reloj.
- Si existe una conversación del jugador en estado `OPEN`, el reloj
  se pausa para que la entidad no salga de escena durante un mensaje del LLM.
  Al pausarla o cerrarla, reanuda en el siguiente intervalo, sin ticks
  acumulados durante la conversación. Las acciones del jugador siguen
  ejecutándose al instante dentro de World Core.
- Las entidades generadas mantienen sus objetivos iniciales
  `OBSERVE_WORLD`, `SEEK_CREATOR` y `EXPLORE`; una percepción propia
  válida de anomalía puede seguir imponiendo temporalmente la investigación.
  En caso de que no deban viajar entre localizaciones o investigar,
  pueden decidir `WANDER`, una acción de movimiento **local** que consume
  energía (0.02), registra un evento y avanza uno de cuatro waypoints
  persistentes. Descansan automáticamente al bajar de 0.25 de energía.
  Ningún mensaje LLM ni el cliente Godot puede inventar esa acción o
  modificar localizaciones; `WANDER` solo se valida para agentes de tipo
  `GENERATED`, con destino igual a su ubicación real actual.
- El snapshot del jugador revela `patrol_step` exclusivamente para una
  entidad presente en la misma localización, sin incluir sus objetivos,
  memorias, creencias o paradero remoto. Se conserva el formato anterior
  para K/Nora y entidades todavía en waypoint cero.
- Godot consulta `GET /api/v1/player/state` cada 1.5 segundos sin ejecutar
  `player/step`. Al llegar un waypoint nuevo, interpola el modelo
  durante 1.8 segundos en un pequeño circuito cerca de la baliza
  `ENTITY_ANCHOR`. El identificador de la entidad usado para hablar
  no cambia; desaparece si World Core informa que ya no está presente.

Este hito valida autonomía **acotada**, no planificación libre general:
`WANDER` usa cuatro pasos locales próximos al punto de aparición, no una
ruta de navegación con obstáculos ni un sistema de pathfinding por toda
la escena. Los cambios entre escenas siguen usando el `MOVE` semántico
preexistente; no se representan como una caminata continua entre mapas.

## Prueba en Windows

1. Hacer copia de `world.db` fuera del repositorio. Detener Godot y
   Uvicorn con Ctrl+C antes de cambiar de rama. Si tienes modificaciones
   gráficas locales sin confirmar, hacer antes un commit en tu rama o
   guardarlas para no sobrescribirlas.
2. Desde PowerShell en la carpeta del repositorio:

```powershell
cd C:\Users\ENRIQUE\lain
git fetch origin
git switch --track origin/experiment/reality-0.3-autonomous-world
# Si ya existe la rama local: git switch experiment/reality-0.3-autonomous-world
# y a continuacion: git pull --ff-only
$env:LAIN_LLM_ENABLED="1"
$env:LAIN_LLM_MODEL="lain-qwen7b"
$env:LAIN_LLM_ENDPOINT="http://127.0.0.1:11434/v1/chat/completions"
$env:LAIN_LLM_TIMEOUT="45"
$env:LAIN_REALITY_GENERATION="1"
$env:LAIN_REALITY_TIMEOUT="45"
$env:LAIN_WORLD_CLOCK="1"
$env:LAIN_WORLD_TICK_SECONDS="8"
.\.venv\Scripts\python.exe -m uvicorn server.api:app --host 127.0.0.1 --port 8000
```

3. En otro PowerShell, en la misma rama y con Godot disponible, ejecutar
   `.\play.ps1`. Quedarse quieto junto a una entidad existente. Un
   `OBSERVE_WORLD` debería caminar por un circuito pequeño aproximadamente
   cada 8 segundos, sin pulsar controles. Si la entidad decide investigar
   una señal o viajar hacia K/Nora, su objetivo puede tener prioridad:
   desaparecerá del escenario al cambiar de ubicación; en la Wired
   seguirá siendo reconocible según el estado de conexión.
4. Hablar con ella: no debe escapar a mitad del diálogo. Cerrar el
   diálogo, observar el siguiente tick y comprobar que sigue actuando.
   Reiniciar ambos procesos y comprobar que la entidad y su waypoint
   persisten. El jugador **no debe gastar energía al quedarse quieto**.

Desactivar temporalmente la simulación automática en el servidor:
`$env:LAIN_WORLD_CLOCK="0"` antes de arrancar Uvicorn. El reloj solo
se activa en el proceso de FastAPI (no durante los tests unitarios que
importan los módulos).

## Pruebas de regresión

```powershell
.\.venv\Scripts\python.exe -m pytest -q
godot --headless --path client --editor --import --quit
godot --headless --path client --script res://tools/test_reality03_visual.gd
```

La suite de Python cubre tick autónomo sin acción humana, gasto cero de
energía del jugador, waypoint y origen persistentes, rechazo de WANDER
si lo intenta el humano y pausa/reanudación durante conversación.
La prueba de Godot sustituye el servidor por un snapshot falso; valida
aparición, interpolación, identidad e invisibilidad en las cuatro escenas,
sin modificar `world.db`. Realizar también una prueba manual de Godot
con Uvicorn y Ollama locales. No fusionar la PR experimental hasta
confirmar el recorrido visual en el entorno real del usuario.
