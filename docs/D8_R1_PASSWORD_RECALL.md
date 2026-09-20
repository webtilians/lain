# D8-r1 · Reparación de recuerdos contradictorios de contraseña

## Problema reproducido

Un LLM puede escoger una contraseña antigua de un historial mezclado o
responder «no tengo constancia» después de recibir una nueva. El registro
persistente de un turno no garantiza por sí solo su recuperación correcta.

## Qué cambia

World Core conserva para cada NPC, por separado, la última declaración
explícita de contraseña que haya recibido del jugador. Es una
`PLAYER_TESTIMONY`, no una observación propia ni un hecho del mundo.
Los turnos anteriores se mantienen íntegros; la última contraseña declarada
tiene preferencia para las preguntas directas por ese dato.

Ejemplos de frases reconocidas:

- `Mi contraseña es ESTRELLA-52.`
- `Esta es mi contraseña: MAR-763.`
- `Mi nueva contraseña es LUNA-28.`
- `Mi contraseña centinela es RIO-819.`

`Esta es mi contraseña.` **no especifica ningún valor**, así que no se
crea un recuerdo concreto a partir de esa frase. No se intenta adivinarlo.

Cuando el jugador pregunta por su contraseña y el NPC tiene un valor
explícito guardado, el servidor devuelve una **respuesta fundamentada en
el testimonio** con `response_source=GROUNDED_RECALL`. Esta respuesta
concreta no procede del LLM. El resto del diálogo libre continúa usando
Ollama y mantiene su procedencia `LLM_DIALOGUE`.

Los turnos libres anteriores a D8-r1 se examinan, sin reinicializar la
base de datos, para recuperar las declaraciones explícitas más recientes.
Una entrada solo puede recuperarse por el destinatario de su conversación.
Nora no recibe la contraseña de K, aunque puede recordar la que tú le
hayas contado a ella. No hay transmisión automática entre personajes.

## Prueba jugable

Conserva `world.db`: haz una copia de seguridad antes de cambiar de
rama. Mantén la configuración local de Ollama usada en D8.

1. Di a K `Mi contraseña es ESTRELLA-52.`
2. Dile `Mi contraseña ahora es NUBE-731.`
3. Pregunta `¿Cuál es mi contraseña?`
4. K debe referirse a **NUBE-731** y mostrar
   `DIALOGUE // SOURCE = GROUNDED_RECALL`.
5. Pregunta lo mismo a Nora antes de contarle un valor: no debería
   recuperar el testimonio privado de K.
6. Di a Nora `Esta es mi contraseña: LAGO-561.` y repite la pregunta.
   Nora debe recordar **LAGO-561**, no la contraseña que escuchó K.

Para esta prueba usa contraseñas **inventadas del juego**; no introduzcas
claves reales de tus cuentas en ningún chat de NPC. Las conversaciones
se conservan en la base local y pueden aparecer en respaldos.

**Límites:** esta corrección cubre únicamente declaraciones explícitas
de contraseña con ese formato. No convierte la memoria en comprensión
general, no valida todas las respuestas del LLM y no integra todavía la
recuperación semántica de INFINITO. El siguiente hito debe ampliar este
mecanismo sin depender de reglas especiales por cada tipo de recuerdo.
