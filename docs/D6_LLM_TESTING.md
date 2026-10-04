# D6 · Primer diálogo generativo (experimental)

El servidor conserva World Core y SQLite como autoridad. Godot no necesita
cambios: los turnos generados usan el mismo endpoint y contrato de D5.

## Sin configurar nada

El diálogo sigue siendo determinista, con memoria y reanudación D5 intactas.
No se envían recuerdos ni conversaciones a ningún proveedor por defecto.

## Probar un modelo LOCAL con endpoint compatible

1. Inicia tu servidor local de inferencia (por ejemplo, un servidor
   compatible con chat-completions). Comprueba en su interfaz el puerto
   real y el ID exacto del modelo cargado.
2. En PowerShell, en la carpeta del proyecto, usa estas líneas (una por
   instrucción; sustituye NOMBRE_REAL por el modelo que tengas cargado):

```powershell
$env:LAIN_LLM_ENABLED="1"
$env:LAIN_LLM_MODEL="NOMBRE_REAL"
$env:LAIN_LLM_ENDPOINT="http://127.0.0.1:1234/v1/chat/completions"
$env:LAIN_LLM_TIMEOUT="8"
.\.venv\Scripts\Activate.ps1
uvicorn server.api:app --reload
```

El puerto 1234 es solo un ejemplo. Si tu servidor local usa otro,
cambia LAIN_LLM_ENDPOINT. Nunca pegues una API key en GitHub, en capturas
ni en mensajes; si la necesitas, usa una variable de entorno privada.

3. En Godot habla con K: después de pulsar una opción de diálogo,
   la respuesta debería ser nueva y distinta de la respuesta fija D5.
   El saludo al reabrir sigue siendo determinista en D6.
4. Para comprobar si hubo generación, consulta en la base local:
   `SELECT source, text FROM player_conversation_turns ORDER BY id DESC LIMIT 5;`
   Solo `LLM_DIALOGUE` confirma que el turno lo generó el modelo.
   `DETERMINISTIC_DIALOGUE` significa que se utilizó el respaldo:
   modelo no cargado, endpoint incorrecto, fallo de red, respuesta inválida,
   tiempo de espera o modo desactivado.

## Privacidad y límites de D6

La inferencia es opt-in. El endpoint local es el valor por defecto;
un endpoint remoto solo se admite con HTTPS, LAIN_LLM_ALLOW_REMOTE=1 y
LAIN_LLM_API_KEY establecido en el proceso del servidor. Activarlo de forma
remota enviará el contexto individual y turnos recientes a ese proveedor;
revísalo antes de hacerlo. El sistema no envía el estado global del mundo,
pero el modelo puede alucinar o interpretar erróneamente información.
La instrucciones de contexto son una primera barrera, NO una verificación
formal de cada frase. No habilitamos acciones ni mutación de creencias
propuestas por el LLM. INFINITO todavía no está conectado.

D6 mantiene las opciones de diálogo actuales; la entrada libre, un validador
de afirmaciones y la recuperación selectiva de INFINITO son hitos futuros.

## Pruebas sin conexión al proveedor

```powershell
$env:LAIN_LLM_ENABLED="0"; python -m pytest -q
```

Los tests D6 simulan las respuestas del proveedor y no precisan modelo ni red.
