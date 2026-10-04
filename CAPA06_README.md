# LAIN · Capa 06 · Presentación

Rama `experiment/layer-06-presentation`. Cuarta capa del **Protocolo de
presencia** (ver [BIBLIA_NARRATIVA.md](BIBLIA_NARRATIVA.md)). Empieza al
decidir quién conserva la cuenta en la [Capa 05](CAPA05_README.md). Se activa
con `LAIN_LAYER_SIX=1`, que ya ponen el lanzador, `serve-city.ps1` y el
servidor online.

**La pregunta:** ¿qué máscara llevo?

## Qué hay que hacer (sin destripar)

1. En el PC de casa llega el correo **«Tres caras»**. El último paquete de la
   Sesión Cero ha llegado tres veces al enlace del videoclub, cada vez con una
   cara distinta. Una es suya, otra la ha reescrito NOEMA y la tercera la ha
   escrito la réplica de KAGAMI.
2. En la consola del armario del videoclub están las tres caras
   (`/var/spool/caras/a.pkt`, `b.pkt` y `c.pkt`). Cada una trae una cabecera en
   claro y una carga en base64 enmascarada con XOR. `base64 -d` enseña sus
   bytes (`man codificacion`, `man base64`).
3. Quita la máscara con `xor <archivo> <clave>` (`man xor`, `man mascara`). La
   clave no viaja con el paquete, pero hay dos caminos para encontrarla:
   - recordar la palabra que guardó la Sesión Cero en la Capa 05;
   - aprovechar que todos sus paquetes empiezan igual: texto conocido ⊕
     carga enmascarada = clave.
4. Compara la firma: `hmac <archivo> <clave>` contra `x-signature`
   (`man hmac`). Una de las caras se descifra con tu clave pero su firma ya no
   coincide. Otra solo encaja con una clave que no es la tuya.
5. Decide qué haces con las máscaras:
   - **publicar** la cara verdadera con su clave (`publish <cara>`): todos
     pueden comprobar la verdad, pero cualquiera puede hablar con su voz;
   - **responder a la réplica** con su propia clave (`reply <cara> <clave>`);
   - **guardártelo** (`keep`).

   Nora y K lo recordarán en sus conversaciones.

Cada jugador tiene sus propias caras: otro orden, otra clave de la réplica y
la palabra que guardó en la Capa 05. Todo sale en español e inglés.

## Órdenes nuevas

`base64 -d <archivo>`, `xor <archivo> <clave|0xHEX>`, `hmac <archivo> <clave>`,
`publish <cara>` (o `publicar`), `reply <cara> <clave>` (o `responder`),
`keep` (o `guardar`) y los temas de `man`: codificacion, base64, xor, mascara,
hmac.

## Cómo está construido

- `server/world_core/layer_six.py`: estado por jugador y tres caras generadas
  a partir de su id y de la palabra de la Capa 05. Incluye la máscara XOR de
  clave repetida y el HMAC-SHA256 recortado a 64 bits. La cara de NOEMA tiene
  los bytes cambiados sin la clave, así que conserva la firma antigua. La de la
  réplica está firmada con otra clave. Se engancha al terminal de la Capa 03
  (mismo endpoint).
- Las órdenes que enseñan bytes (`base64`, `xor`) no pasan por la traducción.
  Las caras se generan en el idioma con el que el jugador empezó la capa; los
  manuales y las respuestas siguen el idioma elegido en cada momento.
- Cliente: la esquina y la pestaña Terminal muestran la capa más reciente. El PC
  enseña los correos de todas las capas, empezando por el más nuevo.

## Validación

`tests/test_layer_six.py` resuelve la capa entera leyendo solo la salida del
juego:
1. saca la clave de cada cara con el texto conocido «Has vuelto.»;
2. separa las caras con `hmac`: la auténtica, la de NOEMA (misma clave, firma
   rota) y la de la réplica (otra clave, firma válida);
3. descifra la cara auténtica con la clave en hexadecimal y la publica.

También prueba responder a la réplica con su clave, que las decisiones exigen
descifrar y comprobar la firma y solo ocurren una vez, los mensajes de error y
la memoria de Nora y K. Por último, comprueba la variedad entre 120 jugadores y
que todo sale en inglés, incluido el texto conocido «You have returned.».
