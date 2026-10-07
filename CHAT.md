# Sesión Cero · Un solo chat

Una crítica decía: *«que todo sea el mismo chat y que nunca sepas si estás hablando con
un NPC o con un jugador»*. Así funciona ahora.

## Cómo se vive

- **Cada zona tiene una conversación**: lo que se dice en un sitio lo leen todos los que
  están allí, jugadores y vecinos. Es el dominio de *broadcast* de Indara: solo te
  oyen quienes comparten tu zona.
- **Nadie lleva etiqueta.** Los vecinos firman con su nombre de pila (Hideo, no Hideo
  Sakamoto), igual que firmaría un jugador. Cada mensaje llega al juego con una clave
  opaca, la misma clase de clave para todos; nunca con el identificador interno, así que
  ni mirando por dentro del juego se sabe quién es quién.
- **Solo hablan los vecinos que tienes cerca**: los que ves en pantalla, a menos de unos
  14 metros. Uno que está en la otra punta del barrio no se mete en tu conversación.
  - **Si los nombras**, contestan: «Hideo, ¿has visto a Ryoko?».
  - **Si estás hablando con uno**, sigue contestándote él aunque no repitas su nombre
    (hasta dos minutos sin hablar, o hasta que te alejes de él).
  - **Si estás solo en la zona** y preguntas algo al aire, contesta el que tienes más
    cerca. Si hay más gente, lo dejan para las personas.
  - **De vez en cuando dicen algo por su cuenta**, solo si hay alguien cerca para oírlo:
    lo que hacen, lo que ven, lo que les preocupa (unos cuatro minutos por zona).
- **Cada frase sale unos segundos sobre la cabeza de quien la dice**, sea un jugador, un
  vecino o tú, así se ve quién habla.
- **Tardan lo que tarda una persona en escribir** (entre 2 y 7 segundos, según lo largo
  de la respuesta), nunca al instante.
- **Hablar con alguien (E) también es en voz alta**: lo que le escribes a un vecino y lo
  que te contesta sale en el chat de la zona, y los demás lo leen.
- **Recuerdan lo que se les dice** en el chat, como en una conversación.

## Con la IA y sin ella

Con la IA de los personajes (en el servidor, Gemini) los vecinos contestan con su propia
voz, sabiendo quién les habla y lo último que han dicho esa persona y los vecinos. Lo que
otros jugadores hablan entre ellos nunca le llega a la IA.

Sin IA:
- solo contestan si los nombras, con una frase corta de alguien ocupado («Ni idea, la
  verdad», «¿Me lo dices a mí?»);
- no contestan preguntas al aire ni hablan por su cuenta.

Una frase de relleno repetida delataría enseguida que es una máquina; callar, no.

## Cómo está hecho

- `server/world_core/zone_chat.py`:
  - quién contesta (`on_player_chat`, entre los que están cerca según `around`: nombrados,
    el que ya te hablaba, o el más cercano si estás solo y preguntas);
  - qué dice (`reply_text`, con el contexto del vecino, el jugador y las últimas líneas
    de la zona);
  - las frases por su cuenta (`ambient_tick`);
  - el hilo que espera el tiempo de escritura antes de publicar.

  Entre dos frases por su cuenta, un vecino espera 20 segundos; entre dos respuestas, 4.
  Como mucho contestan dos a la misma línea. Un juego antiguo, que no dice quién tiene
  cerca, oye a toda la zona como antes.
- `server/world_core/online.py`:
  - el chat de siempre, con `post_chat` para lo que dice el servidor;
  - `speaker_key`, la clave opaca de cada voz (también va con cada jugador y cada vecino
    visibles, para poner la frase sobre su cabeza);
  - `near_residents` y `residents_near_players`: los vecinos que cada jugador tiene cerca;
  - `recent_lines` y `zones_with_players`.
- `server/world_core/free_conversation.py`: la conversación con E también sale en el chat
  de la zona.
- `client/scripts/network/OnlinePresence.gd`: el chat con scroll; dice al servidor qué
  vecinos ve el jugador (`near_residents`) y pone cada frase nueva sobre la cabeza de
  quien la dijo (`_bubble`).
- Pruebas: `tests/test_zone_chat.py` y `client/tools/test_chat_box.gd`.
