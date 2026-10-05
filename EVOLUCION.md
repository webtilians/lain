# Sesión Cero · La Malla evoluciona (propuesta de diseño)

> Estado: **en marcha**. Hechas la etapa 1, el Instituto de Física del Puerto y
> la convocatoria QB-01 ([INSTITUTO.md](INSTITUTO.md)), y la etapa 2, el vigía
> y los otros dos centros ([VIGIA.md](VIGIA.md)). Decisiones
> tomadas: se empieza por el Instituto; las convocatorias del vigía **entran
> solas** y se revisan después, borrando las que no gusten; el agente `kumo`
> tendrá **20 preguntas al día** por jugador.

## La idea en una frase

La Malla no está terminada: cada cierto tiempo aparece una **convocatoria** sobre
una tecnología nueva. Quien la estudia y supera su prueba **hace avanzar la red
para todos**, y algunas líneas de investigación acaban dándote herramientas
nuevas, la más grande de ellas tu propio **agente de IA** en el ordenador de casa.

Encaja con la tesis del juego: igual que un paquete solo existe si alguien lo
recibe, una tecnología solo llega a la Malla si alguien la entiende.

## 1. Los centros de investigación

Tres sitios nuevos de la Malla. Al principio se visitan **desde el terminal**,
como NODO_07 en la Capa 07 (con `curl` a su servidor). Más adelante, si va bien,
tendrán su escena 3D en el barrio.

| Centro | Dónde | Qué investiga |
|---|---|---|
| **Instituto de Física del Puerto** | `instituto.malla` | Física cuántica: qubits, medida, entrelazamiento, distribución cuántica de claves (BB84), por qué un ordenador cuántico rompería los Círculos. |
| **Laboratorio de Inteligencias** | `laboratorio.malla` | IA: tokens, contexto, herramientas, agentes. Ahí se construye el agente de IA del jugador. |
| **Archivo de Protocolos** | `archivo.malla` | Redes nuevas: QUIC, enrutamiento en malla, pruebas de conocimiento cero, criptografía poscuántica. |

Cada centro tiene un personaje responsable (un vecino nuevo o uno que ya
existe: Hideo Sakamoto, el profesor de ciencias, encaja con el Instituto) y su
propia web dentro del juego: convocatorias abiertas, artículos para estudiar y
un buzón para entregar resultados.

## 2. Las convocatorias: estudiar una tecnología

Una convocatoria es una **unidad de estudio** con tres partes, como una capa
pequeña:

1. **Estudiar**: artículos y páginas de `man` escritos para el juego.
2. **Experimentar**: un ejercicio en el terminal con números de tu propia partida
   (por ejemplo, simular BB84: tus bases, las del otro y el ruido de un espía).
3. **Demostrar**: entregar un resultado comprobable (una clave, un hash, una
   cifra, un programa del taller que pasa unas pruebas). Nada de preguntas tipo
   test: lo mismo que el resto del juego, conocimiento real que se demuestra
   haciendo.

Al superarla aparece una cinemática corta («la Malla aprende…») y el
descubrimiento queda en el **registro del centro**, con tu nombre.

### Que la red avance para todos

Cada convocatoria tiene un **umbral colectivo**: cuando la superan, por ejemplo,
tres jugadores, la tecnología **entra en la Malla para todos**:
- órdenes nuevas en el terminal (por ejemplo, `qkd` tras BB84);
- cambios en el mundo (carteles, lo que comentan los vecinos, la cinemática
  «la Malla evoluciona», que se ve una vez);
- nuevas convocatorias que dependen de esa (un árbol de tecnologías).

Así el multijugador vuelve a ser la red: el progreso de cada uno empuja el de
los demás.

## 3. Seguir el ritmo de la tecnología real

Aquí está tu idea de que una IA «recoja llamadas» sobre tecnología nueva. Lo
haría así, con **una persona siempre al mando**:

