# LAIN en un servidor propio (siempre encendido)

El motor del mundo online vive en un VPS pequeño. Tu PC ya no tiene que
estar encendido, la dirección no cambia y cada amigo recibe un único ZIP:
lo extrae, abre `LAIN.exe` y entra.

- **Servidor**: Hetzner Cloud CPX12 (1 vCPU AMD, 2 GB, 40 GB) en Falkenstein,
  Ubuntu 24.04, llamado `lain`. El CX23, más barato, estaba agotado en
  Europa en octubre de 2026; para el motor basta con 2 GB.
- **Dirección**: `https://<ip-con-guiones>.sslip.io`, gratis. Caddy obtiene
  y renueva el certificado HTTPS él solo.
- **IA de los personajes**: Groq, llamado desde el servidor. La clave se
  escribe en el propio servidor y nunca sale de allí.

Todo se maneja desde el PC con `vps.ps1`.

## Que juegue gente nueva (sin que tú hagas nada)

1. Pásales la web del servidor: **https://178-105-103-4.sslip.io**. Tiene el
   botón de descarga. El enlace directo, que siempre baja la última versión,
   es `https://github.com/webtilians/lain/releases/latest/download/LAIN-Windows.zip`.
2. Pásales también el **código de invitación**. Para verlo o cambiarlo:

   ```powershell
   .\vps.ps1 -Invite ver      # muestra el código actual
   .\vps.ps1 -Invite nuevo    # código nuevo (el anterior deja de valer)
   .\vps.ps1 -Invite abierto  # cualquiera con el juego puede registrarse
   .\vps.ps1 -Invite cerrado  # nadie nuevo puede registrarse
   ```

3. Cada persona extrae el ZIP, abre `LAIN.exe` y se crea su cuenta con nombre,
   contraseña y el código. El PC recuerda la sesión. Desde otro PC entra con
   su nombre y contraseña.
4. Si alguien olvida su contraseña: `.\vps.ps1 -ResetPassword "Nombre"` te da
   una nueva para pasársela.

Los jugadores de antes (con su `lain-online.json`) copian ese archivo junto
al nuevo `LAIN.exe` una vez: el menú les pide que pongan una contraseña.

## Publicar una fase nueva

```powershell
.\vps.ps1 -Publish 0.13.1
```

Sube una etiqueta `v0.13.1` a GitHub. El flujo *LAIN — publicar versión
online* compila el juego (unos 20 minutos), comprueba que dos clientes
comparten mundo y publica la versión en GitHub Releases. Después el script
actualiza el servidor. Cada jugador recibe la versión nueva al abrir
`LAIN.exe`. El lanzador no vuelve a bajar el juego entero: corta su copia en
trozos, compara con la lista `parts.json.gz` de la versión nueva y descarga
solo los trozos que faltan. De la 0.22 a la 0.23 habrían sido unos 3 MB en
lugar de 291. Antes de instalar comprueba la huella SHA-256 de cada archivo.
Si algo falla, descarga el archivo entero como antes. La primera versión con
parches aún se baja entera, porque la instala el lanzador antiguo.

## Copias de seguridad

El servidor guarda una copia del mundo cada día, y otra antes de cada
actualización. Esas copias viven en el mismo servidor: si el servidor se
pierde, se pierden con él. Por eso tu PC descarga también una copia cada día:

```powershell
.\vps.ps1 -Backup
```

- Pide al servidor una copia nueva y descarga las que tu PC aún no tiene: el
  mundo (`online-world-….sql.gz`) y los accesos (`access-….tar.gz`).
- **Comprueba cada copia**: la reconstruye en una base nueva con
  `tools/check_backup.py` y lee los jugadores, las cuentas y el minuto del
  mundo. Una copia que no se puede leer no cuenta como copia.
