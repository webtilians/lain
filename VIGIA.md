# Sesión Cero · El vigía: la Malla sigue a la tecnología real

Etapa 2 de [EVOLUCION.md](EVOLUCION.md). Cada pocos días el servidor lee
noticias reales de tecnología y abre, **él solo**, una convocatoria nueva en uno
de los tres centros de investigación. Nadie tiene que estar pendiente: tú las
revisas cuando quieras en el panel y borras las que no te gusten.

## Los tres centros

| Centro | Orden | Dirige | Estudia |
|---|---|---|---|
| Instituto de Física del Puerto | `instituto` | Hideo Sakamoto | física: cuántica, fotones, medida, ordenadores cuánticos |
| Laboratorio de Inteligencias | `laboratorio` (o `lab`) | Takeshi Uno | IA: modelos de lenguaje, agentes, aprendizaje, datos |
| Archivo de Protocolos | `archivo` | Yasuo Ueda | redes y protocolos: internet, cifrado, seguridad, poscuántica |

Los tres funcionan igual que el Instituto ([INSTITUTO.md](INSTITUTO.md)):
`<centro>`, `<centro> ver <código>`, `<centro> leer <artículo>`,
`<centro> entregar <código> <respuesta>` y `<centro> registro`. Al principio el
Laboratorio y el Archivo están vacíos («el vigía del centro busca la
próxima»); el vigía los va llenando.

## Cómo trabaja el vigía

1. **Cada 3 días** (`LAIN_WATCH_DAYS`), el motor lee titulares de tres fuentes
   públicas:
   - **arXiv**: física cuántica, criptografía, redes e IA;
   - **Hacker News**: la portada;
   - **RFC Editor**: los últimos estándares de internet.
2. Le pasa los titulares a la IA de los personajes (Gemini), con la lista de lo
   que ya se ha estudiado. La IA elige **una** noticia y un centro, y escribe en
   español y en inglés:
   - el título y el resumen;
   - un artículo de estudio;
   - una frase que une la noticia con el ejercicio;
   - qué aprende la Malla cuando se completa;
   - qué recordará el director.
3. **El ejercicio no lo escribe la IA.** Elige uno de cinco tipos y el código lo
   rellena con números propios de cada jugador. Por eso todas las convocatorias
   tienen solución y se comprueban solas:

   | Tipo | Qué hay que hacer | Con qué |
   |---|---|---|
   | `xor` | XOR de dos bytes | a mano |
   | `powmod` | g^x mod p | `powmod` |
   | `hamming` | encontrar el bit erróneo de un bloque Hamming(7,4) | a mano |
   | `huella` | sha256 de una línea de un fichero | `sha256` |
   | `contar` | cuántas líneas de un registro dicen una palabra | `grep` |

   La parte de experimentar es un primer caso de práctica, y la de demostrar,
   otro caso con los números del jugador. Los ficheros están en
   `/malla/<centro>/<código>/`.
4. La convocatoria se **publica al momento** con el siguiente código libre del
   centro (QB-02, IA-01, PR-01…). Su director manda un correo a casa de cada
   jugador (`~/correo/<código>.eml`). Si la terminan **tres personas**, su
   tecnología entra en la Malla para todos: la cinemática «La Malla
   evoluciona», los centros la enseñan como sabida y el director y Nora la
   recuerdan.

Si algo falla (no hay red, la IA no responde o devuelve algo que no cuadra),
no se publica nada y lo vuelve a intentar a las 6 horas. Una respuesta de la IA
solo vale si nombra un centro, un tipo de ejercicio y una noticia de la lista, y
trae todos los textos. El enlace de la fuente siempre sale de la lista, nunca de
la IA.

## Revisar y borrar (panel del servidor)

```powershell
.\vps.ps1 -Panel
```

La sección **Convocatorias del vigía** enseña cada convocatoria con:
- su centro, título y tipo de ejercicio;
- qué trae a la Malla;
- cuántos la han terminado y cuándo se creó;
- un enlace a la noticia original.

Desde ahí puedes:
- **Borrar** una convocatoria: desaparece del juego para todos, y con ella lo
  que hubiera traído a la Malla. Su código no se vuelve a usar.
- **Buscar una convocatoria ahora**, sin esperar a los 3 días.
- Ver **las últimas búsquedas**, con lo que salió bien y lo que falló.

El panel solo se abre por el túnel SSH. Los botones solo funcionan desde la
propia página del panel: otra web abierta en tu navegador no puede pulsarlos.

## Ajustes

| Variable (`/etc/lain/lain.env`) | Por defecto | Qué hace |
|---|---|---|
| `LAIN_WATCH_DAYS` | `3` | días entre convocatorias |
| `LAIN_WATCH` | `1` | `0` para el vigía |

Sin la IA encendida (`-Gemini`), el vigía espera sin hacer nada. Usa una
llamada a Gemini cada 3 días: cabe de sobra en el plan gratuito.

## Cómo está hecho

- `server/world_core/watch.py`: las fuentes, la llamada a la IA, la
  validación, el registro de búsquedas (`research_watch`) y el hilo que lo
  comprueba cada media hora. Arranca con el servidor en línea (nunca en las
  pruebas ni en las partidas sin conexión).
- `server/world_core/research.py`: los tres centros, las convocatorias (las
  escritas a mano y las del vigía, en la tabla `research_calls`), el progreso,
  el registro, el umbral, los cinco generadores de ejercicios, los correos y
  lo que ven el panel, el cliente y los personajes.
- `server/world_core/admin.py` y `server/api.py`: la sección del panel y sus
  dos acciones (`POST /admin/research/<código>/delete` y
  `POST /admin/research/watch`).
- Pruebas: `tests/test_research.py`.
  - Las tres fuentes y un vigía con una IA de mentira.
  - Cada tipo de ejercicio resuelto solo con su enunciado y las órdenes del
    terminal.
  - El umbral y que lo malo de la IA no se publica.
  - El borrado desde el panel y el inglés.
