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

Hay retrato de Ryoko, del profesor y de K. Falta Sesión Cero (dibujada en los
bocetos; su sitio natural son las cinemáticas de sus fragmentos) y los vecinos.

## Lo siguiente

1. Varias expresiones por personaje (desconfiada, sonriendo, seria).
2. En el mundo: sombreado de anime para los personajes 3D (tonos planos y contorno).
