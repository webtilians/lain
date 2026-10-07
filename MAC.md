# Sesión Cero · La versión para Mac

Desde la 0.28 cada versión publica, junto al ZIP de Windows, **`SesionCero-Mac.zip`**:
una app universal (Mac con chip Apple o Intel, macOS 11 o posterior) que juega en el
mismo mundo que Windows, con las mismas cuentas.

Enlace permanente: https://github.com/webtilians/lain/releases/latest/download/SesionCero-Mac.zip
(también en la página de descarga, botón «Para Mac»).

## Para quien juega

1. Descarga el ZIP. Safari lo descomprime solo; si no, haz doble clic.
2. Arrastra **Sesion Cero** a **Aplicaciones**.
3. La primera vez macOS no la abre, porque el juego no está firmado por Apple
   (ver más abajo). Hay que permitirla una vez:
   1. Ábrela y cierra el aviso.
   2. Ve a **Ajustes del Sistema → Privacidad y seguridad**.
   3. Abajo aparece *Sesion Cero*: pulsa **Abrir igualmente** y confirma con tu
      contraseña o Touch ID.
4. En el menú, crea tu cuenta con un nombre y una contraseña, o entra con los tuyos si
   ya juegas en Windows.

Si macOS dice que la app «está dañada», es la cuarentena de las descargas. Desde el
Terminal se quita con:

```bash
xattr -dr com.apple.quarantine "/Applications/Sesion Cero.app"
```

**Actualizaciones.** En Windows, `LAIN.exe` se actualiza solo. En Mac no hay
lanzador: cuando hay una versión nueva, el menú de inicio lo dice con un botón
**Descargar la versión X**. Se reemplaza la app en Aplicaciones y, la primera vez, hay
que volver a permitirla. Las partidas y las cuentas están en el servidor, así que no se
pierde nada.

Los ajustes del Mac (idioma, gráficos, sonido, sesión) se guardan en
`~/Library/Application Support/Godot/app_userdata/Sesion Cero`.

## Sin firma de Apple

Para que un Mac abra una app descargada sin preguntar, Apple pide firmarla con un
certificado de **Apple Developer Program** (99 USD al año) y mandarla a notarizar. Sin
eso, la app va con una firma *ad hoc*: basta para que funcione en los Mac con chip
Apple, pero hay que permitirla la primera vez.

Si algún día compensa, solo hay que:
- darse de alta en el programa (es tuyo, como la cuenta de Hetzner);
- guardar el certificado y la clave de notarización como secretos de GitHub;
- cambiar el preset `macOS` (`codesign` y `notarization`) en
  `client/export_presets.cfg`.

## Cómo está hecho

- **La app es el juego de Godot solo**, sin el lanzador de Windows. Lo que en Windows
  le pasa `LAIN.exe` (la dirección del servidor, su versión y de dónde actualizarse),
  la app lo lleva dentro, en `res://release.json`.
  - Lo escribe `tools/mac_release.py info` a partir de `packaging/lain-server.json`.
  - `ServerConnection.gd` lo lee cuando no hay variables de entorno.
  - `Boot.gd` consulta el `manifest.json` de la última versión y ofrece la descarga
    si es más nueva.
- **Preset `macOS`** en `client/export_presets.cfg`:
  - arquitectura universal;
  - firma ad hoc integrada en Godot, así que se exporta desde el mismo Windows de
    GitHub que la versión de Windows;
  - nombre «Sesion Cero» (`config/name.macos`), sin acento porque la firma ad hoc de Godot
    no se puede verificar en un Mac si los archivos de dentro lo llevan (la ventana sí dice
    «Sesión Cero»), e identificador `io.github.webtilians.sesioncero`.
  - Las texturas también se importan en ETC2/ASTC (`import_etc2_astc`), que piden los
    Mac con chip Apple. Por eso pesa más que la de Windows: lleva los dos formatos.
- **GitHub Actions:**
  - En cada PR, `beta01-windows.yml` exporta la app y `tools/mac_release.py check`
    revisa el ZIP: la app entera, el programa ejecutable, los datos del juego, la firma,
    el nombre y la versión. Después, en un **Mac de verdad** (`macos-14`):
    - se descomprime como lo hace el Finder;
    - se comprueba la firma y que el programa trae las dos arquitecturas;
    - dos copias del juego juegan juntas en un mundo de prueba (`tools/smoke_online01.py`).
  - Al publicar, `release.yml` exporta la app con el número de versión y la sube a la
    versión.
- **Pruebas:** `tests/test_mac_release.py`, `tests/test_vps_deploy.py` (la página
  enlaza las dos descargas) y `client/tools/test_startmenu.gd` (el aviso de versión
  nueva).
