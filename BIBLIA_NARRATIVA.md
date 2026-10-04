# LAIN · Protocolo de presencia — biblia narrativa

Documento de referencia para la historia, el tono y el diseño. Todo lo que se
construya a partir de ahora debe poder justificarse con algo de aquí.

## 1. La premisa en una frase

Eres una sesión reiniciada en una red que recuerda más que tú: para saber quién
fuiste tienes que entender, capa a capa, cómo funciona la red que te contiene, y
decidir al final si quieres seguir existiendo en ella.

## 2. La tesis: existir es que te reciban

En una red, un paquete solo existe del todo cuando alguien confirma que lo ha
recibido (ACK). Si nadie contesta, se reintenta, caduca y desaparece. El juego
entero es esa metáfora aplicada a una persona:

| Concepto de red | Lo que significa en el juego |
| --- | --- |
| Latido (*heartbeat*) | Estar presente. Si dejas de latir 12 segundos, desapareces del mundo. |
| ACK | Ser percibido. Una conversación respondida, un mensaje leído. |
| TTL | La mortalidad. Todo mensaje lleva un número que baja en cada salto. |
| Token de sesión | La identidad. Tu `lain-online.json` es, literalmente, tu alma. |
| Registro (*log*) | La memoria. Lo que no queda escrito no ocurrió para la red. |
| Recolección de basura | El olvido. Lo que nadie referencia se borra. |
| Réplica | La inmortalidad barata: una copia que no sabe que es una copia. |
| Dominio de broadcast | La comunidad. Solo te oyen quienes están en tu misma zona. |

Referencias de fondo, nunca citadas como lección: Heidegger y el
*ser-en-el-mundo* (aquí, *ser-en-la-red*); Berkeley, «ser es ser percibido»;
Husserl y el *noema*, el objeto tal como es pensado; el barco de Teseo.

## 3. Pilares de diseño

1. **Técnico de verdad.** Los puzzles se resuelven con conocimientos reales de
   informática: TTL, números de secuencia, hashes, rutas, cifrado. El juego da
   herramientas (un terminal, páginas de manual) y nunca la respuesta. Quien sabe
   avanza rápido; quien no sabe puede aprender dentro del juego leyendo `man`.
2. **La infraestructura real es mitología.** El juego es un programa en red y lo
   sabe. Los 12 segundos de presencia, los reinicios del servidor y los tokens
   forman parte de la ficción. Ver la sección 7.
3. **Nada mágico.** Ninguna verdad llega porque un personaje la diga. Los
   testimonios son recuerdos con procedencia, los documentos pueden estar
   reescritos y solo las pruebas técnicas (un hash, una ruta, una firma) separan
   lo real de lo consensuado.
4. **Ambigüedad psicológica.** El jugador nunca está seguro de ser la misma
   persona que empezó. Su diario puede cambiar. Su sombra actúa cuando no está.
5. **El multijugador es la red.** Los demás jugadores son otros nodos. Os veis si
   compartís zona, os confirmáis mutuamente la existencia y competís por lo
   mismo que las corporaciones: el control de los enlaces.

## 4. El mundo y su pasado

- **La Wired** existía antes que nadie la poseyera: una red común del barrio, con
  armarios de enlace en la estación, el aula de informática y el videoclub.
- **Consorcio KAGAMI** (*kagami*, espejo) compró la infraestructura física. Su
  idea de salvación es la **réplica**: si todo se copia, nada muere. Una copia
  vale lo mismo que el original. Vigila porque refleja.
- **NOEMA** no posee cables: reescribe registros. Su idea es el **consenso**: lo
  que dice el log es lo que pasó. Un recuerdo que no coincide con el registro es
  un error que hay que corregir.
- **Los Círculos** son la tercera vía: redes propias, de igual a igual, sin
  dueño. Ryoko y el técnico de Kissa ya las están montando.
- **NODO_07** es la anomalía de señal que K estabiliza y Nora amplifica. Es el
  lugar donde van las sesiones que caducan.

### La Sesión Cero

