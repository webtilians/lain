# Integración Visual + Reality 0.3-r1

Rama nueva: `experiment/visual-reality-0.3-r1`.
Conserva todos los commits de `experiment/reality-0.1-generated-entities`
hasta d73e175 y añade los ocho assets persistidos de ce22fde. Las ramas
anteriores no se han fusionado ni reescrito.

## Fallo corregido

La PNG original estaba en el repositorio y en la copia del jugador, pero el
juego se ejecutó sin que Godot generase `.godot/imported/plaster...ctex`.
El archivo `.png.import` contiene instrucciones de importación, no la textura
procesada. El servidor no genera esa caché ni puede corregirla al arrancar.

`play.ps1` importa primero todos los recursos con Godot, valida el resultado
y después abre el juego. No borra la caché ni modifica world.db. El servidor
se inicia de la forma habitual; este lanzador no cambia su configuración.

```powershell
.\play.ps1
```

Solo reparar recursos sin abrir el juego:

```powershell
.\play.ps1 -ImportOnly
```

Godot se localiza en PATH; también se puede indicar `-GodotPath C:\ruta\Godot.exe`.
Cerrar Godot antes de actualizar o ejecutar la reparación. No borrar la partida.
La creación de entidades sigue requiriendo las opciones de Reality 0.1;
esta integración conserva el opt-in y no habilita funciones silenciosamente.
