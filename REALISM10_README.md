# LAIN · Visual 0.10 — materiales, luz y vegetación

Rama independiente: `experiment/visual-0.10-realism`.
Base: City09, `adc8d98`. No se fusiona con ninguna rama anterior.

## Cambios visibles

- Asfalto, revoco, hormigón y madera con texturas 2K, relieve, rugosidad y
  oclusión propios. Los mapas siguen la misma proyección y escala en metros.
- Iluminación del cielo, sombras suaves, luz indirecta exterior en calidad
  Alta, reflejos interiores y sombras de contacto. Corrección tonal AgX.
- 26.940 hojas con volumen en 32 grupos; sustituyen las tarjetas planas
  de los árboles y plantas del barrio. Se conservan sus ubicaciones.
- Pequeños biseles en muebles: mesas, sillas, mostradores, estanterías y CRT.
- Ajuste de color suave y texturas con mipmaps para evitar el ruido a distancia.
- **F6** alterna Ligera, Equilibrada y Alta. La selección se guarda como
  preferencia gráfica, separada de SQLite. Alta es el valor inicial.

| Calidad | Materiales y hojas | Sombras de contacto y luz en pantalla | Luz indirecta del cielo (SDFGI) | Reflejos en pantalla |
| --- | --- | --- | --- | --- |
| Ligera | Sí | No | No | No |
| Equilibrada | Sí | Sí | No | No |
| Alta | Sí | Sí | Exterior | Interiores |

Los efectos avanzados requieren Forward+. El renderizador de compatibilidad
conserva materiales y geometría con iluminación más sencilla. El reflejo
del cielo usa una panorámica procedural; los reflejos de pantalla tienen
las limitaciones normales de lo que la cámara ve. Los interiores mantienen
luz ambiental ajustada y SSIL, porque la GI volumétrica del barrio oscurecía
en exceso los locales pequeños. El resplandor se limita a interiores.

Esta entrega mejora el renderizado real del proyecto. Todavía hay edificios
y personajes de geometría sencilla; no equivale al detalle de la ilustración
de referencia. Las capturas adjuntas proceden de Godot, sin retoque.

## Probar en Windows

En la carpeta de esta rama, cierra el servidor anterior si ocupa el puerto
8000 y ejecuta:

```powershell
.\serve-city.ps1
```

En otra ventana:

```powershell
.\play.ps1
```

El lanzador importa todos los recursos antes de abrir el juego. Los assets
ya están en GitHub; no hace falta generarlos ni descargarlos por separado.
El servidor usa **city10.db**. Si no existe, crea una partida nueva; para
continuar una partida se debe copiar mediante la función backup de SQLite
desde una copia anterior, conservando el original.

Recorrido: salir de casa, mirar las fachadas y árboles, ir al parque,
entrar en el videoclub y visitar la estación. Pulsar F6 en cada sitio.
E sigue abriendo interacciones y J las fichas. Se mantienen los 56 PNJ,
el prólogo, el LLM, la autoridad de World Core y las memorias privadas.
No se han modificado los módulos del servidor ni el formato de guardado.

## Validación y comparación

- `test_realism10.gd`: carga las 12 localizaciones y cambia entre las tres
  calidades; comprueba que no cambian colisiones, cámara, snapshot ni la
  preferencia guardada. Verifica materiales de los MultiMesh, follaje y biseles.
- Se mantienen las pruebas del barrio, los 56 ciudadanos y sus rutas,
  interiores, prólogo, fichas, caso de estación y personaje.
- `capture_realism10.gd` captura las escenas de producción con los PNJ del
  catálogo público y API desconectada, sin tocar una partida real.
- `docs/realism10/comparison.html` permite comparar las capturas de la misma
  cámara y resolución. Son escenas reales con un estado de prueba fijo.

Para repetir capturas, crear antes una carpeta absoluta de salida y ejecutar:

```powershell
Godot_v4.7.2-stable_win64_console.exe --path client --script res://tools/capture_realism10.gd --resolution 1440x900 -- C:/ruta/antes --render-baseline
Godot_v4.7.2-stable_win64_console.exe --path client --script res://tools/capture_realism10.gd --resolution 1440x900 -- C:/ruta/despues --render-high
```

`--render-baseline` desactiva esta capa visual para la comparación; no cambia
la lógica del juego. Las capturas no constituyen un benchmark. Si el movimiento
es lento, bajar con F6 a Equilibrada o Ligera.

Fuentes de los materiales y licencia: [SOURCES.md](client/art/realism10/SOURCES.md).
Referencias del motor: [materiales PBR](https://docs.godotengine.org/en/stable/tutorials/3d/standard_material_3d.html)
y [SDFGI](https://docs.godotengine.org/en/stable/tutorials/3d/global_illumination/using_sdfgi.html).
