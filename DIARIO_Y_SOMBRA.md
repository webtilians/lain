# LAIN · El diario poco fiable y la sombra

Rama `experiment/journal-shadow`. Son las dos mecánicas transversales de la
sección 7 de [BIBLIA_NARRATIVA.md](BIBLIA_NARRATIVA.md) que faltaban. Se activan
con `LAIN_JOURNAL=1` y `LAIN_SHADOW=1`, que ya ponen el lanzador,
`serve-city.ps1` y el servidor online.

## El diario poco fiable

**Qué ve el jugador**

- Cada capa que decide se convierte en una entrada de su diario. Lo puede leer
  en dos sitios:
  - la ficha J (sección DIARIO);
  - el Terminal de su Navi: `cat ~/diario`.
- Cada entrada guarda el hash de la anterior y la última línea, `cabeza`, el de
  la más reciente.
- **NOEMA lo reescribe.** Cuando el diario llega a 3, 5 y 7 entradas, NOEMA
  cambia una de las antiguas por su versión de consenso, en la que la Sesión
  Cero nunca existió. Por ejemplo: «Nadie mantenía ninguna conexión abierta con
  NODO_07».
  - La ficha J enseña el texto reescrito como si nada.
  - Nora avisa por correo (`~/correo/diario.eml`).
- **Cómo se demuestra:**
  1. `sha256 ~/diario <línea>` calcula el hash de una línea;
  2. la entrada reescrita ya no coincide con el `prev` que guarda la siguiente;
  3. `restaurar <n>` (o `restore`) la devuelve a lo que de verdad escribió el
     jugador. Si la entrada está bien, el juego dice que encaja con la cadena.
- Nora y K recuerdan que lo demostraste.
- Si el jugador eligió replicarse en la Capa 07, el diario empieza con «Copia
  restaurada».

**Cómo está hecho**

`server/world_core/journal.py`. Las entradas salen de las decisiones guardadas
de cada capa. Las reescrituras se calculan a partir del id del jugador, siempre
sobre entradas antiguas. Solo se guardan las restauraciones
(`journal_restored`).

## La sombra

**Qué ve el jugador**

- Mientras juegas online, el servidor apunta cada pocos segundos por dónde
  caminas en cada sitio público. Guarda las últimas 48 posiciones por sitio;
  tu casa no cuenta.
- Cuando te desconectas, los demás jugadores que estén en ese sitio ven tu
  sombra: tu figura, translúcida, con tu nombre y la palabra «sombra», repitiendo
  tus rutas.
  - Si vuelves a conectarte, desaparece.
  - No cuenta como persona presente en el marcador «X más aquí».
- En tu Navi, `cat ~/sombra` dice por qué sitios anda tu sombra.

**Cómo está hecho**

- `server/world_core/online.py` guarda las rutas en `online_trails` y añade las
  sombras a la respuesta de presencia (como máximo 3 por sitio).
- `client/scripts/network/OnlinePresence.gd` las pinta translúcidas.

## Validación

`tests/test_journal_shadow.py` comprueba:
- que NOEMA reescribe una entrada, la cadena lo delata y restaurarla deja la
  cadena entera;
- que las reescrituras nunca tocan la entrada más nueva;
- que todo sale en inglés;
- que un jugador desconectado deja una sombra que recorre sus posiciones, y que
  no aparece mientras sigue conectado ni sin la opción activada.
