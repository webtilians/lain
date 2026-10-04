# LAIN · Capa 07 · Aplicación

Rama `experiment/layer-07-application`. Última capa del **Protocolo de
presencia** (ver [BIBLIA_NARRATIVA.md](BIBLIA_NARRATIVA.md)) y final de la
historia. Empieza al decidir qué hacer con las caras de la
[Capa 06](CAPA06_README.md). Se activa con `LAIN_LAYER_SEVEN=1`, que ya ponen el
lanzador, `serve-city.ps1` y el servidor online.

**La pregunta:** ¿quiero quedarme?

## Qué hay que hacer (sin destripar)

1. En el PC de casa llega un correo de Nora: **«NODO_07»**. Nunca ha podido
   entrar. NODO_07 no tiene armario: se llega desde cualquier terminal, hablando
   su protocolo.
2. **DNS.** `dig nodo07.wired` devuelve NXDOMAIN: NOEMA borró el nombre de su
   servidor. Pero la zona `wired` tiene más servidores de nombres (`man dns`,
   `man dig`). Uno guarda la dirección real; otro responde con una copia.
3. **HTTP.** Conectar por dirección no basta. El servidor atiende varios nombres
   y responde 421 si no le dices a cuál hablas (`man host`, `man http`). Con el
   nombre correcto pide autenticación Basic: 401 (`man auth`, `man curl`).
4. **Dentro.** `/sesiones` muestra las sesiones que nadie recuerda, incluidas las
   de otros jugadores del mundo. La Sesión Cero guarda allí sus tres últimos
   fragmentos.
5. **El final.** Se elige con un método HTTP:
   - **Persistir** (`PUT /registro/<tu nombre>`): tu nombre entra en un registro
     encadenado por hashes que ven todos los jugadores. Nadie puede borrarlo,
     tampoco tú.
   - **Replicarte** (`POST /replicas` en el espejo de KAGAMI): sigues jugando,
     pero `~/diario` empieza con «Copia restaurada» y `whoami` lo dice.
   - **Desconectarte** (`DELETE /sesiones/<tu sesión>`): la Sesión Cero
     descansa. Lo que viviste queda en `/ecos/<tu nombre>` para los demás.

   Nora y K lo recordarán en sus conversaciones.

Cada jugador tiene su propia dirección de NODO_07, su espejo y sus ids de
sesión. La clave es la palabra de la Capa 05. Todo sale en español e inglés.

## Órdenes nuevas

`dig [@servidor] <nombre> [A|NS|CNAME|TXT]` (o `nslookup`) y `curl` con `-i`,
`-v`, `-X MÉTODO`, `-H "Cabecera: valor"`, `-u nombre:clave`,
`--resolve nombre:80:dirección` e `-I`. Temas de `man`: dns, dig, http, curl,
host, auth.

## Cómo está construido

- `server/world_core/layer_seven.py` contiene:
  - tres zonas DNS (NOEMA, KAGAMI y los Círculos) con registros A, CNAME, NS y
    TXT;
  - un cliente HTTP con anfitriones virtuales, autenticación Basic, códigos de
    estado y verbos REST;
  - las tres decisiones.

  Se engancha al terminal de la Capa 03 (mismo endpoint) y funciona en
  cualquier terminal, no solo en el PC de casa.
- El registro de quienes persisten es una tabla compartida por todo el mundo
  (`layer_seven_registry`). Cada entrada guarda el hash de la anterior. Los ecos
  se construyen con las decisiones reales de cada jugador en las capas 03 a 06.
- `dig` y `curl` no pasan por la traducción del terminal: la capa traduce el
  cuerpo de cada respuesta y deja intactos cabeceras, direcciones y base64.
- Cliente: la esquina y la pestaña Terminal muestran la capa más reciente. Al
  terminar, los fragmentos llegan a 7/7.

### Lo que aún no está

La biblia describe el eco como un personaje con IA que camina por el mundo y
habla con tus recuerdos. Por ahora el eco se consulta en NODO_07
(`GET /ecos/<nombre>`) y responde con lo que ese jugador vivió. Tampoco existe
todavía un diario de personaje fuera del terminal: «Copia restaurada» aparece en
`~/diario` y en `whoami`.

## Validación

`tests/test_layer_seven.py` resuelve la capa entera leyendo solo la salida del
juego:
1. pregunta a cada servidor de nombres de la zona hasta encontrar la dirección;
2. recorre 421, 401 y 200 con la cabecera Host y la autenticación Basic;
3. comprueba que `-v` enseña la clave en base64;
4. lee los fragmentos y persiste, con la entrada encadenada en `/registro`.

También prueba el espejo de KAGAMI y la réplica con su diario, y el eco de otro
jugador. Comprueba que desconectarse deja descansar a la Sesión Cero, los
errores de `dig` y `curl`, la variedad de direcciones entre 100 jugadores y que
todo sale en inglés.
