# LAIN · Interiores 0.22

Rama `experiment/interiors-22`. Pasada visual a los once interiores: las seis
tiendas del barrio, el piso, la escuela, el aula de informática, la discoteca y
la estación. Solo cambia la presentación; las colisiones, los personajes, sus
rutas y el estado del mundo siguen igual.

## Qué cambia

- **Luz de verdad.** Cada sitio tiene sus propias lámparas, con su color y sus
  sombras:
  - videoclub, tienda, librería, escuela, aula y estación: fluorescentes fríos.
    El techo está recortado para la cámara isométrica, así que se ve la luz y no
    los tubos;
  - izakaya: farolillos de papel encendidos;
  - kissa: lámparas colgantes sobre las mesas;
  - recreativos: neones y el brillo de cada pantalla;
  - discoteca: focos de colores;
  - piso: lámpara de techo y luz cálida junto a la cama.

  Las luces de relleno de cada sala ya no parpadean como velas, y el ambiente es
  neutro en lugar de violeta.
- **Materiales de cada sitio:**
  - baldosas de vinilo o cerámica con juntas y desgaste;
  - madera clara (librería, izakaya, kissa);
  - moqueta con dibujo (recreativos);
  - paredes enlucidas y pintadas, con zócalo de color.
- **Atrezo:**
  - cintas VHS, productos y libros de colores en las estanterías;
  - carteles de verdad;
  - pantallas de recreativos encendidas;
  - noren y taburetes en la izakaya;
  - discos en la kissa;
  - buzón de devoluciones en el videoclub;
  - cajas de fruta en la tienda;
  - máquina de premios y cambiador en los recreativos;
  - plantas.
- **Calidad (F6):**
  - Ligera: sin sombras de las lámparas;
  - Equilibrada: sombras en las dos principales;
  - Alta: sombras en cuatro y reflejos del interior (sonda de reflexión).

## Cómo está hecho

- `client/scripts/art/InteriorDresser.gd` viste cada interior según su estilo.
  Todo cuelga de un nodo `InteriorDressing`, sin colisiones.
- `client/shaders/interior_floor.gdshader` proyecta baldosas o moqueta desde
  arriba, en coordenadas del mundo.
- `GraphicsDirector.gd` llama al vestidor después de los materiales y ajusta la
  luz de los interiores.
- Las piezas repetidas de las salas conservan un nombre legible (`Stock2`,
  `ArcadeScreen3`). Así cada una recibe su aspecto.

Antes y después, con la misma cámara: [docs/interiors22](docs/interiors22).

## Validación

- `client/tools/test_interiors22.gd` carga los once interiores y comprueba:
  - que todos están vestidos y tienen lámparas;
  - que no aparece ninguna colisión ni cambia el estado del jugador;
  - que la sonda de reflexión sigue la calidad;
  - que las cintas del videoclub y las pantallas de los recreativos tienen su
    color.
- Siguen pasando `test_realism10.gd` (12 escenas, 3 calidades, física intacta),
  `test_city09.gd` (los 56 vecinos y sus rutas) y el resto de pruebas de Godot.
