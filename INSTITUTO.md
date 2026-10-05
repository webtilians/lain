# Sesión Cero · El Instituto de Física del Puerto

El primer centro de investigación de la Malla (etapa 1 de
[EVOLUCION.md](EVOLUCION.md)). Lo dirige Hideo Sakamoto, el profesor de
ciencias del colegio, y se visita desde el terminal: casa o cualquier armario,
en cuanto el jugador está conectado a la Malla (Capa 03).

## Las convocatorias

Una convocatoria es una unidad de estudio con tres partes:

1. **Estudiar**: leer sus artículos (`instituto leer <artículo>`).
2. **Experimentar**: un ejercicio con el simulador del Instituto.
3. **Demostrar**: entregar un resultado que el servidor comprueba.

Quien termina las tres entra en el **registro del Instituto**
(`instituto registro`), con su nombre y el minuto. Cuando la terminan **tres
personas**, su tecnología **entra en la Malla para todos**: una orden nueva en
todos los terminales, una cinemática «La Malla evoluciona» que cada uno ve una
vez y lo que saben de ello Hideo y Nora cuando les hablas.

| Orden | Qué hace |
|---|---|
| `instituto` | portada: convocatorias abiertas, tu progreso y lo que ya sabe la Malla |
| `instituto ver QB-01` | una convocatoria: sus tres partes, con lo que llevas hecho |
| `instituto leer qubit` | un artículo (cuenta para la parte de estudiar) |
| `instituto entregar <canal> <clave>` | entrega el resultado de QB-01 |
| `instituto registro` | quién ha terminado cada convocatoria |

En inglés: `institute`, `show`, `read`, `submit`, `registry`.

## QB-01 · El qubit y la clave que delata al espía

**Estudiar**: los artículos `qubit` (superposición, bases Z y X, las puertas X,
Z y H) y `bb84` (el protocolo de Bennett y Brassard y por qué el espía deja
errores).

**Experimentar** con `qubit`, un simulador de un qubit: `qubit nuevo`,
`qubit x|z|h` y `qubit medir z|x`. El reto es conseguir que una medida en la
base X dé 1 **con total certeza**, es decir, preparar |-> antes de medir
(`qubit x` y luego `qubit h`, o `qubit h` y luego `qubit z`). Un 1 que sale por
suerte no cuenta.

**Demostrar** con `bb84`: Hideo hace de Alicia y el jugador de Bob.
1. `bb84 medir a` mide 24 fotones con bases elegidas al azar (o con las que
   escribas: 24 signos `+` o `x`).
2. `bb84 bases a`: Hideo dice sus bases, nunca sus bits. El terminal las pone
   alineadas con las tuyas y con tus bits.
3. `bb84 comparar a`: sacrificáis en público la mitad de las posiciones donde
   coincidís (la 1.ª, la 3.ª, la 5.ª…) y Hideo dice sus bits ahí.
4. La clave son tus bits en las demás posiciones donde coincidís, en orden:
   `instituto entregar a 0110…`

Uno de los dos canales está **pinchado**: alguien mide cada fotón por el
camino y lo reenvía. En ese canal la muestra siempre tiene al menos dos bits que
no coinciden (en torno a uno de cada cuatro), y Hideo no acepta su clave. En el
canal limpio no hay ningún error. El canal pinchado es fijo para cada jugador,
así que copiar el de otro no sirve.

Las comprobaciones explican qué falta: no se puede entregar sin haber medido,
sin las bases publicadas o sin comparar la muestra («antes de usar una clave hay
que comprobar que nadie escuchaba»). Medir otra vez empieza una ronda nueva.

**Trae a la Malla:** `qkd`. Antes de que lleguen las tres personas, `qkd` dice
cuántas faltan. Después enseña los enlaces cuánticos entre casa y los armarios
con su tasa de error (QBER): todos con un poco de ruido del cable menos uno, que
pasa del 20 % porque KAGAMI escucha, y cambia cada día. Prepara la amenaza de la
etapa 4 (un ordenador cuántico contra los Círculos).

## Cómo está hecho

- `server/world_core/research.py`: los centros de investigación (este y los
  dos que llena el vigía, [VIGIA.md](VIGIA.md)), con las órdenes `instituto`,
  `laboratorio` y `archivo`, el progreso, el registro, el umbral y lo que ven el
  cliente y los personajes (tablas `research_progress`, `research_unlocks` y
  `research_knowledge`).
- `server/world_core/institute.py`: lo propio de QB-01. Las órdenes `qubit`,
  `bb84` y `qkd`, las tablas `institute_qubit` e `institute_bb84`, el correo de
  Hideo, los artículos y las páginas de `man` (`man qubit`, `man bb84`,
  `man qkd`).
  - El simulador solo usa X, Z y H desde |0>, así que el qubit siempre está en
    |0>, |1>, |+> o |->.
  - Cada ronda de BB84 se calcula con una semilla del jugador, el canal y la
    ronda. Se repite hasta que la clave tiene al menos 4 bits y, si el canal
    está pinchado, la muestra enseña el espía.
- El estado del jugador lleva `research` (convocatorias terminadas y
  tecnologías que ya están en la Malla), ya en el idioma del jugador. `client/scripts/ui/Cinematic.gd` lo usa
  para dos cinemáticas: «La Malla aprende», al terminar una convocatoria, y «La
  Malla evoluciona», al entrar una tecnología. Las dos se pueden volver a ver
  desde el diario.
- Pruebas: `tests/test_institute.py` (el recorrido completo, leyendo la salida
  como lo haría un jugador, el canal pinchado, el simulador, las tres personas
  que traen `qkd`, y el inglés) y `client/tools/test_cinematic.gd`.
