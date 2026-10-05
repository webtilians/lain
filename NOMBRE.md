# El juego se llama Sesión Cero

Antes se llamaba LAIN y usaba varios nombres de *Serial Experiments Lain*. Para
poder venderlo sin problemas de marca, el juego y su mundo tienen ahora nombres
propios. La historia es la misma; la red es la misma, con otro nombre.

| Antes | Ahora (español) | Ahora (inglés) |
|---|---|---|
| LAIN (título) | **Sesión Cero** | **Session Zero** |
| la Wired | la Malla | the Mesh |
| el ordenador Navi, «navi-tunombre» | el ordenador Kumo, «casa-tunombre» | Kumo, «casa-yourname» |
| LAIN-DOS | CERO-DOS | CERO-DOS |
| dominios `.wired`, correos `@wired` | `.malla`, `@malla` | `.malla`, `@malla` |
| `/var/log/wired/` | `/var/log/malla/` | `/var/log/malla/` |
| pintadas: WIRED, LAYER:07, PRESENT DAY, CLOSE THE WORLD, KNIGHTS, PROTOCOL 7, DEUS, NAVI, TXEN EHT NEPO, CYBERIA | LA MALLA, CAPA 07, TTL 8, ¿QUIÉN TE RECIBE?, NOEMA MIENTE, NODO 07, SIN ACK, KAGAMI TE VE, OREC NÓISES, AZUL | (son carteles: no se traducen) |

*Kumo* es «nube» y también «araña» en japonés. El subtítulo, «Protocolo de
presencia», ya era nuestro.

El puzle del prólogo pide ahora `telnet malla 23` (en inglés la pista dice
MESH). El terminal acepta `malla`, `mesh` y la palabra antigua, para que nadie
que estuviera a mitad del prólogo se quede atascado.

## Lo que no cambia, a propósito

Son nombres internos que el jugador no ve, o que cambiarlos rompería partidas en
curso:

- Los archivos `LAIN.exe`, `LAIN-Game.exe`, `LAIN-Game.pck` y `LAIN-Windows.zip`.
  El lanzador de cada jugador se actualiza buscándolos por su nombre; cambiarlos
  exige una versión puente. Para una tienda (Steam, itch) se hará un paquete
  nuevo desde cero.
- Las carpetas de datos (`%LOCALAPPDATA%\LAIN`, el nombre interno del proyecto
  Godot). La ventana se titula «Sesión Cero», pero los ajustes y la sesión de
  cada jugador siguen donde estaban.
- El repositorio `webtilians/lain`, el servidor (`/opt/lain`, `lain.service`,
  `vps.ps1`) y las variables `LAIN_*`.
- Los identificadores del código: errores `WIRED_*`, la facción `WIRED`, el
  anfitrión `navi` que viajan entre cliente y servidor.

## Cómo se hizo

Un cambio de texto con reglas exactas sobre el código, las escenas, las pruebas,
los documentos y el catálogo de traducciones (claves en español y valores en
inglés). La página de descarga tiene capturas nuevas hechas con el juego ya
renombrado (`client/tools/capture_landing.gd`).
