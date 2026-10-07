# Sesión Cero · Dirección de arte

Elegida: **anime** (la fila D de los bocetos). Cabezas grandes, ojos con brillos,
pelo en mechones, sombras de corte limpio y una luz de neón de color en el borde de
cada personaje: verde fósforo para Sesión Cero, rosa para Ryoko, rojo para K y la
luz cálida de una lámpara para el profesor.

## Retratos en las conversaciones

Al hablar con un personaje que tiene retrato, su dibujo aparece a la izquierda y el
texto se aparta a la derecha, como en una novela visual. Entra con un pequeño
deslizamiento al empezar la conversación, no en cada respuesta.

- Los retratos están en `client/art/portraits/` como SVG (570×720, el origen entre
  los ojos, sin fondo). Godot los importa como textura.
- `client/scripts/ui/EventDialog.gd` (`PORTRAITS`) dice qué retrato lleva cada
  nombre: el que muestra el diálogo, en los dos idiomas («Profesor» y «Teacher»).
  Para añadir uno: el SVG en esa carpeta y una línea en `PORTRAITS`.
- Al dibujar un SVG para el juego, nada de filtros (desenfoques, brillos) ni texto:
  el importador de Godot no los dibuja. Degradados y recortes sí.
- Prueba: `client/tools/test_portraits.gd`.

Hay retrato de Ryoko y del profesor. Faltan Sesión Cero y K (ya dibujados en los
bocetos) y los vecinos.

## Lo siguiente

1. La ventana de conversación con el estilo de los bocetos: caja abajo, nombre en
   una etiqueta de color y las respuestas como botones redondeados.
2. Varias expresiones por personaje (desconfiada, sonriendo, seria).
3. En el mundo: sombreado de anime para los personajes 3D (tonos planos y contorno).
