# LAIN · Capa 03 · TTL

Rama `experiment/layer-03-ttl`, sobre `experiment/visual-0.12-gothic`.
Es la primera capa del **Protocolo de presencia**. La historia completa, los
temas y las siete capas están en [BIBLIA_NARRATIVA.md](BIBLIA_NARRATIVA.md).

Se activa con `LAIN_LAYER_THREE=1` (ya lo ponen el lanzador, `serve-city.ps1` y
el servidor online) en cuanto el jugador se ha conectado a Indara.

## Qué hay que hacer (sin destripar)

1. En el **PC de casa**, el correo «TTL=1» de una identidad desconocida y una
   pestaña nueva: **Terminal**. Empieza leyendo el correo y escribe `help`.
2. El paquete con el cuerpo del mensaje no llegó. Averigua en qué router se le
   acabó el TTL. Hay que entender cómo funciona un TTL: `man ttl` lo explica.
3. Ve a ese armario de enlace (estación, aula de informática o videoclub), pulsa
   **E** y elige **Conectarse al puerto de consola del armario**.
4. En su búfer de descartes están los segmentos: desordenados, con una
   retransmisión y una copia alterada. Reconstruye el mensaje con `ensamblar`.
5. El diario de Indara es una cadena de hashes y alguien reescribió una
   entrada. Demuéstralo con `denunciar`.
6. Decide qué haces con el paquete: `reenviar` o `soltar`. K y Nora lo
   recordarán (o no) en sus conversaciones con IA.

Cada jugador recibe su propio puzzle: otro paquete, otra ruta, otro armario y
otra entrada falsificada. No sirve copiar las respuestas de un amigo.

**Presencia:** si en tres minutos nadie te recibe (ninguna conversación, nadie
más en tu zona, ninguna respuesta de la red), tu señal se debilita y tu avatar
se vuelve translúcido y con fallos. Arriba a la derecha tienes el objetivo de la
capa y el aviso de señal.

## Órdenes del terminal

`ls`, `cd`, `pwd`, `cat`, `grep`, `sha256`, `traceroute`, `ping`, `whoami`,
`uptime`, `last`, `date`, `man`, `ensamblar`, `denunciar`, `reenviar`, `soltar`,
`clear`, `exit`. Las ejecuta el servidor sobre un sistema de archivos del
mundo: nada toca el ordenador de nadie y el cliente no puede saltarse un paso.
`uptime` y `last` muestran datos reales del servidor (sus reinicios son los
«apagones» del mundo).

## Cómo está construido

- `server/world_core/layer_three.py`: estado por jugador, generación
  determinista del puzzle a partir del id del jugador, sistema de archivos
  virtual, intérprete y decisiones. Endpoint `POST /api/v1/layer-three/shell`.
- Los armarios (`network_conflict.py`) ofrecen la consola; la decisión de
  reenviar entra en la memoria de K y Nora por `agent_context.py`.
- Cliente: `scripts/ui/ShellTerminal.gd` (terminal), `scripts/ui/PresenceSignal.gd`
  (objetivo y desvanecimiento), pestaña Terminal y correo en `Workshop.gd`.

## Validación

- `tests/test_layer_three.py`: resuelve la capa entera usando solo lo que el
  jugador puede leer (tabla de rutas, manual, huellas y diario); comprueba la
  consola física, los errores de ensamblado, el sellado tras tres denuncias, la
  memoria de K y que 200 jugadores reciben puzzles distintos y resolubles.
- `client/tools/test_layer03.gd`: pestaña, terminal, historial, consola del
  armario, bloqueo del movimiento y desvanecimiento.
