# Assets del apartamento

Estos archivos se cargan directamente desde ApartmentIso.tscn y son escenas
editables en Godot, con mallas, materiales y colisiones incluidas.

| Archivo | Contenido |
|---|---|
| models/Floor.tscn | Tablas del suelo, base y alfombra |
| models/Architecture.tscn | Ventana, cortinas, marco y detalles de puerta |
| models/Workstation.tscn | Escritorio, CRT, teclado, torres, silla y cables |
| models/SleepingArea.tscn | Futón, almohada, mesa baja y objetos |
| models/Shelves.tscn | Estantería, libros y tablón |
| models/Kitchen.tscn | Mueble, fregadero, grifo y azulejos |
| models/Lighting.tscn | Ambiente y luz de ventana |
| models/PlayerSilhouette.tscn | Personaje provisional con animación básica |
| plaster.png | Textura original de pared generada con ImageGen |
| wood.gdshader | Material de madera procedural |

Los modelos son geometría original de Godot: no hace falta Blender, GLB ni
instalar paquetes externos. Se ven también en el editor, antes de ejecutar.
ApartmentPresentation.gd solo aplica el estilo de la interfaz; no construye
muebles. ApartmentArt.gd conserva el código de autoría anterior como referencia,
pero la escena jugable ya no lo ejecuta.

Tras descargar la rama, abre client/project.godot y deja que Godot importe
plaster.png. La carpeta .godot es una caché local y no contiene assets fuente
necesarios para descargar. No borres world.db.