- La primera vez programa la tarea **LAIN copia del servidor**, que se
  ejecuta cada día a las 13:00. Si el PC estaba apagado a esa hora, la tarea
  espera a que lo enciendas. Para quitarla: `.\vps.ps1 -Backup -NoDaily`.
- En el PC quedan todas las copias de los últimos 30 días y, de antes, la
  última de cada mes. Están en `%LOCALAPPDATA%\LAIN\VPS\copias`, con un
  registro en `copias.log`.
- Para guardarlas en otra carpeta (otro disco, o la carpeta de OneDrive si
  quieres otra copia en la nube): `.\vps.ps1 -Backup -BackupFolder "D:\LAIN-copias"`.
  La carpeta se recuerda.

El panel (`-Panel`) y `-Status` muestran cuándo tu PC verificó la última
copia. En el panel, la fecha se pone **en amarillo** si tiene más de dos días.

Las copias llevan las cuentas y los accesos de los jugadores: no las
compartas ni las subas a GitHub. La clave de la IA no viaja en las copias;
tras una reinstalación se vuelve a poner con `-Gemini`.

### Restaurar una copia

```powershell
.\vps.ps1 -Restore ultima        # la más reciente
.\vps.ps1 -Restore 2026-10-04    # la última copia de ese día
```

Comprueba la copia en el PC, enseña cuántos jugadores tiene y pide que
escribas `RESTAURAR`. Después la sube, guarda antes el mundo actual en el
servidor, cambia uno por otro y reinicia el motor.

### Si el servidor desaparece

1. Crea otro servidor como en «Primera vez» e instálalo con
   `.\vps.ps1 -Ip <ip nueva> -Install`.
2. `.\vps.ps1 -Restore ultima` vuelve a poner el mundo, las cuentas y los
   accesos.
3. `.\vps.ps1 -Gemini` vuelve a activar la IA.

La dirección del servidor sale de su IP. Con otra IP, los juegos de tus
amigos seguirán buscando la antigua. En Hetzner puedes conservar la IP
aunque borres el servidor: en **Primary IPs**, desactiva el borrado
automático y asígnala al servidor nuevo. Así nadie tiene que cambiar nada.

## Primera vez

1. **Llave SSH** (ya creada en este PC):

   ```powershell
   .\vps.ps1 -Key
   ```

   Muestra la llave pública `ssh-ed25519 ... lain-vps`. La privada se queda
   en `%USERPROFILE%\.ssh\lain_vps`; no la compartas.

2. **Crear el servidor** (en la web de Hetzner, lo haces tú):
   1. Ve a https://console.hetzner.com, crea la cuenta y un proyecto.
   2. Pulsa *Add server* (o *Create server*).
   3. Ubicación: Alemania (Falkenstein o Nuremberg).
   4. Imagen: **Ubuntu 24.04**.
   5. Tipo: *Cost-Optimized* CX23 si está disponible; si no, *Regular
      Performance* CPX12.
   6. Red: deja activada la **IPv4 pública**; tus amigos la necesitan.
   7. SSH keys: *Add SSH key*, pega la llave pública y guárdala.
   8. Nombre: `lain`. Pulsa *Create & Buy now*.
   9. Copia la IPv4 que te asigna.

3. **Instalar el motor**, unos 3 minutos:

   ```powershell
   .\vps.ps1 -Ip 1.2.3.4 -Install
   ```

   Esto deja configurado:
   - Python, el motor y Caddy.
   - Cortafuegos con los puertos 22, 80 y 443 abiertos.
   - SSH solo con llave.
   - Actualizaciones de seguridad automáticas.
   - Copia diaria del mundo, guardada 14 días.
   - Servicio que arranca solo y se reinicia si falla.

   Termina con `LISTO: el mundo está encendido en https://...`.

