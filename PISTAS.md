# LAIN · Pistas

Cada paso de cada capa tiene tres pistas: **la idea**, **el método** y, por
último, **los valores de tu propia partida**. Al llegar a un paso nuevo se
empieza otra vez por la primera.

## Cómo se piden

1. **`pista` en cualquier Terminal.** Nora te da la primera pista (la idea) y
   te dice **quién sabe más**: alguien del barrio cuyo oficio tiene que ver con
   esa capa. Si otros jugadores ya superaron la capa, también salen sus nombres
   para que les preguntes por el chat; nunca su solución.
2. **Ve a hablar con esa persona** (E junto a ella). En la conversación aparece
   una opción nueva: «Me han dicho que sabes de esto. ¿Me ayudas con la Capa…?».
   Te explica el método (pista 2). Si vuelves a preguntar, te da los valores de
   tu partida (pista 3).
3. **`pista` te recuerda** después lo que te contó, para releerlo.

`pista 3` pide ayuda con la Capa 03 en lugar de la actual. Quien te ayudó lo
recuerda en sus conversaciones.

## Quién sabe de cada capa

| Capa | Quién | Dónde | Por qué |
|---|---|---|---|
| 01 · Física | Jun Saito, alumno del taller | aula de informática | sabe de electrónica: cables, señales y osciloscopios |
| 02 · Enlace | Yasuo Ueda, coleccionista | librería | colecciona conmutadores y tarjetas de red antiguas |
| 03 · TTL | Osamu Kaneko, empleado | estación | se sabe todas las rutas y cuántos saltos tiene cada una |
| 04 · Transporte | Haruto Senda, cartero | barrio | sabe lo que es esperar un acuse de recibo |
| 05 · Sesión | Makoto Ishikawa, encargado | videoclub | lleva préstamos que caducan y copias que se pisan |
| 06 · Presentación | Natsumi Honda, estudiante | Kissa Café | escribe en clave y le encantan los cifrados |
| 07 · Aplicación | Takeshi Uno, ayudante de informática | aula de informática | mantiene los servidores del aula |

Los expertos son vecinos fijos de cada sitio, así que siempre están allí. Su
respuesta es el texto exacto de la pista, no una paráfrasis de la IA, para que
los valores de la pista 3 lleguen sin errores.

Si un mundo no tiene vecinos (partidas locales antiguas), `pista` sube las tres
pistas en el propio Terminal, como antes.

## Cómo está hecho

- `server/world_core/hints.py`: los pasos y sus pistas, `EXPERTS`,
  `dispatch` (el Terminal), `expert_layer` y `consult` (el experto).
- `server/world_core/player_conversation.py`: la opción `ASK_HINT` aparece
  solo con el experto al que te mandó `pista`, y su respuesta se guarda como
  cualquier otro turno de conversación.
- `client/scripts/world/ActorInteractable.gd` muestra esa opción la primera.
- Pruebas: `tests/test_hints.py` sigue cada pista 3 y comprueba que resuelve de
  verdad su paso.
