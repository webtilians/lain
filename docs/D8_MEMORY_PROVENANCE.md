# LAIN D8 · Memoria relevante, procedencia y transmisión controlada

D8 parte de D7 y mantiene el diálogo libre con Ollama, la base de datos
local y la interfaz de Godot. No se borran las conversaciones anteriores.

## Qué cambia al hablar con K y Nora

- Cada agente recupera exclusivamente sus propios recuerdos. Se consultan
  hasta los últimos 1000 candidatos de su memoria persistente; la respuesta
  prioriza coincidencias léxicas con lo que pregunta el jugador y conserva
  algunos recuerdos recientes como contexto. La selección máxima sigue
  siendo 12. Esta búsqueda es **léxica**, no vectorial ni INFINITO todavía.
- Los nuevos mensajes del jugador quedan etiquetados como
  `PLAYER_TESTIMONY`, con su emisor y el turno de origen. No se transforman
  en hechos verificados de World Core.
- Se conserva y consulta la memoria previa a D8. Las entradas antiguas que
  contienen `PLAYER_1 said:` se señalan como testimonio legado; otras
  memorias sin metadatos nuevos quedan `LEGACY_UNCLASSIFIED`.
- El LLM recibe estos metadatos para distinguir testimonio, informe propio
  y transmisión de terceros. **No existe todavía un validador automático
  de todas sus afirmaciones**: una respuesta del modelo puede equivocarse.

## Transmisión entre personajes: contrato interno, NO cotilleo automático

`server/world_core/episodic_memory.py` proporciona primitivas internas:

- `remember_agent_report(..., shareable=True)` registra un informe que
  World Core ha autorizado expresamente a compartir.
- `relay_shareable_memory(sender_id, recipient_id, memory_id, minute)`
  requiere dos agentes de IA presentes en la misma localización, que
  la memoria sea del emisor y esté marcada como compartible. Copia el
  relato como `RELAYED_TESTIMONY`, conserva su procedencia y registra
  el intercambio. La copia recibida no se puede retransmitir por defecto.
- Los mensajes privados que dice el jugador quedan `shareable=False`
  por defecto y no se transmiten solo porque dos agentes estén cerca.

**Aún no hay un botón del jugador ni una decisión autónoma de K que
active estos intercambios**. El contrato y sus pruebas están preparados
para conectar una intención de agente explícita en un siguiente hito;
no afirmamos que K pueda contar ya tus secretos a Nora dentro del juego.

## Prueba jugable con tu modelo local

Conserva la configuración de Ollama de D7. Habla con K y dile:
`Mi contraseña centinela es ESTRELLA-52.`

Habla con él de otros asuntos durante varios turnos y pregúntale:
`¿Recuerdas cuál era la contraseña centinela?`

Comprueba que la respuesta proviene de `LLM_DIALOGUE` en la consola
de Godot y observa si lo atribuye a algo que **tú le contaste**, en lugar
de presentarlo como una comprobación propia. Pregunta después a Nora.
Nora no debe recuperar esa memoria privada en el contexto que le envía
World Core, aunque el modelo podría inventar una respuesta plausible.
Para discriminar memoria real frente a coincidencia, usa una frase
arbitraria distinta cada vez y revisa las pruebas D8 de privacidad.

## Pruebas y límites

En PowerShell desde la raíz del proyecto:

```powershell
cd C:\Users\ENRIQUE\lain; .\.venv\Scripts\Activate.ps1; python -m pytest -q
```

La suite usa bases SQLite temporales y no necesita conexión a Ollama:
simula las respuestas del proveedor. Hay pruebas de recuperación de
recuerdos antiguos, privacidad K/Nora, rechazo de transmisiones privadas,
procedencia de rumores transmitidos y deduplicación de relays.
