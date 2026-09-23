# Visual 0.7 — limpieza espacial y rediseño del prólogo

Rama experimental: `experiment/visual-0.7-prologue-district-pass`,
derivada de `experiment/prologue-0.2-neighborhood-dialogue`.
La PR no fusiona ni modifica Visual 0.6, la lógica del prólogo, el
servidor, la base de datos `world.db` ni las partidas de prueba previas.

## Causa concreta de los árboles sobre casas

El barrio ampliado de 38 × 78 unidades todavía instanciaba **dos copias**
del modelo de calle residencial de 36 m. Ese modelo tiene cinco troncos y
75 tarjetas de follaje por instancia, así como fachadas y postes situados
según el diseño estrecho original. Al combinar dos copias sin adaptar sus
coordenadas con la nueva escuela y discoteca aparecían objetos superpuestos.

Se han eliminado únicamente las **dos instancias** desajustadas de
`ResidentialStreet.tscn` de `ApartmentDistrict.tscn`; el asset original
continúa en el repositorio, sin modificarlo. El nuevo barrio conserva
su geometría, ubicación de accesos y texturas de Visual 0.6 y utiliza
vegetación intencional del propio `PrologueDistrictEntrances.gd`.
Sus árboles quedan cerca de las aceras pero **al menos 3 m separados del
frente de los edificios una vez descontada la copa**, y se omiten
los que quedarían demasiado cerca de cualquiera de las dos entradas.
No hay vegetación superpuesta entre las fachadas antiguas y las nuevas.

## Cambios visuales

**Escuela municipal:** volumen de piedra gris cálida y textura de
hormigón, zócalo, cornisas, pilastras, ventanas de doble altura con
marcos, escalinata visual y pórtico de entrada reconocible. El
`ExitDoor` real sigue en su ubicación semántica original.

**Club AZUL:** fachada oscura, ventanas cubiertas por lamas, marquesina
sobre el acceso, umbral sin colisión, señalización contenida y luces de
tono violeta/azulado. No se ha sustituido el acceso interactivo ni
desplazado a Ryoko.

**Interiores:** los antiguos muros de cámara (este y frontal) han
pasado de 3,4 m a 0,76 m: desde la cámara isométrica se puede ver
dentro de la escuela, el aula y el club. Se conservan las paredes de
fondo y oeste para enmarcar el ambiente. Se introducen pavimentos
texturizados, ventanas, mobiliario escolar, cuatro ordenadores CRT
con pantalla, pizarra, iluminación fluorescente, barra, pista,
equipo de sonido e iluminación de club tenue. Elementos de atrezo
pequeños son exclusivamente visuales, sin colisiones ocultas.

**Se mantienen** el avatar esbelto, el ciclo de mundo autónomo,
las preguntas del profesor, las pistas indirectas de Ryoko, el diario,
las ubicaciones del servidor y el acertijo de conexión.

## Probar sin arriesgar las partidas

Cierra antes Godot y Uvicorn; no cambies de rama en
`C:\Users\ENRIQUE\lain` porque tiene cambios locales y la partida
principal. Si ya existe `lain-visual07`, no sobreescribas la carpeta.

```powershell
cd C:\Users\ENRIQUE\lain
git fetch origin
git worktree add --detach ..\lain-visual07 origin/experiment/visual-0.7-prologue-district-pass
cd ..\lain-visual07
```

Si existe `C:\Users\ENRIQUE\lain-prologue02\newgame02.db`, puedes
**copiarla, con Godot y Uvicorn detenidos**, a `lain-visual07\visual07.db`
para probar el nuevo aspecto con el mismo progreso sin tocar el original.
Si prefieres empezar otra vez, **no copies** ninguna base; en el primer
arranque el servidor creará `visual07.db`.

```powershell
$env:LAIN_WORLD_DB="C:\Users\ENRIQUE\lain-visual07\visual07.db"
$env:LAIN_PROLOGUE_ENABLED="1"
$env:LAIN_LLM_ENABLED="1"
$env:LAIN_LLM_MODEL="lain-qwen7b"
$env:LAIN_LLM_ENDPOINT="http://127.0.0.1:11434/v1/chat/completions"
$env:LAIN_REALITY_GENERATION="1"
$env:LAIN_WORLD_CLOCK="1"
$env:LAIN_WORLD_TICK_SECONDS="8"
C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m uvicorn server.api:app --host 127.0.0.1 --port 8000
```

En otra consola:
`cd C:\Users\ENRIQUE\lain-visual07; .\play.ps1`.

Las pruebas CI de Godot importan el cliente y recorren las tres
escenas, comprueban accesos reales y que el barrio conserva
vegetación sin invadir edificios o entradas. No equivalen a una
inspección con cámara y movimiento en Windows: comprobar a mano
la visibilidad de las puertas, posibles huecos, recorrido y contraste
de los materiales antes de fusionar.
