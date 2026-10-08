# Sesión Cero · Dirección de arte

Elegida: **anime** (la fila D de los bocetos). Cabezas grandes, ojos con brillos,
pelo en mechones, sombras de corte limpio y una luz de neón de color en el borde de
cada personaje: verde fósforo para Sesión Cero, rosa para Ryoko, rojo para K y la
luz cálida de una lámpara para el profesor.

## La ventana de conversación

Como en una novela visual: la escena se sigue viendo detrás, el texto va en una caja
a lo largo de la parte de abajo, el nombre de quien habla en una etiqueta inclinada
de su color, la narración más tenue que lo que se dice («…», o “…” en inglés) y las
respuestas como botones redondeados encima de la caja, a la derecha. El texto
aparece como si se escribiera, rápido. Todo en `client/scripts/ui/EventDialog.gd`.

## Retratos en las conversaciones

Al hablar con un personaje que tiene retrato, su dibujo aparece a la izquierda y el
texto empieza a su derecha. Entra con un pequeño deslizamiento al empezar la
conversación, no en cada respuesta.

- Los retratos están en `client/art/portraits/` como SVG (570×720, el origen entre
  los ojos, sin fondo). Godot los importa como textura.
- `client/scripts/ui/EventDialog.gd` (`PORTRAITS`) dice qué retrato lleva cada
  nombre: el que muestra el diálogo, en los dos idiomas («Profesor» y «Teacher»).
  `ACCENTS` da el color de cada uno. Para añadir uno: el SVG en esa carpeta y una
  línea en `PORTRAITS` y otra en `ACCENTS`.
- Al dibujar un SVG para el juego, nada de filtros (desenfoques, brillos) ni texto:
  el importador de Godot no los dibuja. Degradados y recortes sí.
- Prueba: `client/tools/test_portraits.gd`.

## Expresiones

Cada frase del prólogo dice con qué cara se dice (`mood` en la respuesta del
servidor; `PROFESSOR_MOODS` y `RYOKO_MOODS` en `server/world_core/prologue.py`). El
juego muestra `<retrato>_<cara>.svg` si existe y, si no, el retrato de siempre; la
cara cambia sin que el retrato vuelva a entrar.

- Ryoko: la de siempre (desconfiada), `sonrie`, `seria`.
- El profesor: el de siempre (cansado), `sorpresa`, `serio`, `sin_gafas`.

Una cara nueva es una copia del retrato con otros ojos, cejas y boca. Un test
comprueba que toda cara que pide una frase está dibujada.

Hay retrato de Ryoko, del profesor y de K. Falta Sesión Cero (dibujada en los
bocetos; su sitio natural son las cinemáticas de sus fragmentos) y los vecinos.

## El aspecto anime en el mundo

`client/scripts/art/AnimeLook.gd`, aplicado por `GraphicsDirector` a cada escena y a
quien llega después:

- **Las personas** con sombreado anime: luz con corte limpio, brillo marcado y una luz
  de color en el borde.
- **Los escenarios** conservan su luz pintada (el corte limpio en suelos y paredes les
  quitaba la luz de las lámparas).
- **Contorno de tinta** en siluetas y aristas: una pasada a pantalla completa sobre
  profundidad y normales (`client/shaders/anime_outline.gdshader`, solo Forward+).
- **Color** algo más vivo, sombras de tono medio violeta y más brillo en las luces.
- **F9** cambia entre anime y realista; se guarda en `user://graphics10.cfg`.
- Prueba: `client/tools/test_anime_look.gd`.

## Lo siguiente

1. Personajes 3D anime hechos con VRoid Studio (ver `VROID.md`): Ryoko y el profesor ya
   están; siguen Haruto y K.
2. Caras para K y para las conversaciones libres (según lo que diga la IA).
