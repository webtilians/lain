# LAIN · Capa 05 · Sesión

Rama `experiment/layer-05-session`. Tercera capa del **Protocolo de
presencia** (ver [BIBLIA_NARRATIVA.md](BIBLIA_NARRATIVA.md)). Empieza al
decidir qué hacer con la conexión de la [Capa 04](CAPA04_README.md). Se activa
con `LAIN_LAYER_FIVE=1`, que ya ponen el lanzador, `serve-city.ps1` y el
servidor online.

**La pregunta:** ¿soy la misma persona que ayer?

## Qué hay que hacer (sin destripar)

1. En el PC de casa llega el correo **«Dos sesiones, una cuenta»**: NODO_07 ha
   encontrado una sesión caducada con tu nombre, la Sesión Cero. Tu cuenta solo
   admite una sesión activa. `sessions` enseña las dos, con su versión y el
   arrendamiento (*lease*) vigente.
2. El archivo de sesiones se monta en la consola del armario del andén
   (estación). Allí están `base.json`, el último estado que compartíais, y lo que
   cambió cada sesión después: `s0.json` y `s1.json`.
3. Fusiona campo a campo con `merge <campo> <base|s0|s1>`, como una **fusión a
   tres bandas** de git (`man merge`). Si un campo cambió en una sola sesión, ese
   cambio se queda. Si cambió de forma distinta en las dos, eliges tú.
4. Escribe la fusión con `commit version=<n> token=<n>`:
   - la versión debe ser la siguiente a la actual (`man version`, concurrencia
     optimista);
   - el token debe ser el del arrendamiento vigente, no el antiguo de la Sesión
     Cero (`man fencing`).
5. Decide quién conserva la cuenta:
   - **quedártela** (`lease s1`);
   - **devolvérsela a la Sesión Cero** (`lease s0`): el mundo te llama sesión 0;
   - **borrar su archivo** (`expire s0`).

   Nora y K lo recordarán en sus conversaciones.

Cada jugador tiene su propio archivo: otros cambios, uno o dos conflictos, otra
versión, otro token y otra palabra guardada, que abrirá la Capa 06. Todo sale
en español e inglés.

## Órdenes nuevas

`sessions` (o `sesiones`), `merge <campo> <base|s0|s1>` (o `fusionar`),
`commit version=<n> token=<n>` (o `confirmar`), `lease s1`, `lease s0`,
`expire s0` (o `caducar`) y los temas de `man`: sesion, lease, fencing,
version, merge, json.

## Cómo está construido

- `server/world_core/layer_five.py`: estado por jugador y archivo de sesiones
  generado a partir de su id. Incluye la regla de fusión a tres bandas, la
  comprobación de versión (compare-and-swap) y de token de exclusión, y las
  decisiones. Se engancha al terminal de la Capa 03 (mismo endpoint), como la
  Capa 04.
- Lo que confía la sesión 1 depende de cómo acabó la Capa 04: FIN, RST o
  keepalive.
- Los JSON se generan en el idioma con el que el jugador empezó la capa; los
  manuales y las respuestas siguen el idioma elegido en cada momento.
- Cliente: la esquina y la pestaña Terminal muestran la capa más reciente. El PC
  enseña los correos de todas las capas, empezando por el más nuevo.

## Validación

`tests/test_layer_five.py` resuelve la capa entera leyendo solo la salida del
juego:
1. lee los tres JSON y aplica la regla de tres bandas;
2. saca versión y token de `sessions`;
3. comprueba que se rechazan el token antiguo, la versión repetida y una fusión
   que pierde un cambio;
4. confirma la fusión y devuelve la cuenta a la Sesión Cero.

También prueba que las decisiones exigen la fusión y solo ocurren una vez, el
borrado y la memoria de Nora, y que las órdenes solo funcionan en el andén. Por
último, comprueba la dependencia de la Capa 04, la variedad entre 120 jugadores
y que todo sale en inglés.