1. **El vigía** (en el servidor, una vez al día): lee titulares de fuentes
   públicas sobre redes, IA, criptografía y física (por ejemplo arXiv,
   Hacker News, los RFC nuevos del IETF) y le pide a Gemini que proponga como
   mucho **una convocatoria por semana**: el tema, por qué importa y un esbozo
   de las tres partes.
2. **Entran solas**: la convocatoria se publica en el juego sin esperar a nadie.
   El panel del servidor (`-Panel`) las lista y permite **borrar** las que no
   gusten.
3. **Se escribe la convocatoria**: los artículos los redacta la IA y los
   repasamos nosotros; el ejercicio y su comprobación se programan y prueban como
   cualquier capa, porque una prueba que no se puede verificar no vale.

Para que entren solas sin romper nada, la IA solo escribe los textos. El
ejercicio es siempre uno de cinco tipos que el código rellena y comprueba, así
que toda convocatoria tiene solución. Lo que la IA se invente se ve en el panel
y se borra (así quedó hecho: [VIGIA.md](VIGIA.md)).

Coste: una llamada al día a Gemini cabe de sobra en el plan gratuito.

## 4. La IA entra en la Malla: tu agente

La línea del **Laboratorio de Inteligencias** termina con algo tuyo: un agente
de IA en el ordenador de casa (Kumo). Se gana por etapas:

1. **Tokens y contexto**: entender qué recibe un modelo y qué no. El texto de la
   terminal del arranque ya lo cuenta: es el mismo concepto.
2. **Herramientas**: en el taller de código, escribes las reglas de tu agente
   («si te piden leer un archivo, usa `cat`; si es un hash, usa `sha256`») como
   un programa pequeño que tiene que pasar unas pruebas.
3. **El agente**: se abre la orden `kumo <pregunta>`. Responde con IA de verdad
   (Gemini), puede leer tus archivos y ejecutar las órdenes que le has permitido,
   y te explica lo que ves.

Reglas para que no rompa el juego:
- **No resuelve capas**: no ve la solución, solo lo que tú ves. Al pedirle algo
  de una capa abierta, te da pistas, no el resultado, igual que los expertos.
- **Límite diario** por jugador, para no gastar la cuota de la IA.
- Las herramientas que use son las que **tú** programaste: cuanto mejor lo
  hagas, más útil es.

En la historia, KAGAMI y NOEMA ya usan agentes. El tuyo es el primero que no
pertenece a ninguna corporación, igual que los Círculos.

## 5. Física cuántica: el arco que une lo que ya existe

Una línea de investigación con historia propia:

1. **El qubit**: superposición y medida, con un simulador de un qubit en el
   terminal (`qubit h`, `qubit medir`).
2. **BB84**: distribuir una clave con fotones; si alguien escucha, el ruido lo
   delata. Ejercicio: detectar al espía por la tasa de error.
3. **La amenaza**: el Instituto descubre que KAGAMI construye un ordenador
   cuántico. Con el algoritmo de Shor, los intercambios Diffie-Hellman de los
   Círculos dejarían de ser secretos.
4. **La respuesta**: el Archivo de Protocolos estudia criptografía poscuántica
   (un esquema de juguete basado en retículos). Cuando la comunidad lo
   consigue, los Círculos de dos pasan a usar claves poscuánticas: `circulo`
   cambia para todos.

Así la física cuántica no es un añadido: protege algo que los jugadores ya
construyeron juntos.

## 6. Plan por etapas

| Etapa | Qué incluye | Tamaño |
|---|---|---|
| 1 | El Instituto en el terminal + la primera convocatoria (el qubit y BB84), con registro y umbral colectivo | como una capa |
| 2 | El vigía de tecnología y la aprobación en el panel | pequeño |
| 3 | El Laboratorio de Inteligencias y el agente `kumo`, con su límite diario | grande |
| 4 | El arco cuántico completo y los Círculos poscuánticos | como dos capas |
| 5 | Escenas 3D de los centros en el barrio | grande (arte) |
