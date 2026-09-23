# Reality 0.2-r1 — correccion de enrutamiento del dialogo LLM

Esta rama parte de `experiment/reality-0.2-autonomy-visual04` y mantiene
todos los cambios visuales de Visual 0.4, las entidades persistentes y sus
pruebas. No modifica el guardado ni fusiona ramas previas.

**Causa:** `generate_dialogue_reply` respondia desde `CURRENT_TESTIMONY`,
`GROUNDED_RECALL` o `general_claims` *antes* de consultar el modelo, incluso
con `LAIN_LLM_ENABLED=1`. Por tanto Reality nunca examinaba esos turnos para
proponer una entidad. Ademas la conexion HTTP al modelo capturaba cualquier
excepcion y se limitaba a mostrar un fallback sin diagnostico.

Ahora, con `LAIN_LLM_ENABLED=1`, las **preguntas abiertas y narrativas**
llegan al LLM: el modelo recibe solo el contexto privado del destinatario.
Las declaraciones personales explícitas (por ejemplo, `Mi perro se llama...`),
las preguntas de memoria cronológica y los encuentros verificables mantienen
las respuestas deterministas para no confundir recuerdos con invenciones.
También se conservan las barreras de contraseñas y la inexistencia de una
clave verificada de acceso a NODE_07. Solo cuando una respuesta original del
LLM imagina una presencia y Reality acepta una propuesta válida se crea
una entidad persistente; no está garantizada en cada turno.
Con el modelo desactivado permanece el comportamiento determinista anterior.

Al activar `LAIN_LLM_TRACE=1` (o `LAIN_REALITY_TRACE=1`), el servidor
imprime solo codigos: `LLM // REQUESTED`, `LLM // RESPONSE_RECEIVED`,
`LLM // FALLBACK_HTTP_404`, `LLM // FALLBACK_TIMEOUT`,
`LLM // FALLBACK_CONNECTION_ERROR`,
`LLM // FALLBACK_INVALID_RESPONSE_OR_CONFIGURATION`,
`LLM // BYPASS_PASSWORD_CLAIM`, `LLM // BYPASS_NODE_ACCESS_RULE`.
Nunca incluye el texto de la conversacion, respuestas crudas, URL ni keys.
Un `LLM // RESPONSE_RECEIVED` demuestra que el provider respondio, no que
World Core creara una entidad. Para ello observar
`REALITY // ENTITY_CREATED_ENTITY_...`.

## Ejecutar con Ollama local

Detener previamente el viejo servidor con Ctrl+C y ejecutar desde PowerShell
en la raiz del repositorio. Verificar que Ollama tiene el modelo configurado.

```powershell
git fetch origin
git switch --track origin/experiment/reality-0.2-r1-llm-routing
$env:LAIN_LLM_ENABLED="1"
$env:LAIN_LLM_MODEL="lain-qwen7b"
$env:LAIN_LLM_ENDPOINT="http://127.0.0.1:11434/v1/chat/completions"
$env:LAIN_LLM_TIMEOUT="45"
$env:LAIN_LLM_TRACE="1"
$env:LAIN_REALITY_GENERATION="1"
$env:LAIN_REALITY_TRACE="1"
$env:LAIN_REALITY_TIMEOUT="45"
.\.venv\Scripts\python.exe -m uvicorn server.api:app --reload
```

Si se usa la rama local por segunda vez en vez de `--track`, ejecutar
`git switch experiment/reality-0.2-r1-llm-routing; git pull --ff-only`.
`play.ps1` arranca Godot por separado. No eliminar `world.db`.

Para un chequeo independiente del modelo sin hablar con ningun NPC:

```powershell
ollama list
$body = @{ model="lain-qwen7b"; messages=@(@{role="user";content="Responde hola en una frase."}); stream=$false } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri "http://127.0.0.1:11434/v1/chat/completions" -Method Post -ContentType "application/json" -Body $body
```

El chequeo envia solo el texto de prueba, no memorias del jugador. Si devuelve
404, revisar el nombre exacto en `ollama list`. Si hay
`FALLBACK_TIMEOUT`, una primera carga del modelo o insuficiente RAM pueden
necesitar mas tiempo. Con el provider accesible, hablar con K/Nora por texto
libre y comprobar en Godot `DIALOGUE // SOURCE = LLM_DIALOGUE` antes de
esperar una propuesta Reality. Algunos temas predefinidos tienen protecciones
que devuelven una respuesta determinista de forma deliberada.


## Diagnostico si Godot sigue mostrando DETERMINISTIC_FALLBACK

Godot solo muestra el tipo de respuesta. El codigo `LLM // ...` se imprime
en la **ventana de PowerShell del servidor Python**, no en la consola Godot.
Si `LLM // REQUESTED` aparece seguido de `LLM // FALLBACK_TIMEOUT`, por
ejemplo, la consulta se intento y fracaso. Si aparece
`LLM // RESPONSE_RECEIVED` seguido de
`LLM // FALLBACK_REPEATED_GREETING`, el modelo contesto, pero repitio una
frase de saludo que no es una respuesta a la pregunta.

Para aislar la conexion de Ollama y el procesado del contexto sin alterar
`world.db` ni enviar ninguna conversacion de la partida, detenga Godot si
hace falta y, desde **otra** consola PowerShell con el mismo modelo, endpoint
y timeout configurados, ejecute:

```powershell
cd C:\Users\ENRIQUE\lain
.\.venv\Scripts\python.exe -m tools.diagnose_llm
```

El script hace dos consultas exclusivamente con texto **sintetico**.
`SIMPLE_HTTP_404` indica que el modelo/ruta no se puede consultar con
ese endpoint; `SIMPLE_CONNECTION_ERROR` indica que la conexion local
ha fallado; `SIMPLE_TIMEOUT` indica que la consulta minima ha agotado
el tiempo. `SIMPLE_OK` seguido de `LAIN_CONTEXT_...` separa un proveedor
accesible de un fallo con el formato o carga del contexto realista de LAIN.
`LAIN_CONTEXT_OK` demuestra que el modelo es accesible desde el proceso de
diagnostico pero no que el **proceso Uvicorn que esta sirviendo al juego**
tenga las mismas variables, ultima rama o puerto. Las lineas de diagnostico
no contienen credenciales, memoria ni dialogos de tu partida.

Si ambos chequeos dan OK pero la partida sigue devolviendo el fallback,
comprobar en la ventana de Uvicorn sus lineas `LLM // ...` y confirmar que
Godot conecta con el servidor local de puerto 8000. La generacion de
entidades necesita ademas el codigo `REALITY // ENTITY_CREATED_ENTITY_...`.
