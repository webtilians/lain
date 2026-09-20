# LAIN 0.2-D7 · Conversación libre

D7 añade un campo de texto a las conversaciones con K y Nora. Las
interacciones de World Core, las conversaciones previas y las respuestas
rápidas existentes siguen disponibles; en el diálogo compacto del NPC se
muestra una pregunta rápida sobre NODE_07 y la opción **Alejarse**.

## Prueba manual

1. Guarda una copia de `world.db` fuera de la carpeta del repositorio.
2. Cambia a `develop/isometric-0.2-d7` y mantén Ollama encendido.
3. Arranca Uvicorn con el modelo local ya instalado:

```powershell
cd C:\Users\ENRIQUE\lain; $env:LAIN_LLM_ENABLED="1"; $env:LAIN_LLM_MODEL="lain-qwen7b"; $env:LAIN_LLM_ENDPOINT="http://127.0.0.1:11434/v1/chat/completions"; $env:LAIN_LLM_TIMEOUT="15"; .\.venv\Scripts\Activate.ps1; uvicorn server.api:app --reload
```

4. En Godot, habla con K y escribe una frase nueva, por ejemplo:
   «Recuerda que mi palabra clave es ESTRELLA-52».
5. Pulsa ENVIAR o Enter. En la consola comprueba
   `DIALOGUE // SOURCE = LLM_DIALOGUE`; si aparece
   `DETERMINISTIC_FALLBACK`, el modelo local no respondió y
   el servidor registró el mensaje, pero la respuesta no es generativa.
6. Aléjate, vuelve a hablar con K y pregúntale por la palabra clave
   con otras palabras. Pregunta también a Nora: no debería acceder
   automáticamente a esa conversación privada de K. El modelo puede
   alucinar: esta prueba necesita revisar su respuesta y su procedencia.

## Contrato de API

`POST /api/v1/player/conversations/{actor_id}/say`

```json
{"text":"Mensaje del jugador","after_turn_id":123}
```

Solo acepta hasta 500 caracteres de una línea. Requiere conversación
OPEN y al agente presente en la misma localización semántica que el jugador.
La respuesta usa el formato de las opciones anteriores y añade
`response_source`. El servidor guarda el turno del jugador con procedencia
`PLAYER_FREE_TEXT` y su recuerdo solo en la memoria del destinatario.

Un mensaje del jugador NO modifica automáticamente creencias, nodos,
ubicaciones u objetivos de World Core. Un LLM puede decir cosas falsas:
sus textos siguen siendo diálogo narrativo, no hechos verificados por
la simulación. El protocolo no ejecuta acciones sugeridas por el LLM.

## Pruebas

```powershell
cd C:\Users\ENRIQUE\lain; .\.venv\Scripts\Activate.ps1; python -m pytest -q
```

Los tests usan una base temporal distinta de `world.db`.
