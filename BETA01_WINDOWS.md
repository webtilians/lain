# LAIN Beta 0.1 — distribución portable de Windows

Rama exclusivamente experimental `experiment/distribution-0.1-windows-beta`,
derivada de `experiment/wired-0.7-code-exchange`. **Sin merge y sin cambiar
`world.db`, `exchange01.db`, otras partidas ni las ramas anteriores.**

## Qué entrega

La acción [LAIN Beta 0.1 — Windows portable ZIP](.github/workflows/beta01-windows.yml)
construye `LAIN-Beta-0.1-Windows.zip` en el runner Windows 2022 con:

```text
LAIN.exe                    # único botón visible que debe pulsar el jugador
Game/LAIN-Game.exe          # cliente Godot 4.7.2 exportado
Game/LAIN-Game.pck          # escenas y recursos del juego
Server/LainServer.exe       # FastAPI + World Core congelados con PyInstaller
Server/_internal/...        # bibliotecas y catálogo de torneos
LEEME.txt                   # instrucciones para los probadores
```

Es un juego **portátil**, no un instalador ni un solo binario autónomo.
Godot se exporta con PCK separado para no embutir recursos en el EXE;
el arte y el backend van dentro del ZIP, nunca se descargan al ejecutar.
Python 3.12, PyInstaller 6.16.0 y el editor y las plantillas de Godot
4.7.2 se usan únicamente en el *runner* de compilación. En el PC de
destino no se necesitan Python, Git, Godot ni permisos de administrador.

## Arranque y aislamiento

El lanzador de Windows verifica que el puerto 8000 esté libre, toma un
bloqueo por usuario, arranca únicamente su proceso de servidor enlazado
a `127.0.0.1:8000` y espera una respuesta válida de
`/api/v1/player/state` antes de ejecutar Godot. Cierra el servidor
hijo cuando termina el cliente; **no mata otros procesos de terceros**.
La única ruta de SQLite del paquete es:

```text
%LOCALAPPDATA%\LAIN\Beta01\save.db
```

Los registros del lanzador y el servidor también están en esa carpeta.
Si el puerto está ocupado, informa del problema en vez de usar por
accidente el servidor o la partida de otra instalación. El ZIP no
contiene ninguna base de datos del desarrollador, credenciales,
configuración `.env` ni rutas o claves de su ordenador.

El código del cliente aún utiliza una URL fija
`http://127.0.0.1:8000`: esta distribución es para **un jugador y
un solo ordenador**, no una infraestructura remota. No incorpora
autenticación de conexiones de otros procesos locales; el servidor no
escucha en interfaces de red.

## IA local opcional

El modo habitual es `LAIN_LLM_ENABLED=0`: funciona sin Ollama y se
mantienen las mecánicas y los diálogos deterministas. El lanzador
consulta únicamente el `/api/tags` de Ollama en localhost
(`127.0.0.1:11434`) con un tiempo de espera corto. Solo si el modelo
`lain-qwen7b` está disponible pregunta si se desea activar la
generación. La negativa deja la IA desactivada. No se incluyen pesos,
API keys ni se permite ningún proveedor remoto desde la beta.

## CI y descarga

1. Abrir la pestaña **Actions** del repositorio.
2. Elegir **LAIN Beta 0.1 — Windows portable ZIP**.
3. Abrir la ejecución más reciente **verde** de esta rama.
4. En **Artifacts**, descargar **LAIN-Beta-0.1-Windows**. GitHub
   entrega un contenedor ZIP; dentro está `LAIN-Beta-0.1-Windows.zip`,
   que es el que se envía a los probadores.
5. Descomprimir el ZIP del juego y hacer doble clic en `LAIN.exe`.
   No seleccionar `LainServer.exe` ni `LAIN-Game.exe` directamente.
6. Compartir el ZIP del juego por Drive o itch.io después de probarlo
   en un segundo equipo y revisar las licencias de los materiales.

Los artefactos de Actions caducan a los 14 días. Esta tarea **no
publica automáticamente una GitHub Release** ni altera otras ramas.
Antes de ofrecer una descarga pública permanente, revisar rendimiento,
derechos de referencias artísticas, falsas alertas antivirus y
firma digital del ejecutable. SmartScreen puede avisar por falta de
firma; nunca recomendar desactivar el antivirus.

## Validaciones

- Pruebas puras de `packaging/test_beta01.py` sobre aislamiento de
  AppData, opción de IA, claves, catálogo y filtrado de artefactos.
- Suite Python existente en un runner desechable.
- El servidor **congelado** se ejecuta con SQLite temporal y se exige
  estado nuevo jugable en `APARTMENT` y prólogo activo.
- Importación y exportación Godot `Windows Desktop`; se comprueba
  presencia de exe y pck.
- `packaging/check_zip.py` recorre el ZIP, verifica CRC y rechaza
  archivos `.db`, `.env`, claves y rutas ajenas.

Estas pruebas no sustituyen un playtest interactivo del ZIP final.
Probar el recorrido apartamento → colegio → AZUL → primera conexión,
luego capítulo y PC, sin ningún componente de desarrollo instalado.
Si una comprobación falla, **no compartir el artefacto**: no se
considera compilación válida.

Comprobación en desarrollo:

```powershell
python -m unittest discover -s packaging -p "test_*.py" -v
python -m pytest -q
```

La ejecución del workflow por `push` a la rama construye una beta
nueva; `workflow_dispatch` permite repetirla desde Actions cuando
GitHub ya reconoce el archivo de flujo. Se conserva el guardado
individual entre ejecuciones en el mismo PC. Para nuevas versiones,
realizar una copia de seguridad antes de cambiar de formato de SQLite.
