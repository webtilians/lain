# D10 experimental: episodios autobiográficos y cronología privada

Base validada: `develop/isometric-0.2-d9-r1`, commit
`d0043afaad3bf6e1455e26743c63de1f9a833a2b`.
Rama independiente: `experiment/isometric-0.2-d10-episodic`.

## Comportamiento

Cada nuevo recuerdo conserva el propietario, fuente, emisor, turno original,
minuto de adquisición y, cuando existe, conversación y lugar de adquisición.
Las observaciones e investigaciones que World Core ya registraba ahora llevan
procedencia individual. Un informe propio sigue siendo SELF_REPORTED; un
rumor transmitido conserva su padre y no se convierte en observación directa.

La recuperación episódica combina coincidencia léxica, contexto del lugar y
recencia: cuatro recuerdos recientes preservan continuidad; las otras plazas
priorizan relevancia. El lugar desempata coincidencias y no introduce recuerdos
ajenos. Se examinan hasta 1000 candidatos privados y se devuelven 12 por defecto,
ordenados por minuto de adquisición e ID. La expansión semántica D9 sigue siendo
opcional y desactivada por defecto.

La cronología de declaraciones personales usa los turnos originales del jugador,
filtrados por destinatario y fuente. Conserva versiones anteriores y distingue
EARLIER_TESTIMONY de CURRENT_TESTIMONY. «Actual» significa lo último oído por ese
personaje, nunca verdad comprobada. En un mismo minuto, el ID del turno determina
el orden de recepción. No se interpreta como fecha del suceso relatado.

Preguntas deterministas admitidas, sin Ollama:

- `¿Cómo se llama mi perro?` / `¿Cómo se llama mi perro ahora?`
- `¿Cómo se llamaba mi perro antes?` / `¿Cómo se llamaba mi perro de antes?`
- `¿Qué te dije primero sobre mi perro?`
- `¿Qué te dije antes sobre mi perro?`
- `¿Qué ha cambiado sobre mi perro?`

«Antes» devuelve la declaración inmediatamente anterior y la última; «primero»
la primera registrada. Si solo hay una versión, reconoce que desconoce una
anterior. El historial se deriva de turnos persistidos, también de partidas
antiguas; no se toman respuestas del modelo como declaraciones del jugador.
Se recorre el historial privado completo para no perder la primera versión,
con memoria de trabajo acotada y un máximo de 12 versiones en el contexto
(primera y últimas 11 si hay más). El coste de esa consulta crece con el historial.

## Autoridad y compatibilidad

World Core conserva acciones, creencias, acceso a nodos y reglas. El diálogo
solo escribe testimonios; una contraseña personal no desbloquea NODE_07.
K y Nora consultan exclusivamente sus propios recuerdos. No hay difusión por
proximidad ni lectura automática de recuerdos del otro personaje.

La migración SQLite solo añade `agent_memory_episodes` con CREATE TABLE IF NOT
EXISTS. No borra ni reescribe tablas existentes. Los nuevos metadatos se guardan
en la misma transacción que el recuerdo. Los recuerdos antiguos conservan el
texto y la procedencia disponible; fechas y lugares desconocidos siguen vacíos,
sin inventar el lugar actual del personaje como lugar histórico. No hay cambios
en Godot, sus controles, escenas ni formato de las respuestas de la API.

Límites: no es comprensión temporal general ni embeddings. La cronología
estructurada admite las declaraciones explícitas D9 (`Mi … es …`, `Mi … se
llama …`) y las preguntas anteriores; contraseñas mantienen su ruta D8.
Otros relatos se recuperan como episodios atribuidos y, con el modelo activado,
su formulación depende de él. No se infieren automáticamente sucesos, emociones
ni fechas a partir del texto. Historiales truncados se señalan en el contexto.

## Prueba local sin perder tu partida

1. Detén el servidor y guarda una copia de `world.db` fuera del repositorio.
   Con el árbol de trabajo limpio, desde tu carpeta habitual de LAIN:

   ```powershell
   git fetch origin
   git switch --track origin/experiment/isometric-0.2-d10-episodic
   .\.venv\Scripts\Activate.ps1
   python -m pytest -q
   python -m uvicorn server.api:app --reload
   ```

   Si la rama local ya existe, usa `git switch experiment/isometric-0.2-d10-episodic`.
   Conserva tu configuración habitual de Ollama y abre el mismo proyecto Godot.
   No borres `world.db` ni ejecutes una inicialización de partida nueva.
2. Habla con K: `Mi perro se llama Tango.` y después
   `Mi perro ahora se llama Lupo.`
3. Pregunta por el nombre actual: debe citar Lupo. Pregunta
   `¿Cómo se llamaba mi perro de antes?`: debe distinguir Tango de Lupo.
4. Pregunta lo mismo a Nora. Si nunca se lo contaste, debe decir que no lo
   recuerda; si ya tenía información propia, responderá con su historial.
5. Reinicia el servidor conservando `world.db` y repite las preguntas a K.
   Debe mantener las versiones. Puedes hablar de otro tema entre las preguntas.

Las pruebas usan SQLite temporal y proveedores simulados; no necesitan Ollama
ni alteran la partida. Incluyen privacidad, empates de minuto, reinicialización
idempotente, historial antiguo/largo, procedencia, lugar histórico, turnos
rechazados y regresiones existentes del World Core. El cliente Godot requiere
la comprobación manual anterior; la suite Python no prueba el renderizado.
