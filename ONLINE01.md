# LAIN Online 0.1 — beta privada

Rama actual revisada: `experiment/online-0.1-review-fixes`, basada en `fee68e8` de `experiment/online-0.1-shared-world`. No se mezcla con ninguna rama anterior. Correcciones y resultados en [REVIEW_ONLINE01.md](REVIEW_ONLINE01.md).

Esta versión permite que dos o tres personas entren en un mismo mundo, se vean en el barrio y hablen con Enter. Cada acceso conserva su prólogo, inventario, diario y conversaciones. El anfitrión guarda el mundo; cerrar un cliente no cierra el servidor. La IA compartida se puede conectar después.

## Anfitrión con un solo comando (`online-host.ps1`)

Desde la carpeta del proyecto, con Python 3.12 y `requirements.txt` instalados:

```powershell
.\online-host.ps1                      # abre el mundo por internet (túnel HTTPS de Cloudflare)
.\online-host.ps1 -Mode lan            # solo para la misma red Wi-Fi
.\online-host.ps1 -AddPlayer "Carlos"  # crea un acceso y su kit (con el mundo cerrado)
```

- **Internet**: arranca el World Core en `127.0.0.1` y un *quick tunnel* de
  Cloudflare (`cloudflared.exe` en `%USERPROFILE%\tools` o en el PATH). No
  hay que tocar el router ni crear cuentas. La dirección
  `https://….trycloudflare.com` cambia cada vez que se abre el mundo.
- Al abrir, el script escribe la dirección en todos los accesos y deja un kit
  por jugador en `%USERPROFILE%\LAIN-Online-Amigos\<nombre>` (y el mismo kit
  en `.zip`): `lain-online.json`, `Cambiar servidor.bat` y `LEEME-AMIGO.txt`.
  Cada amigo copia el kit junto a su `LAIN.exe`; en las siguientes sesiones
  solo necesita la dirección nueva, que pega con `Cambiar servidor.bat`.
- Si Ollama tiene `lain-qwen7b`, los personajes usan esa IA del anfitrión
  (`-NoAI` la desactiva). Sin ella, diálogos predefinidos.
- Registros en `%LOCALAPPDATA%\LAIN\OnlineHost\logs`. Ctrl+C cierra el mundo
  y el túnel; el progreso queda guardado.
- El anfitrión puede jugar en el mismo PC con su acceso apuntando a
  `http://127.0.0.1:8000`, sin pasar por el túnel.

## Probar primero en tu ordenador

Usa la carpeta **`C:\Users\ENRIQUE\lain-online01`**. El ZIP de esta versión contiene un juego nuevo: el ejecutable antiguo no sabe conectarse al mundo compartido.

1. Extrae `LAIN-Online-0.1-Windows.zip` en dos carpetas, una para cada jugador.
2. Abre PowerShell y crea dos accesos, con el servidor detenido:

```powershell
cd C:\Users\ENRIQUE\lain-online01
& C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m tools.online_server add-player --name Enrique --url http://127.0.0.1:8000
& C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m tools.online_server add-player --name Invitado --url http://127.0.0.1:8000
```

Cada orden indica dónde ha guardado un **`lain-online.json` personal**. Copia el de Enrique junto al `LAIN.exe` de la primera carpeta y el de Invitado junto al de la segunda, sustituyendo la plantilla vacía. Guarda esos archivos: contienen el acceso a cada personaje. No los publiques en GitHub ni en el ZIP público.

3. Arranca el mundo compartido y deja abierta esa ventana:

```powershell
cd C:\Users\ENRIQUE\lain-online01; & C:\Users\ENRIQUE\lain\.venv\Scripts\python.exe -m tools.online_server serve
```

4. Abre ambos `LAIN.exe`. Los dos empiezan con su propio prólogo. Sal de casa con cada uno: deberías ver al otro personaje y su nombre. Pulsa Enter para escribir y Enter para enviar.
5. Entra en el colegio con uno: el otro debe seguir en el barrio. Habla con el profesor con uno y comprueba que el diario del otro no avanza. Cierra y vuelve a abrir un juego: conserva su progreso. Si acabas de cerrarlo, espera hasta 12 segundos antes de abrir el mismo acceso en otro ordenador.

El puerto 8000 debe estar libre. Si usas otro, por ejemplo `serve --port 8010`, cambia también `server_url` de los archivos personales. No ejecutes a la vez el servidor anterior en ese mismo puerto. Un archivo vacío mantiene el modo individual anterior, con su guardado habitual.

En otra instalación, usa Python 3.12, instala `requirements.txt` y sustituye la ruta del intérprete. Los jugadores que reciben el ZIP no necesitan Python ni Godot.

## Probar con amigos en la misma red

Crea un acceso diferente para cada persona usando la IP privada del ordenador anfitrión, por ejemplo `--url http://192.168.1.50:8000`. También puedes cambiar solo `server_url` en los accesos existentes: conserva `player_token` para mantener el personaje.