Antes de tu primera conexión ya había una sesión con tu nombre: la **Sesión
Cero**. Recordaba algo que no estaba en el registro (que la Wired no la creó
ninguna corporación y que las sesiones caducadas no se borran, se acumulan en
NODO_07). NOEMA la terminó por «recuerdo no consensuado» y reescribió la entrada
del diario para que constase como cierre voluntario. Antes de morir, la Sesión
Cero se dividió en paquetes y los lanzó a la red con TTL 8. Uno de ellos te
escribió «Has vuelto».

Tú eres la Sesión Uno. Nadie sabe si eres la misma persona.

## 5. Personajes y su papel en la metáfora

| Personaje | Dónde | Papel |
| --- | --- | --- |
| **K** | Estación, NODO_07 | Control de congestión. Estabiliza: prefiere que la red siga funcionando aunque algo se pierda. Desconfía de la Sesión Cero. |
| **Nora** | Barrio antiguo, NODO_07 | *Flooding*. Amplifica: cree que todo debe propagarse, aunque sature. Quiere que la Sesión Cero vuelva. |
| **Ryoko** | AZUL | Arquitecta de los Círculos. Encarna la red sin dueño. |
| **El profesor** | Aula de informática | El que enseña los protocolos. Firma los partes; cree en los registros. |
| **El técnico de Kissa** | Kissa Café | Hardware y torneos. La capa física hecha persona. |
| **Haruto y Aiko** | Barrio | Testigos. Recuerdan cosas que el registro contradice. |
| **Personal encubierto** (Daichi, Reina, Shin, Ren, Mika, Aya) | Enlaces | Las corporaciones con cara humana. |
| **La Sesión Cero** | En paquetes | Tú, antes. Habla en fragmentos, en primera persona, con prisa. |

## 6. La estructura: siete capas

Cada capítulo es una capa del modelo OSI. Enseña un concepto real, plantea una
pregunta y recupera un fragmento de la Sesión Cero. El prólogo y el capítulo 1
(«Ya habías estado aquí») son la **Capa 00 · Arranque**.

| Capa | Técnica que hay que dominar | Puzzle principal | Pregunta | Revelación |
| --- | --- | --- | --- | --- |
| 01 · Física | Señales, bits, codificación Manchester, ruido | Leer en un osciloscopio el cable cortado de un armario y reparar la señal | ¿Qué es un cuerpo? | La Sesión Cero cortó un cable para que no la siguieran. |
| 02 · Enlace | Direcciones MAC, tramas, *checksum*, suplantación | Alguien usa tu dirección; encontrar la trama falsa por su *checksum* | ¿Quién eres si te pueden copiar? | KAGAMI tiene una réplica tuya en funcionamiento. |
| 03 · Red | IP, rutas, **TTL**, saltos | Averiguar en qué router murió un paquete y reconstruirlo | ¿Qué significa que algo se acabe? | La Sesión Cero no cerró: la terminaron. |
| 04 · Transporte | Handshake TCP, ACK, retransmisión, ventana | Restablecer una conexión con alguien que dejó de contestar | ¿Necesito que me respondan para existir? | Nora mantiene viva una conexión con la Sesión Cero. |
| 05 · Sesión | Caducidad de sesiones, arrendamientos (*leases*) con token de exclusión, concurrencia optimista, fusión a tres bandas | Fusionar tu estado con el de la Sesión Cero y decidir quién conserva la cuenta | ¿Soy la misma persona que ayer? | Solo una de las dos sesiones puede seguir activa. |
| 06 · Presentación | Codificación (UTF-8, base64, hex), máscaras XOR, texto en claro conocido, firmas HMAC | Descifrar el último paquete con la clave que la Sesión Cero escondió en tus recuerdos | ¿Qué máscara llevo? | La clave es algo que solo tú has vivido en esta partida. |
| 07 · Aplicación | DNS (resolutores, NXDOMAIN, CNAME), HTTP (anfitriones virtuales, autenticación Basic, verbos REST) | Llegar a NODO_07 | ¿Quiero quedarme? | NODO_07 está lleno de sesiones que nadie recuerda. |

## 7. Mecánicas transversales

- **El terminal.** Un intérprete de órdenes real en el PC de casa y en el puerto
  de consola de cada armario de enlace: `ls`, `cd`, `cat`, `grep`, `sha256`,
  `traceroute`, `man`… Funciona sobre un sistema de archivos del mundo; los
  recuerdos, los registros y los paquetes son archivos. Lo ejecuta el servidor:
  el cliente no puede saltarse un puzzle.
