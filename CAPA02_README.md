# LAIN · Capa 02 · Enlace

Rama `experiment/layer-02-link`. Segunda capa del **Protocolo de presencia**
(ver [BIBLIA_NARRATIVA.md](BIBLIA_NARRATIVA.md)). Empieza al decidir qué hacer
con el cable de la [Capa 01](CAPA01_README.md). Se activa con
`LAIN_LAYER_TWO=1`, que ya ponen el lanzador, `serve-city.ps1` y el servidor
online.

**La pregunta:** ¿quién eres si te pueden copiar?

## Qué hay que hacer (sin destripar)

1. En el PC de casa llega un correo de K. La tabla del conmutador de la estación
   no se está quieta: tu dirección MAC aparece en dos puertos a la vez.
2. En tu Navi, `ip link` enseña tu dirección y el número de tu último latido.
3. En la consola del armario del andén:
   - `show mac` y `show log` enseñan la tabla y los avisos `MAC_FLAP` entre
     los dos puertos (`man conmutador`);
   - `capture <puerto>` enseña las tramas de cada uno (`man trama`).
4. En cada puerto hay una trama dañada. `fcs <puerto> <n>` compara el CRC-32 que
   trae con el calculado (`man fcs`). Descartadas las dañadas, los latidos dicen
   cuál es tu puerto. El otro es una réplica tuya que KAGAMI copió hace un
   tiempo.
5. Decide qué hacer con tu copia:
   - **apagar su puerto** (`shutdown <puerto>`);
   - **cambiar tu propia dirección** (`ip link set address <mac>`, en tu Navi).
     Tiene que ser unicast y administrada localmente (`man mac`); la copia se
     queda con la tuya de fábrica;
   - **compartirla** (`compartir`): para la red sois la misma persona en dos
     sitios.

   Nora y K lo recordarán en sus conversaciones.

Cada jugador tiene su propia dirección, sus puertos y sus latidos. Todo sale en
español e inglés (en inglés también vale `share`).

## Órdenes nuevas

`ip link`, `ip link set address <mac>`, `show mac`, `show log`,
`capture <puerto>`, `fcs <puerto> <n>`, `shutdown <puerto>`, `compartir` y los
temas de `man`: mac, trama, fcs, conmutador.

## Cómo está construido

- `server/world_core/layer_two.py` genera, para cada jugador:
  - su dirección y los dos puertos;
  - las tramas de cada puerto, con un FCS CRC-32 calculado sobre destino,
    origen, tipo y datos;
  - una trama dañada por puerto, que conserva el FCS de lo que se envió.

  La réplica se copió unos cientos de latidos antes. Una de sus tramas dañadas
  parece llevar tu último latido, y solo el FCS la delata.
- Se engancha al terminal de la Capa 03 (mismo endpoint). `capture` enseña las
  tramas tal cual; se generan en el idioma con el que el jugador empezó la capa.
- El fragmento 2 cuenta en el total de capas completadas
  (`server/world_core/protocol.py`).

## Validación

`tests/test_layer_two.py` resuelve la capa leyendo solo la salida del juego:
1. lee tu dirección y tu último latido en `ip link`;
2. saca los dos puertos de `show log`;
3. descarta en cada puerto la trama cuyo FCS no coincide;
4. reconoce tu puerto por los latidos y apaga el de la copia.

También prueba:
- las reglas de una dirección nueva: formato, multicast, universal y local;
- compartir;
- las órdenes fuera de su consola;
- la variedad entre 100 jugadores;
- que todo sale en inglés.
