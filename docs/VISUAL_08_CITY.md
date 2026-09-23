# Visual 0.8 — un barrio que se puede recorrer

Rama: `experiment/visual-0.8-city-neighborhood`.
Base revisada: Visual 0.7, commit `8998af4`, incluyendo el prólogo 0.2,
colegio, aula, Ryoko, AZUL, fichas y reloj autónomo.

El escenario exterior pasa de 38 × 78 a 92 × 132 unidades: unas cuatro
veces la superficie delimitada. Tres calles longitudinales y cuatro
transversales conectan varias manzanas, una plaza y los accesos del juego.
Hay rutas alternativas; ya no es una sola calle larga entre dos muros.
Las viviendas tienen tejados, remates, ventanas, balcones y bajantes.
Los comercios, postes con cableado, bicicletas, coches aparcados, bancos,
parada, cabina y máquinas expendedoras dan escala a pie de calle.

Los árboles usan la textura de follaje que ya estaba en el proyecto,
en lugar de esferas. El pavimento, muros y tejados reutilizan los mapas
de textura incluidos en Visual 0.5 con materiales diferentes. No hay
descargas de assets durante el juego.

## Integración

- El colegio, discoteca, apartamento y estación conservan exactamente
  sus destinos de World Core. Solo cambian las coordenadas físicas.
- Al salir de un interior se reaparece junto a la puerta correspondiente.
- El plano muestra lugares públicos y al jugador; no revela personajes
  ocultos, recuerdos, pistas privadas ni posiciones privadas del servidor.
- Las partes altas de los edificios se ocultan si tapan al personaje
  desde la cámara ortográfica. Sus colisiones y zócalos permanecen.
- No se añaden habitantes de mentira ni se alteran las fichas, IA,
  memoria, reloj, acertijo, terminal ni progreso del prólogo.
- La geometría está guardada en `client/art/city08/Neighborhood.tscn`.
  Se agrupa por material y por zona con MultiMesh, para evitar un objeto
  dibujado por cada baldosa o varilla. Las puertas siguen siendo nodos
  interactivos independientes.

La iluminación ambiente utiliza una fuente de color explícita,
[según Environment de Godot](https://docs.godotengine.org/en/stable/classes/class_environment.html#enum-environment-ambientsource).
El acabado cromático solo se aplica al escenario, por debajo de los textos.
Esta entrega desarrolla el exterior; conserva los interiores de Visual 0.7.
Los comercios de decorado todavía no tienen interiores ni interacciones.

## Probar en Windows

Usa una carpeta independiente. No cambies de rama sobre la partida activa.
Si aún no existe:

```powershell
cd C:\Users\ENRIQUE\lain
git fetch origin
git worktree add --detach ..\lain-city08 origin/experiment/visual-0.8-city-neighborhood
```

Para continuar, utiliza una **copia** coherente de la partida de Visual 0.7
en `C:\Users\ENRIQUE\lain-city08\city08.db`.
Si no existe esa base, se crea una partida nueva con prólogo.
El lanzador selecciona esa base explícitamente; no usa el `world.db`
histórico incluido en el repositorio. Nunca sobrescribe una partida.

Cierra el juego y el servidor anteriores para liberar el puerto 8000.
En una ventana de PowerShell:

```powershell
cd C:\Users\ENRIQUE\lain-city08; .\serve-city.ps1
```

En otra:

```powershell
cd C:\Users\ENRIQUE\lain-city08; .\play.ps1
```

`serve-city.ps1` conserva el modelo y proveedor ya configurados. Si faltan,
usa los valores habituales de este proyecto: Ollama local, lain-qwen7b,
LLM habilitado y un tiempo de espera de 45 segundos. Se puede indicar
`-PythonPath` o `-WorldPath` para otras instalaciones. Para probar el
prólogo desde cero, utiliza un nombre nuevo, por ejemplo
`./serve-city.ps1 -WorldPath city08-new.db`.

Paseo sugerido: casa → calle principal → cruce del colegio → plaza →
calle lateral derecha → AZUL → estación → regreso por la calle izquierda.
WASD mueve al personaje, E interactúa y J abre el diario.

## Comprobaciones

- 240 pruebas Python pasan, con modelos simulados y SQLite temporal.
- Godot 4.7.2 importa los scripts y recursos.
- Pruebas existentes: prólogo y terminal, diario y caso de estación,
  patrullas de entidades y articulaciones del protagonista.
- `test_city08.gd` recorre las cuatro rutas con el cuerpo y las colisiones
  reales, comprueba todas las entradas y retornos, ocho entidades con
  patrullas, recuperación de fachadas y presencia de datos de los assets.
- Capturas de las cinco zonas obtenidas con el renderizador real
  Compatibility en Windows; sin servidor ni mutaciones de partida.

```powershell
Godot_v4.7.2-stable_win64_console.exe --headless --path client --script res://tools/test_city08.gd
```

El generador offline es `client/tools/build_city08.gd`. Solo se necesita
para editar el arte, no para jugar. Ejecutarlo **sin --headless**: el
renderizador ficticio no conserva los buffers de transformaciones de
MultiMesh. El generador lo rechaza y espera un fotograma real antes de
guardar. Las pruebas verifican que los buffers se incluyeron en el asset.
Los generadores/capturas sustituyen WorldApi y PrologueApi por adaptadores
sin red. Una captura no arranca el reloj del mundo ni cambia su base.
