# Prólogo 0.2 — barrio explorable y conversaciones de deducción

Rama experimental: `experiment/prologue-0.2-neighborhood-dialogue`.
Base: `experiment/prologue-0.1-school-ryoko-terminal` (Reality 0.4,
Visual 0.6). No modifica la partida original, el stash, los recuerdos
ni las fichas técnicas de las siete entidades creadas.

## Revisión del prólogo 0.1 a partir de la prueba jugable

- **Antes:** el primer clic en el profesor o en Ryoko entregaba su pista
  completa sin una pregunta del jugador; el profesor revelaba la
  progresión en un monólogo, Ryoko mencionaba explícitamente TELNET
  y pedía buscar la sintaxis por Internet. El terminal HELP, sus errores
  y el diario repetían la solución o indicaban cómo averiguarla.
- **Ahora:** cada personaje responde a preguntas elegidas en el diálogo.
  Solo la pregunta apropiada al profesor desbloquea la búsqueda de
  Ryoko; solo una pregunta sobre los datos de acceso desbloquea el
  regreso al ordenador. Preguntar otra cosa, abrir un diálogo,
  darlo por terminado o encontrar a Ryoko antes del profesor NO
  adelanta el estado del servidor.
- El profesor recuerda que únicamente Ryoko parecía conocer la red,
  pero **no sabe dónde está**. El jugador debe explorar el barrio:
  ni el profesor ni el diario dicen «ve a la discoteca».
- Ryoko recuerda solamente `WIRED` y el **puerto 23** y dice
  «Lo demás tendrás que averiguarlo tú». No revela el protocolo, la
  sintaxis, un buscador ni que haya que preguntar a una IA.
  La solución real de programación sigue siendo exactamente
  `telnet wired 23`, validada **solo dentro del juego**. No se
  envía un paquete real de red ni se ejecutan comandos del sistema.
  No se acepta un texto parecido, otro host, otro puerto ni una
  secuencia de comandos.

## El barrio

El escenario `APARTMENT_DISTRICT` pasa de un corredor de unos
12 × 36 a un espacio de aproximadamente **38 × 78 unidades**, con:

- Una calle principal y dos aceras continuas, fachadas residenciales,
  locales cerrados, ventanas, iluminación y una plaza a medio camino.
- **Escuela** al oeste, integrada en una fachada cerca de
  `(-11.18, -20)`, con una entrada accesible desde la acera;
  **discoteca** en el otro extremo y al este, cerca de
  `(11.18, -53)`. El recorrido entre ambas atraviesa el barrio
  y no se reduce a cruzar la calle.
- Biblioteca cerrada, taller, parada sin servicio y cabina sin tono
  como puntos urbanos disponibles para futuras historias, sin inventar
  misiones ni dar recompensas por pulsar props inertes.
- Al salir de la escuela o de la discoteca reapareces **cerca de
  la fachada por la que acabas de salir**, no delante del apartamento.
  El cambio de localización continúa validándose en World Core.

Los exteriores son una **maqueta 3D ampliada y utilizable**, no arte
definitivo ni todavía un barrio con horarios, peatones o misiones
secundarias. Conservamos el personaje, decoración y la arquitectura
preexistente de Visual 0.6 mientras desarrollamos el escenario.

## Prueba segura en Windows

Detén primero Godot y Uvicorn. **No cambies de rama en**
`C:\Users\ENRIQUE\lain`: allí está tu partida principal y tus
cambios gráficos. Tampoco alteres `lain-prologue01`, porque es tu
primera prueba y contiene otra partida guardada.

Desde PowerShell, crea un worktree nuevo y **una base nueva** (sin
copiar ni borrar ninguna partida). Puedes ejecutar los tres comandos
de esta sección en una sola línea, separados por punto y coma, si
lo prefieres:

```powershell
cd C:\Users\ENRIQUE\lain
git fetch origin
git worktree add --detach ..\lain-prologue02 origin/experiment/prologue-0.2-neighborhood-dialogue
cd ..\lain-prologue02
```

Arranca el servidor desde ese worktree:

```powershell
$env:LAIN_WORLD_DB="C:\Users\ENRIQUE\lain-prologue02\newgame02.db"
$env:LAIN_PROLOGUE_ENABLED="1"
$env:LAIN_LLM_ENABLED="1"
$env:LAIN_LLM_MODEL="lain-qwen7b"
$env:LAIN_LLM_ENDPOINT="http://127.0.0.1:11434/v1/chat/completions"
$env:LAIN_REALITY_GENERATION="1"
$env:LAIN_WORLD_CLOCK="1"
$env:LAIN_WORLD_TICK_SECONDS="8"
C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m uvicorn server.api:app --host 127.0.0.1 --port 8000
```

En **otro PowerShell**, lanza Godot **desde el worktree nuevo**:

```powershell
cd C:\Users\ENRIQUE\lain-prologue02
.\play.ps1
```

Pulsa **J** si necesitas recordar la pista vigente; no obtendrás
instrucciones sobre Telnet. Explora hasta la escuela, pregunta al
profesor por quien conocía la red, busca a Ryoko sin indicador directo
y pregúntale por los datos que conserva. Vuelve a tu PC e intenta
resolver la conexión por tu cuenta. Si quieres comprobar por qué
funciona la solución, puedes buscar fuera del juego la finalidad del
**puerto 23**; este documento incluye la respuesta para el desarrollador
pero el cliente **no** se la dice al jugador.

## Aceptación y alcance de tests

```powershell
C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m pytest -q
godot --headless --path client --editor --import --quit
godot --headless --path client --script res://tools/test_prologue01_visual.gd
```

Las pruebas Python verifican la progresión por preguntas explícitas,
la imposibilidad de extraer los datos de Ryoko antes de hablar con
el profesor, la persistencia y la protección de partidas previas.
La prueba de Godot comprueba escenas, entradas separadas,
nuevo tamaño del barrio, retorno desde la discoteca, cuatro o más
preguntas en los diálogos y ausencia de pistas de TELNET/Internet
en el terminal. Todavía hay que recorrer a mano las aceras, puertas
y posibles oclusiones con el Godot instalado en Windows.