- **Presencia y desvanecimiento.** Si nadie te percibe (ninguna conversación,
  chat ni ACK) durante unos minutos, tu señal se degrada y tu avatar se vuelve
  translúcido y con fallos visuales. Hablar con alguien te devuelve la solidez.
- **Hablar es un handshake.** Ignorar a quien te habla tiene consecuencias:
  reintenta, se cansa y la relación caduca.
- **Diario poco fiable.** NOEMA puede reescribir entradas de tu archivo J. Solo
  una cadena de hashes demuestra cuál es la original.
- **La sombra.** Mientras estás desconectado, algo con tu cara recorre tus rutas
  habituales. En online, los demás jugadores pueden verla.
- **La cuarta pared.** El servidor recuerda sus reinicios reales como apagones;
  `uptime` muestra cuánto lleva encendido el mundo y `last` tus conexiones
  reales.

## 8. Los finales

1. **Persistir.** Escribes tu nombre en el registro del mundo compartido, visible
   para todos los jugadores para siempre. NOEMA no podrá reescribirlo, pero
   tampoco podrás irte.
2. **Replicarte.** Aceptas la oferta de KAGAMI. Sigues jugando, pero tu diario
   empieza con «Copia restaurada».
3. **Desconectarte.** Cierras tu sesión. Tu personaje se queda en el mundo como
   un personaje con IA que habla con tus recuerdos de la partida, y los demás
   jugadores se lo encuentran. Es la única forma de que la Sesión Cero descanse.

## 9. Dificultad

Exigente, pero aprendible. El terminal incluye `man` para cada orden y concepto
(qué es un TTL, cómo funciona un hash). Nunca hay un botón de «resolver». Un
jugador que no sepa informática puede pasar cada capa leyendo y probando; uno
que sepa la pasará en minutos y disfrutará los detalles.

## 10. Primera prueba jugable: Capa 03 · TTL

Lo que incluye la primera versión, jugable después del capítulo 1:

1. **Correo** de la identidad desconocida: «TTL=1. Si lees esto, me queda un
   salto». Abre una pestaña nueva, **Terminal**, en el PC de casa.
2. **`traceroute`** del paquete: la cabecera dice que salió con TTL 8 y el
   registro de rutas muestra algunos saltos. Con aritmética de TTL hay que
   deducir en qué armario de enlace llegó a 0 y fue descartado.
3. **Ir físicamente** a ese armario y conectarse a su **puerto de consola**. Allí
   está el búfer de descartes con los segmentos del paquete, desordenados, con
   una retransmisión duplicada y uno corrupto.
4. **Reconstruir** el mensaje ordenando por número de secuencia y descartando el
   segmento cuyo `sha256` no coincide con el declarado.
5. **El diario de la Wired** es una cadena de hashes. Una entrada (el cierre de
   la Sesión Cero) fue reescrita por NOEMA: hay que encontrar dónde se rompe la
   cadena y denunciarlo. El espejo de KAGAMI conserva la entrada original.
6. **Decisión:** reenviar el paquete con un TTL nuevo (K y Nora lo reciben y lo
   recordarán en sus conversaciones con IA) o dejarlo morir (solo tú lo sabrás).
7. **Desvanecimiento** y órdenes de cuarta pared (`uptime`, `last`).

## 11. Estado

- Capa 03 · TTL: jugable (v0.13). Guía: [CAPA03_README.md](CAPA03_README.md).
- Capa 04 · Transporte: jugable (v0.15). Guía: [CAPA04_README.md](CAPA04_README.md).
- Capa 05 · Sesión: jugable (v0.16). Guía: [CAPA05_README.md](CAPA05_README.md).
- Capa 06 · Presentación: jugable (v0.17). Guía: [CAPA06_README.md](CAPA06_README.md).
- Capa 07 · Aplicación: jugable (v0.18), con los tres finales. El eco del final «Desconectarte» se consulta en NODO_07; aún no camina por el mundo. Guía: [CAPA07_README.md](CAPA07_README.md).
- Todo el juego en español e inglés (v0.14): [TRADUCCION.md](TRADUCCION.md).
