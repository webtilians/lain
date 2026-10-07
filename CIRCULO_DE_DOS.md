# Sesión Cero · Círculo de dos

El primer reto que **solo se resuelve entre dos jugadores**, cada uno en un
armario de enlace distinto. Es la idea de la biblia: el multijugador es la red.

Los Círculos de Ryoko son enlaces sin dueño. Para abrir uno, dos personas
acuerdan una clave que **nunca viaja**: un intercambio Diffie-Hellman. Ni
KAGAMI (que lo copia todo) ni NOEMA (que reescribe los registros) pueden leerla,
porque nunca pasa por ningún servidor.

## Cómo se juega

Lo puede hacer cualquiera que ya esté conectado a Indara (desde la Capa 03).
Ryoko lo cuenta en `~/correo/circulos.eml`.

1. Una persona va a un armario (el de la estación, el del aula o el del
   videoclub) y escribe `circulo abrir`. Recibe un código (C-4821), los números
   públicos p y g y **su número secreto a**.
2. La otra persona va a **otro** armario y escribe `circulo unirse C-4821`
   (`circulo lista` enseña los círculos que esperan). Recibe su secreto b.
3. Cada una calcula su valor público con la calculadora del terminal,
   `powmod g <secreto> p`, y lo publica: `circulo publicar <valor>`.
4. Con el valor de la otra (`circulo ver`), cada una calcula la clave:
   `powmod <valor de la otra> <su secreto> p`. Sale el mismo número para las dos,
   sin decírselo.
5. Las dos la confirman con `circulo enlazar <clave>`, **en menos de 10
   minutos**. Entonces el círculo se abre y queda en el registro de los
   Círculos (`cat /var/circulos/registro`). Nora se entera, y lo recuerda.

`man dh` explica el intercambio con números pequeños; `man circulo` y
`man powmod`, las órdenes. Si te equivocas, el terminal te dice por qué: un
valor público que no sale de tu secreto, una clave que no es la vuestra…

## Por qué obliga a colaborar

- Hacen falta dos personas en **dos armarios distintos**: desde el mismo no se
  puede unir.
- Las dos tienen que confirmar casi a la vez (10 minutos).
- No se pueden hablar por el chat del juego, porque el chat solo llega a quien
  está en tu misma zona. Se coordinan por el propio círculo (`circulo ver`) o
  quedando fuera del juego.

## Cómo está hecho

- `server/world_core/duo.py`: una capa más del terminal (órdenes `circulo` y
  `powmod`), tablas `duo_links` y `duo_members`, el registro, el correo de Ryoko,
  sus páginas de manual y el recuerdo de Nora.
- Pruebas: `tests/test_duo.py`, con dos jugadores reales en dos armarios: el
  flujo completo, los errores, los 10 minutos, salir, el manual y el inglés.
