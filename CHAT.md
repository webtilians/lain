# Sesión Cero · Un solo chat

Una crítica decía: *«que todo sea el mismo chat y que nunca sepas si estás hablando con
un NPC o con un jugador»*. Así funciona ahora.

## Cómo se vive

- **Cada zona tiene una conversación**: lo que se dice en un sitio lo leen todos los que
  están allí, jugadores y vecinos. Es el dominio de *broadcast* de la Malla: solo te
  oyen quienes comparten tu zona.
- **Nadie lleva etiqueta.** Los vecinos firman con su nombre de pila (Hideo, no Hideo
  Sakamoto), igual que firmaría un jugador. Cada mensaje llega al juego con una clave
  opaca, la misma clase de clave para todos; nunca con el identificador interno, así que
  ni mirando por dentro del juego se sabe quién es quién.
- **Los vecinos hablan en el chat:**
  - **Si los nombras**, contestan: «Hideo, ¿has visto a Ryoko?».
  - **Si estás solo en la zona** y preguntas algo al aire, contesta alguno de los que
    están allí. Si hay más gente, lo dejan para las personas.
  - **De vez en cuando dicen algo por su cuenta**: lo que hacen, lo que ven, lo que les
    preocupa (unos cuatro minutos por zona, con gente en ella).
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
  - quién contesta (`on_player_chat`: nombrados, o uno si estás solo y preguntas);
  - qué dice (`reply_text`, con el contexto del vecino, el jugador y las últimas líneas
    de la zona);
  - las frases por su cuenta (`ambient_tick`);
  - el hilo que espera el tiempo de escritura antes de publicar.

  Cada vecino espera 20 segundos entre una frase y otra, y como mucho contestan dos a
  la misma línea.
- `server/world_core/online.py`:
  - el chat de siempre, con `post_chat` para lo que dice el servidor;
  - `speaker_key`, la clave opaca de cada voz;
  - `recent_lines` y `zones_with_players`.
- `server/world_core/free_conversation.py`: la conversación con E también sale en el chat
  de la zona.
- `client/scripts/network/OnlinePresence.gd`: el chat enseña 6 líneas; no distingue a
  nadie porque no tiene cómo.
- Pruebas: `tests/test_zone_chat.py`.
