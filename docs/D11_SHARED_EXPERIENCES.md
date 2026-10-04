# D11 experimental: experiencias compartidas

Base: D10 validado por el usuario, commit `74d94353c880251c2305b9e4a0d5de7c09c447c0`.
Rama: `experiment/isometric-0.2-d11-shared-experiences`.

## Qué registra World Core

- ENCOUNTER: ambos participantes de una conversación iniciada o reanudada.
  El saludo y el episodio se guardan en la misma transacción. Reintentar START
  no duplica el encuentro. Un encuentro no demuestra investigación conjunta.
- INVESTIGATE / OBSERVE: acciones aceptadas, registradas únicamente para su actor,
  junto con el evento original, minuto, lugar, objetivo y papel individual.
- SHARED_ATTENTION: una investigación aceptada y otra observación o investigación
  aceptada sobre el mismo nodo, en el mismo lugar y en la misma resolución de
  acciones. Cada participante conserva su papel. No se emparejan acciones de
  resoluciones distintas, aunque coincida el minuto; si alguno se mueve durante
  esa resolución no se crea la experiencia compartida.

Esta regla acredita atención compartida al objetivo, no que alguien viera cada
movimiento del otro, ni que conozca sus resultados privados. Estar cerca, recibir
un relato, investigar en otro momento o tener una acción rechazada no basta.
No existe un nuevo endpoint para fabricar experiencias desde el cliente o LLM.
No se cambian las decisiones de los agentes para forzar experiencias compartidas.

## Consultas deterministas

- `¿Qué pasó la última vez que estuvimos en la estación?`
- `¿Qué pasó la última vez que estuvimos en el apartamento?`
- `¿Estabas conmigo cuando investigamos esa señal?`
- `¿Estabas conmigo cuando investigamos NODE_07?`
- `¿Eso lo viste tú o te lo conté yo?`
- `¿NODE_07 lo viste tú o te lo conté yo?`

El encuentro actual se excluye al preguntar por la última vez. La respuesta
atestigua el encuentro anterior, no resume todos los sucesos posteriores a él.
Las respuestas de investigación distinguen observador e investigador y no
atribuyen conclusiones del otro participante. Las preguntas ambiguas solicitan
identificar la señal. Un testimonio explícito recuperado puede atribuirse al
jugador, pero no se transforma en percepción propia. Sin registros, el personaje
reconoce la falta de recuerdo; no afirma que el suceso nunca haya ocurrido.

El contexto privado incluye hasta 12 experiencias; las consultas por lugar,
objetivo o investigación compartida filtran antes del límite. La referencia
«eso» solo se resuelve si hay un único objetivo en ese contexto acotado; usa
NODE_07 para una consulta inequívoca. Otros giros lingüísticos dependen del
modelo. No hay comprensión general de referencias temporales o pronombres.

## Persistencia y límites

Se añade `agent_experiences` e índice por propietario, sin borrar ni reescribir
la partida. Cada episodio tiene clave idempotente y vínculo al evento o turno
original. Las acciones y su experiencia individual se escriben juntas; la
proyección compartida se escribe atómicamente al terminar la resolución. El
motor ya existente no convierte toda la resolución en una única transacción:
una interrupción entre ambas fases podría dejar solo experiencias individuales,
nunca se inventan participantes para completar un registro faltante.

No hay reconstrucción de encuentros históricos usando la ubicación actual.
Los recuerdos D10 y partidas SQLite siguen siendo válidos; las nuevas experiencias
comienzan al ejecutar D11. K y Nora solo consultan sus episodios. No se copian
sus diálogos privados ni sus creencias. Godot, controles y reglas permanecen igual.

## Prueba local

Con servidor detenido, respalda `world.db` fuera del repositorio. Desde LAIN:

```powershell
git fetch origin
git switch --track origin/experiment/isometric-0.2-d11-shared-experiences
.\.venv\Scripts\Activate.ps1
python -m pytest -q
python -m uvicorn server.api:app --reload
```

Si la rama local ya existe, usa `git switch experiment/isometric-0.2-d11-shared-experiences`.
Abre el proyecto Godot y conserva tu configuración de Ollama.

1. En la estación habla con K, sal de la conversación con «Alejarse» y vuelve
   a hablarle. Pregunta qué pasó la última vez que estuvisteis en la estación:
   debe recordar el encuentro anterior. Nora no recibe ese encuentro privado.
2. Di a K `Investigamos juntos NODE_07.` y pregunta si estaba contigo. La frase
   por sí sola no debe crear una investigación compartida.
3. Si World Core resuelve tu investigación y una observación/investigación de K
   juntas, pregunta si estaba contigo: debe responder según su papel real.
   No está garantizado que la IA elija esa acción en cada partida; la prueba
   automática reproduce esa situación sin alterar sus decisiones de juego.
4. Pregunta `¿NODE_07 lo viste tú o te lo conté yo?` para comprobar procedencia.
5. Reinicia el servidor y repite. Los episodios deben persistir.

Pruebas automáticas: encuentros/reintentos/reanudación, privacidad, fuentes,
acciones aceptadas/rechazadas, proximidad insuficiente, resoluciones separadas,
movimientos, roles distintos, persistencia e idempotencia y rollback. SQLite
es temporal; no se necesita un modelo real. El renderizado Godot se comprueba
manualmente con la secuencia anterior.

## D11-r1: preguntas repetidas y variantes del encuentro

Corrección en `experiment/isometric-0.2-d11-r1-recall` desde D11.
También se reconocen «que paso la ultima vez que nos vimos», «que paso la
ultima vez que nos encontramos en la estacion» y «q» como abreviatura de
«que». Se conserva el encuentro anterior al diálogo actual incluso al repetir
la pregunta. La respuesta menciona el lugar y el minuto sin la coletilla
«No deduzco ...». Un saludo de reanudación devuelto por el modelo no se acepta
como respuesta: si la pregunta no tiene recuperación disponible, se solicita
reformular en lugar de repetir el saludo. No se borran conversaciones previas.

Para actualizar desde D11, con el servidor detenido:

```powershell
git fetch origin
git switch --track origin/experiment/isometric-0.2-d11-r1-recall
```

Reinicia el servidor y prueba «que paso la ultima vez que nos encontramos en
la estacion» varias veces seguidas, sin cerrar el diálogo. Debe recordar el
mismo encuentro previo. Prueba también «q» y «nos vimos».
