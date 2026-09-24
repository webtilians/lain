# LAIN · City 0.9 — barrio habitado

Rama experimental: `experiment/visual-0.9-living-neighborhood`.
Base: `78b8fed`, Visual 0.8. No se fusiona con ramas anteriores.

## Qué se puede probar

- Dos viviendas con ventanas hundidas, cortinas, tejas curvas, canalones, bajantes,
  cuadros eléctricos, vegetación y una textura de revoco creada para el proyecto.
- Fachadas de comercios distintas y detalles añadidos edificio por edificio:
  toldos, escaparates, carteles, cajas, ropa tendida, bicicletas y macetas.
- Seis locales con interior, entrada y regreso al barrio: **Tsuki** (librería),
  **Inoue** (alimentación), **Hoshi** (videoclub), **Kissa** (café),
  **Akari** (izakaya) y **Game Corner** (recreativos). VHS, CRT, cajas registradoras,
  teléfonos, menús de papel, estanterías y mobiliario de ambiente noventero.
- **56 nuevos PNJ persistentes**, además de K, Nora, las entidades de la partida
  y los personajes del prólogo. Nombres ficticios provisionales, oficio,
  habilidades de 1 a 5, un objetivo individual y cuatro actividades.
- Reparto: barrio/parque 16, colegio 8, informática 4, discoteca 6,
  estación 4 y 3 en cada uno de los seis comercios.
- Personajes articulados con variaciones de ropa, altura, pelo y delantal.
  La actividad aparece cerca del personaje; las fichas completas se abren con **J**.
  **E** permite conversar por el sistema existente.

Los objetivos son motivaciones iniciales, **todavía no misiones con recompensa**.
Las rutinas de esta versión recorren puntos locales del lugar asignado; aún no
incluyen horarios diarios de desplazamiento entre edificios ni interacción
completa con cada objeto. El servidor decide el avance y el cliente lo anima.
Una conversación abierta detiene al PNJ. Consultar el estado no mueve a nadie.

El acabado 3D toma la ilustración como referencia de materiales, volumen y tono.
No es una reproducción exacta de su nivel de detalle dibujado. Las zonas lejanas
mantienen parte de la geometría anterior; la mayor elaboración está en las
viviendas de entrada y los comercios.

## Iniciar en Windows

Cierra el servidor anterior si ocupa el puerto 8000. En la carpeta de esta rama:

```powershell
.\serve-city.ps1
```

En otra ventana:

```powershell
.\play.ps1
```

El servidor usa `city09.db` y activa `LAIN_CITY_RESIDENTS_ENABLED=1` por defecto.
El lanzador importa los recursos antes de abrir Godot. Se utiliza Forward+
para las sombras de contacto; también se puede ejecutar Godot con
`--rendering-method gl_compatibility` si se necesita el renderizador sencillo,
con una iluminación menos completa. No es necesario regenerar los assets.

Recorrido sugerido: salir de casa, recorrer las viviendas nuevas, entrar en
Tsuki e Inoue al otro lado de la calle, visitar el parque y el colegio, bajar al
videoclub y terminar en el izakaya y los recreativos. Acercarse a un vecino,
pulsar **E**, preguntar «¿Qué haces aquí?» y abrir su ficha con **J**.
Salir y reiniciar conserva identidades, diálogo y progreso de la rutina.

## Afinar los personajes

El catálogo legible está en `server/world_core/data/residents09.json`.
Los IDs son permanentes: no reutilizarlos para personas diferentes.

Se pueden editar `name`, `role`, `objective`, `skills`, las cuatro
`activities`, `cadence` (de 1 a 12 ticks) y `appearance`.
Apariencias: worker, apron, student, elder, casual, teacher, suit.
Al crear una partida se importan solamente los personajes que falten.
Reiniciar nunca sobrescribe las fichas ya guardadas.

Para aplicar explícitamente las fichas editadas a la partida existente,
**con el servidor cerrado** y desde la carpeta del proyecto:

```powershell
& C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m server.world_core.residents --world .\city09.db --apply-catalog
```

Esta orden conserva posición, identidad, historial, recuerdos y punto de rutina.
Cambiar `location` o `slot` de la población requiere también ajustar sus
recorridos físicos; la orden de fichas deliberadamente no modifica esos campos.

## Autoridad, partidas y privacidad

La población se crea en SQLite durante la inicialización de Simulation, después
de decidir el estado del prólogo de una partida anterior. Se recupera al reiniciar
sin duplicados. Cada civil es un agente real para CONTACT y las conversaciones.
No consume los ocho huecos reservados a entidades generadas.

Las fichas y representaciones sólo incluyen PNJ en la localización del jugador.
Los objetivos públicos de los civiles son datos escritos expresamente para ellos:
no se publican objetivos privados, recuerdos o creencias de K, Nora u otros agentes.
Cada conversación recibe únicamente el perfil y los recuerdos de su interlocutor.
El LLM conserva su configuración y las reglas de procedencia existentes; cuando
no responde, algunas preguntas sobre el trabajo usan los datos escritos de la ficha.

## Assets y autoría

Las escenas guardadas son `client/art/reference09/ReferenceStreet.tscn` y
`Neighborhood.tscn`. Los seis interiores están en `client/scenes/city09`,
con su mobiliario reproducible en `ShopInterior.gd`.
La nueva textura PNG y su procedencia/prompt completo se incluyen en
[client/art/reference09/MATERIAL_SOURCE.md](client/art/reference09/MATERIAL_SOURCE.md).
Se generó con ImageGen integrado; el resto es geometría, materiales y recursos del
propio juego. No se requieren descargas externas ni archivos de importación privados.

Para reconstruir los dos assets exteriores con Godot y renderizador real:
`--path client --rendering-method gl_compatibility --script res://tools/build_reference09.gd`
y después `--script res://tools/build_living_city09.gd`.
No usar `--headless` en estos autores: el renderer ficticio no guarda los buffers
de MultiMesh. Las pruebas sí se ejecutan sin ventana.

## Comprobaciones

Python: suite previa de 240 casos más 7 casos nuevos de población,
persistencia, privacidad, reloj, conversación y edición explícita.
Godot: rutas originales, puertas y retornos; los 56 PNJ en 11 localizaciones,
todos sus segmentos de movimiento, congelación del estado al repetir una
instantánea, animación al recibir un nuevo punto, prólogo, fichas, estación,
rig y entidades existentes. Capturas reales con Forward+ de los locales y barrio.
CI repite Python y Godot en Linux.
