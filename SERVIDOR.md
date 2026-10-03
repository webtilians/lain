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

Notas:
- Añadir un jugador cierra el mundo unos segundos; los conectados se
  reconectan solos. `-Update` hace antes una copia del mundo.
- Para quitar el acceso a alguien: `.\vps.ps1 -Shell`, luego
  `cd /opt/lain && runuser -u lain -- .venv/bin/python -m tools.online_server --data-dir /var/lib/lain revoke-player --id <ID>`
  y `systemctl restart lain`. Su progreso se conserva.

## Qué hay en el servidor

| Ruta | Contenido |
| --- | --- |
| `/opt/lain` | Solo la parte del servidor del repositorio, rama `experiment/layer-03-ttl` (Capa 03; antes `experiment/visual-0.12-gothic`). |
| `/var/lib/lain` | El mundo (`online-world.db`) y los accesos; usuario `lain`, sin login. |
| `/etc/lain/lain.env` | Ajustes de la IA y la clave de Groq; solo root. |
| `/var/backups/lain` | Copias diarias; se restauran como explica `lain-backup`. |
| Servicios | `lain` (motor), `caddy` (HTTPS), `lain-backup.timer`. |

El motor solo escucha en `127.0.0.1:8000`; desde fuera solo se llega por
HTTPS a través de Caddy. Las páginas de desarrollo de FastAPI (`/docs`)
están cerradas. Los jugadores necesitan su token para todo lo demás.

## Coste aproximado

El CPX12 con IPv4 cuesta 14,51 € al mes con IVA (13,90 € + 0,61 €; tarifa de
octubre de 2026). Se paga por horas y se puede borrar cuando quieras. Groq
tiene plan gratuito.
