# LAIN · Capa 01 · Física

Rama `experiment/layer-01-physical`. Primera capa del **Protocolo de
presencia** (ver [BIBLIA_NARRATIVA.md](BIBLIA_NARRATIVA.md)). Se activa con
`LAIN_LAYER_ONE=1`, que ya ponen el lanzador, `serve-city.ps1` y el servidor
online.

**La pregunta:** ¿qué es un cuerpo?

## Cuándo aparece

- **Jugadores nuevos:** se abre con la conexión a Indara, a la vez que la
  [Capa 03](CAPA03_README.md). La esquina de la pantalla enseña primero la
  Capa 01.
- **Quien ya estaba más adelante:** la tiene abierta para jugarla cuando quiera.
  La esquina sigue enseñando su capa principal hasta que la termine.

Los fragmentos de la Sesión Cero cuentan capas completadas: cada capa recupera
el suyo (la 01 el 1, la 07 el 7). La Sesión Cero solo queda completa con las
siete.

## Qué hay que hacer (sin destripar)

1. En el PC de casa llega un parte del profesor: el enlace del pabellón B lleva
   días mudo porque alguien cortó el cable de su armario, en el aula de
   informática.
2. En la consola de ese armario, `scope naranja` y `scope verde` enseñan lo que
   captó el chip del lado cortado. Solo un par lleva datos; el otro solo lleva
   pulsos de enlace (`man cable`).
3. `decode <par> <muestras por medio bit> <ieee|thomas>` lee la señal. Hay que
   deducir tres cosas:
   - cuántas muestras forman un medio bit, a partir del muestreo y de que
     10BASE-T va a 10 Mbit/s con Manchester (`man señal`);
   - que el ruido se vence por mayoría (`man ruido`);
   - qué convención Manchester encaja con la polaridad del par. El preámbulo
     de Ethernet (`man preambulo`, `man manchester`) lo delata.
4. Decide qué hacer con el cable:
   - **empalmarlo** (`empalmar`): el enlace vuelve, y su rastro también;
   - **dejarlo cortado** (`dejar`);
   - **puentearlo por tu Kumo** (`puentear`): la señal pasa por ti.

   Nora y K lo recordarán en sus conversaciones.

Cada jugador tiene su propia captura: otro par, otra polaridad, otro muestreo y
otro ruido. Todo sale en español e inglés (en inglés también valen `orange`,
`green`, `splice`, `leave` y `bridge`).

## Órdenes nuevas

`scope <par> [desde]` (u `osciloscopio`), `decode <par> <muestras> <ieee|thomas>`
(o `decodificar`), `empalmar`, `dejar`, `puentear` y los temas de `man`: señal,
manchester, ruido, preambulo, cable.

## Cómo está construido

- `server/world_core/layer_one.py` hace todo el trabajo:
  - construye la trama: preámbulo, SFD y mensaje, con cada byte empezando por
    el bit menos significativo;
  - la codifica en Manchester con la polaridad del par;
  - la sobremuestrea con ruido que nunca gana una votación;
  - la decodifica por mayoría y cuenta las violaciones de código.
- `server/world_core/protocol.py` cuenta los fragmentos (capas decididas) y
  decide qué capa enseña el cliente (`current_layer` en el estado del jugador).
- Se engancha al terminal de la Capa 03 (mismo endpoint). `scope` y `decode`
  enseñan los bytes sin traducir; el mensaje se genera en el idioma con el que
  el jugador empezó la capa.

## Validación

`tests/test_layer_one.py` resuelve la capa leyendo solo la salida del juego:
1. busca el par con datos;
2. saca las muestras por medio bit del muestreo;
3. prueba IEEE y, si el preámbulo no aparece, Thomas;
4. lee el mensaje y empalma.

También prueba:
- que las decisiones exigen haber leído la trama y solo ocurren una vez;
- que los jugadores que ya iban por la Capa 04 la reciben como capa abierta,
  sin perder su capa principal;
- que los fragmentos cuentan capas;
- la variedad entre 100 jugadores;
- que todo sale en inglés.
