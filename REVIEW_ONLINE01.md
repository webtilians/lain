# Revisión de LAIN Online 0.1 — 28 de septiembre de 2026

Rama de correcciones: `experiment/online-0.1-review-fixes`, basada en `fee68e8` de `experiment/online-0.1-shared-world`. Revisión del servidor, guardados, diálogos, acceso online, cliente Godot y distribución Windows. Las pruebas usan mundos desechables; no modifican partidas personales. No se fusionan ramas.

## Errores reproducidos y corregidos

| Prioridad | Qué ocurría | Corrección y prueba |
|---|---|---|
| Alta | Una interrupción después de confirmar el primer mensaje de Indara podía dejar al jugador sin la pista inicial, incluso al reintentar. Otra interrupción podía guardar el conocimiento sin su creencia o procedencia. | El reintento reconcilia los efectos y guarda conocimiento, creencia y evento en una transacción. Repara guardados parciales conservando el minuto original, sin sobrescribir observaciones posteriores. Pruebas con interrupción y fallo SQLite inducidos. |
| Alta | Al cerrar el servidor, una actualización de más de tres segundos podía seguir escribiendo después de liberar el bloqueo exclusivo del mundo. | El cierre espera a que termine la actualización. Prueba con un reloj real y una actualización retenida hasta que la prueba la libera. |
| Media | El diálogo determinista buscaba el testimonio de `PLAYER_1` y olvidaba lo contado por identidades online. | Busca al participante de esa conversación. Prueba con dos jugadores: recuerda a quien habló y no atribuye su testimonio al otro. |
| Media | Reiniciar el anfitrión reutilizaba números del chat. Un cliente abierto podía confundir mensajes nuevos con otros ya leídos y ocultarlos. | Identificadores únicos entre reinicios; caché del cliente acotada. Prueba de reinicio del estado en memoria conservando el mundo. El historial del chat sigue siendo temporal. |
| Media | Una conexión que aceptaba la petición sin responder podía dejar bloqueados el diálogo de PNJ y el prólogo indefinidamente. | Tiempo máximo de 180 segundos para diálogos con IA y 15 para el prólogo; permiten volver a intentarlo. Prueba Godot contra un servidor TCP que no responde, incluyendo cerrar el diálogo durante la espera. La prueba acorta estos límites. |
| Media | Abrir dos veces el lanzador en Windows podía lanzar un error al leer un byte bloqueado por la primera instancia. | Comprueba el tamaño sin leer el byte protegido y devuelve el aviso de instancia abierta. Prueba Windows de segunda apertura y reapertura tras liberar el bloqueo. |
| Baja | Consultar jugadores antes de crear el primer mundo fallaba porque faltaba la tabla de agentes. | Consulta de solo lectura con mensaje de lista vacía; no crea un mundo incompleto. Prueba del comando real en una carpeta nueva y con un jugador existente, sin revelar su acceso. |

## Verificación

- Batería general local: **502 pruebas Python aprobadas**. Después se añadió la prueba del cierre: **23 pruebas del reloj y online aprobadas**, incluida esa nueva prueba; **503 casos distintos** en total.
- Importación de Godot y **16 comprobaciones** de escenas, personajes, prólogo, ciudad, diario, corporaciones, taller, círculos, eventos, arcade, intercambios y recuperación de red.
- Dos procesos reales de Godot contra el mismo mundo temporal: identidades diferentes, avatares, chat y desplazamiento independiente.
- Dos ejecutables Windows exportados: presencia autenticada con identidades separadas.
- GitHub ejecuta nuevamente la batería completa, las comprobaciones Godot, las pruebas del servicio de IA y la construcción del ZIP Windows sobre esta rama.

Los registros locales están en `outputs/review-*.log`. Los casos de regresión están versionados en `tests/`, `packaging/test_beta01.py` y `client/tools/test_network_recovery.gd`.

## Probar la revisión

1. Cierra la versión anterior y extrae **todo** `LAIN-Online-0.1-r1-Windows.zip` en una carpeta nueva. Abre `LAIN.exe` desde ella.
2. Para jugar solo, deja la plantilla `lain-online.json` vacía. La partida sigue en `%LOCALAPPDATA%\LAIN\Beta01\save.db`.
3. Para jugar online, copia tu archivo personal `lain-online.json` junto al nuevo `LAIN.exe`. El anfitrión debe arrancar el servidor desde esta rama, después de detener el anterior. Mantén la misma carpeta `OnlineHost` y los mismos accesos para conservar personajes y progreso; no hace falta volver a crearlos.
4. Prueba hablar con un PNJ, alejarte y volver; salir al barrio con dos jugadores; intercambiar mensajes y reiniciar el anfitrión. Los nuevos mensajes deben aparecer al reconectar.

El ZIP generado por GitHub conserva el nombre `LAIN-Online-0.1-Windows.zip`; selecciona el artefacto del flujo de esta rama. Los pasos completos para el anfitrión siguen en [ONLINE01.md](ONLINE01.md).

## Límites y mantenimiento pendiente

La conexión por Internet y la IA real de Groq/Cloudflare requieren la configuración del anfitrión: esta revisión verifica HTTP local y proveedores simulados, no esas cuentas ni un túnel público. Se mantiene el alcance de beta privada descrito en `ONLINE01.md`.

El repositorio todavía versiona algunas cachés `.godot` y `.pyc`; conviene retirarlas del seguimiento en una limpieza específica. No forman parte de las correcciones de código. Las pruebas muestran dos avisos de obsolescencia de dependencias de test, sin fallos: revisar esas actualizaciones por separado evita mezclarlas con esta corrección.
