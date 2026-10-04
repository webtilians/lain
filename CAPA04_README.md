# LAIN · Capa 04 · Transporte

Rama `experiment/layer-04-transport`. Segunda capa del **Protocolo de
presencia** (ver [BIBLIA_NARRATIVA.md](BIBLIA_NARRATIVA.md)). Empieza al
decidir qué hacer con el paquete de la [Capa 03](CAPA03_README.md). Se activa
con `LAIN_LAYER_FOUR=1`, que ya ponen el lanzador, `serve-city.ps1` y el
servidor online.

**La pregunta:** ¿necesito que me respondan para existir?

## Qué hay que hacer (sin destripar)

1. En el PC de casa llega el correo **«SYN»**: alguien llama a tu puerto 4004
   desde NODO_07 y nadie contesta. El Navi no tiene pila TCP, así que **el saludo
   de tres pasos lo escribes tú** con `send`. `netstat`, `tcpdump` y `man tcp`
   tienen lo que necesitas.
2. Llega un mensaje partido en segmentos y uno se ha perdido. Confirma con
   **ACK acumulativos** solo lo que tienes seguido (`man ack`, `man
   retransmision`). Si confirmas bytes que no tienes, esas palabras se pierden
   para siempre.
3. El mensaje dice no venir de tan lejos. El **TTL** de sus paquetes y
   `/net/vecinos` te dicen a qué armario ir. Allí, en el puerto de consola,
   `tcpdump` enseña de quién es de verdad esa conexión.
4. Decide qué hacer con ella:
   - **cerrarla con FIN**: el cierre de cuatro pasos con los números exactos,
     sacados de los keepalive (`man keepalive`, `man fin`);
   - **cortarla con RST** (`man rst`);
   - **relevar los keepalive** (`keepalive nodo07`).

   Nora y K lo recordarán en sus conversaciones.

Cada jugador tiene su propia conexión: otros números de secuencia, otro
segmento perdido y otro armario. Todo sale en español e inglés.

## Órdenes nuevas

`netstat`, `tcpdump`, `send nodo07 <FLAGS> seq=<n> ack=<n>`, `wait`
(o `esperar`), `keepalive nodo07` (o `mantener`) y los temas de `man`: tcp,
ack, retransmision, keepalive, fin, rst, netstat, tcpdump, send.

## Cómo está construido

- `server/world_core/layer_four.py`: estado por jugador, conexión generada a
  partir de su id, máquina TCP (saludo, ACK acumulativo, retransmisión rápida
  tras 3 ACK repetidos o por RTO, cierre FIN de cuatro pasos, RST con seq
  exacto) y decisiones. Se engancha al terminal de la Capa 03 (mismo endpoint).
- El mensaje se genera en el idioma con el que el jugador empezó la capa; los
  manuales y las respuestas siguen el idioma elegido en cada momento.
- Cliente: la esquina y la pestaña Terminal muestran la capa más reciente; el
  PC enseña el correo de cada capa.

## Validación

`tests/test_layer_four.py` resuelve la capa entera leyendo solo la salida del
juego:
1. saca el SYN de `tcpdump` y calcula el ack;
2. encuentra el hueco en los números de secuencia y fuerza la retransmisión
   rápida;
3. deduce los saltos con el TTL y localiza el armario con `/net/vecinos`;
4. cierra con FIN usando el seq de los keepalive más uno.

También prueba la pérdida irreversible de datos, la retransmisión por RTO, el
RST con seq exacto, el relevo de los keepalive, la memoria de Nora y K, que
150 jugadores reciben conexiones distintas y que todo sale en inglés.