Arranca el anfitrión con `python -m tools.online_server serve --host 0.0.0.0`. Cada amigo recibe el ZIP público y **su** archivo personal por separado. Si Windows pregunta por el cortafuegos, permite la conexión únicamente en la red privada de la prueba. El anfitrión tiene que permanecer encendido.

## Acceso por Internet cuando esté listo Cloudflare

La dirección del mundo y la dirección del servicio de IA son distintas. El World Core de Python sigue ejecutándose en tu ordenador o en un servidor permanente. El Worker de IA ya preparado no aloja esta simulación.

Para una prueba temporal, Cloudflare documenta los [Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/). Tras instalar `cloudflared`, con el servidor en `127.0.0.1:8000`, ejecuta en otra ventana:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Pon la URL HTTPS que muestre en `server_url` de cada acceso, conservando su token. Es una URL temporal para pruebas y puede cambiar al reiniciar el túnel; Cloudflare no garantiza disponibilidad para Quick Tunnels. Para una dirección estable, configura un túnel administrado. Este mecanismo publica el servicio mediante conexiones salientes sin abrir el router, según la [documentación de Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/).

Esta entrega no publica un túnel ni despliega servicios. La prueba automatizada usa dos clientes reales de Godot y HTTP local; la prueba con equipos en redes distintas queda para cuando exista la dirección pública.

## Añadir Groq después

Sigue `SHARED_AI_BETA02.md` para preparar el servicio de IA. Arranca el mundo con su dirección:

```powershell
python -m tools.online_server serve --ai-gateway https://TU-SERVICIO-DE-IA.workers.dev
```

Los jugadores no necesitan cuentas ni claves de Groq. El anfitrión hace las consultas. La conversación y los recuerdos seleccionados se envían al servicio de IA; la base de datos completa permanece en el anfitrión. Sin servicio configurado puedes probar el mundo y las respuestas deterministas. El límite de uso del proveedor sigue aplicándose.

## Guardados y accesos

- Mundo online: `%LOCALAPPDATA%\LAIN\OnlineHost\online-world.db`.
- Archivos personales: `%LOCALAPPDATA%\LAIN\OnlineHost\access\`.
- La partida local anterior permanece en `%LOCALAPPDATA%\LAIN\Beta01\save.db`.
- Usa **un único proceso** de servidor por mundo. Un bloqueo impide dos relojes sobre el mismo guardado. Detén el servidor antes de crear jugadores nuevos o copiar el mundo como respaldo. Ctrl+C lo detiene.
- `python -m tools.online_server list-players` muestra nombres e identificadores sin revelar los accesos.
- `python -m tools.online_server revoke-player --id IDENTIFICADOR` invalida un acceso y conserva su progreso.
- Si cambias de ordenador anfitrión, copia la carpeta OnlineHost con el servidor detenido y mantén los mismos accesos. `--data-dir RUTA` permite elegir otra carpeta, antes del subcomando.

## Alcance de esta primera fase

El servidor decide acciones, ubicaciones, recursos, relojes y recompensas. Cada petición se autentica como su propietario; no se acepta un jugador elegido en el cuerpo de la petición. Los comandos generales tienen comprobantes para que reenviar una petición no duplique efectos. Si una operación queda interrumpida, no se repite automáticamente: el cliente debe actualizar el estado.

Las posiciones de los avatares son visuales, con comprobación de zona, límites y velocidad. Las colisiones se resuelven en Godot: todavía no es una simulación de movimiento resistente a trampas. El apartamento es privado para presencia y chat; no hay visitas a casas. El chat solo llega a quienes estaban presentes en esa zona, no se usa como memoria de PNJ y desaparece al reiniciar el servidor.

Los torneos y la competencia por relés usan el mundo compartido y las identidades separadas. Se mantienen los círculos y los intercambios con PNJ existentes; las invitaciones y los intercambios directos entre jugadores humanos son una fase posterior. Todavía no hay registro público, recuperación automática de accesos ni un servicio permanente desplegado. Está orientado a una beta con personas invitadas.

## Verificación para desarrollo

```powershell
python -m pytest -q
python -m unittest discover -s packaging -p "test_*.py"
godot --headless --path client --editor --import --quit
python tools/smoke_online01.py --godot godot
```

La integración crea un mundo temporal y dos procesos de Godot, verifica identidad, avatares, chat y cambios de escena independientes, y cierra sus propios procesos. No usa partidas del usuario. `--capture outputs/online-smoke/online-city.png` genera una captura durante esa prueba con renderizado real.

Para comprobar además el juego exportado, usa `python tools/smoke_online01.py --godot RUTA/LAIN-Game.exe --exported`. Esa comprobación arranca dos ejecutables con su PCK y verifica que publican presencia con identidades diferentes. También se ejecuta antes de generar el ZIP de Windows en GitHub.

Validación inicial: 493 pruebas Python, 12 comprobaciones de escenas y mecánicas de Godot, integración HTTP con dos clientes y comprobación de dos ejecutables exportados. La captura de desarrollo está en `outputs/online-smoke/online-city.png`.
