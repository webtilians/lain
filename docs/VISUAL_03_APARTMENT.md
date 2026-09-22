# Visual 0.3 — primera escena jugable: apartamento

Rama independiente `experiment/visual-0.3-apartment`, desde D11-r1
`bbb820ba61022c950a84dcc56e8dad8a41665d83`.

Esta primera entrega implementa el apartamento de la dirección visual aprobada.
No pretende igualar el detalle de la ilustración conceptual: la geometría y el
personaje son estilizados y sencillos. Barrio y estación conservan por ahora sus
escenas anteriores; se podrán extender con el mismo vocabulario visual.

## Cambios

- Mobiliario 3D: escritorio CRT, teclado, torres, cables, futón, mesa baja,
  estantería con libros, fregadero, cortinas, ventana y puerta vestida.
- Textura original de pared y material de madera con grano procedural.
- Cámara fija solo en el apartamento, iluminación lavanda/verdosa, sombras,
  CRT más suave y menos ruido.
- Silueta humana sencilla con giro y movimiento de piernas; es un personaje
  provisional, no un modelo final de Lain.
- Terminal y puerta conservan sus scripts. La puerta se ubica en la pared del
  fondo; los muebles sólidos tienen colisiones y dejan caminos accesibles.
- Resolución lógica de presentación 1280x720 (antes 640x360). Esto también hace
  más discreta la interfaz de las demás escenas; revisar pantallas pequeñas.
- Sin cambios en servidor, memoria, autoridad World Core o esquema SQLite.

## Recursos y procedencia

`client/art/apartment/plaster.png`: generada con la herramienta integrada
ImageGen; incorporada al proyecto como textura. Prompt utilizado:

> Production game texture, one square seamless tileable albedo texture of old Japanese apartment warm grey ivory plaster with extremely subtle lavender grey mottling, soft hand-painted anime background surface quality inspired by late 1990s psychological anime. Flat front-on orthographic scan of a wall surface ONLY. Fine matte paper grain, sparse tiny worn marks and barely visible hairline cracks, restrained aging, low contrast. No objects, no room, no border, no perspective, no directional light, no shadows, no text, no stains shaped like objects, no large cracks. Even illumination and consistent color at opposite edges for tiling. This will be used on 3D walls in an isometric game.

`client/art/apartment/wood.gdshader`: material procedural original.
`client/scripts/art/ApartmentArt.gd`: geometría original determinista con primitivas
Godot. No usa fotogramas del anime como texturas ni requiere descargar recursos.

## Prueba de juego

Detén el servidor y cierra Godot antes de cambiar la rama. Respalda tu partida.

```powershell
git fetch origin
git switch --track origin/experiment/visual-0.3-apartment
```

Abre `client/project.godot` en Godot 4.7.2 y arranca el servidor como siempre.
Si tu jugador está fuera, vuelve al apartamento por la puerta del barrio.
Comprueba movimiento WASD, colisiones, E junto al CRT para abrir el terminal,
y E junto a la puerta del fondo a la derecha para salir. Comprueba también
que diálogo y menús se leen bien con la resolución nueva.

## Verificación sin conexión a la partida

```powershell
Godot_v4.7.2-stable_win64_console.exe --headless --path client --editor --import --quit
Godot_v4.7.2-stable_win64_console.exe --headless --path client --script res://tools/capture_apartment.gd
```

La segunda orden reemplaza WorldApi por un sustituto sin red, recorre rutas
hasta terminal y salida, verifica alcance y apertura del terminal. No llama al
servidor ni carga SQLite. Para guardar una captura real del motor, ejecuta sin
`--headless` y añade `-- C:/ruta/absoluta/captura.png`; el directorio debe existir.
La escena de prueba se cierra sola tras la captura y no es una partida interactiva.

## Pendientes visuales

Modelos de personaje y animaciones definitivas, telas menos geométricas, más
objetos personales y extensión de la dirección artística al barrio y estación.
La composición se ha revisado en una captura 1280x720 con OpenGL Compatibility;
el rendimiento debe comprobarse en el equipo del jugador.