4. **IA de los personajes** (opcional, lo haces tú). Con Google (Gemini):
   1. En Chrome, con tu cuenta de Google, abre https://aistudio.google.com/apikey.
   2. Pulsa *Create API key* y cópiala.
   3. En el panel Terminal ejecuta lo siguiente y pega la clave cuando la
      pida. No se ve al escribirla.

   ```powershell
   .ps.ps1 -Gemini
   ```

   El servidor prueba la clave y elige solo un modelo gratuito que responda.
   Con Groq es igual: la clave sale de https://console.groq.com/keys y el
   comando es `.ps.ps1 -Groq`.

   Sin clave, los personajes usan los diálogos predefinidos. Los planes
   gratuitos tienen límites por minuto y por día: si se superan, ese diálogo
   sale predefinido y el juego sigue. En el plan gratuito de Google, Google
   puede usar los textos para mejorar sus modelos. Para quitar la IA:
   `.ps.ps1 -Shell` y después `lain-set-ai-key --off`.

5. **Trasladar el mundo de tu PC**, para que nadie pierda su personaje.
   Antes cierra `online-host.ps1`.

   ```powershell
   .\vps.ps1 -Migrate -GameZip "$env:USERPROFILE\Downloads\LAIN-Online-0.1-Windows.zip"
   ```

   - Copia el mundo y los accesos al servidor y les pone la dirección
     nueva. Las llaves de los jugadores siguen valiendo.
   - Con `-GameZip` (el ZIP del juego de GitHub Actions) crea también los
     paquetes. El ZIP se guarda, así que solo hace falta la primera vez.

6. **Mandar los paquetes**: en `%USERPROFILE%\LAIN-Amigos` hay un
   `LAIN-<nombre>.zip` por jugador. Manda a cada uno **solo el suyo y por
   privado**, porque lleva su llave personal.

## Día a día

| Quiero... | Comando |
| --- | --- |
| Añadir un amigo (crea su ZIP) | `.\vps.ps1 -AddPlayer "Nombre"` |
| Rehacer todos los ZIP (juego nuevo) | `.\vps.ps1 -Packages -GameZip <zip nuevo>` |
| Ver si todo va bien | `.\vps.ps1 -Status` |
| Actualizar el motor desde GitHub | `.\vps.ps1 -Update` |
| Abrir una consola en el servidor | `.\vps.ps1 -Shell` |
| Copia del mundo en el PC (y diaria) | `.\vps.ps1 -Backup` |
| Volver a una copia | `.\vps.ps1 -Restore ultima` |

Notas:
- Añadir un jugador cierra el mundo unos segundos; los conectados se
  reconectan solos. `-Update` hace antes una copia del mundo.
- Para quitar el acceso a alguien: `.\vps.ps1 -Shell`, luego
  `cd /opt/lain && runuser -u lain -- .venv/bin/python -m tools.online_server --data-dir /var/lib/lain revoke-player --id <ID>`
  y `systemctl restart lain`. Su progreso se conserva.

## Qué hay en el servidor

| Ruta | Contenido |
| --- | --- |
| `/opt/lain` | Solo la parte del servidor del repositorio, rama `main`. |
| `/var/lib/lain` | El mundo (`online-world.db`) y los accesos; usuario `lain`, sin login. |
| `/etc/lain/lain.env` | Ajustes de la IA y la clave de Groq; solo root. |
| `/var/backups/lain` | Copias de 14 días (diarias, antes de cada actualización y al bajarlas al PC). |
| Servicios | `lain` (motor), `caddy` (HTTPS), `lain-backup.timer`. |

El motor solo escucha en `127.0.0.1:8000`; desde fuera solo se llega por
HTTPS a través de Caddy. Las páginas de desarrollo de FastAPI (`/docs`)
están cerradas. Los jugadores necesitan su token para todo lo demás.

## Coste aproximado

El CPX12 con IPv4 cuesta 14,51 € al mes con IVA (13,90 € + 0,61 €; tarifa de
octubre de 2026). Se paga por horas y se puede borrar cuando quieras. Groq
tiene plan gratuito.
