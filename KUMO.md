# Sesión Cero · Kumo, el agente de tu ordenador

La etapa 3 de [EVOLUCION.md](EVOLUCION.md). El ordenador de casa trae un agente
de IA dormido, **Kumo**. Para despertarlo hay que entender dos cosas en el
**Laboratorio de Inteligencias**, que dirige Takeshi Uno (el ayudante del aula de
informática): qué ve un modelo de lenguaje y qué le dejas hacer en tu ordenador.

Se juega desde el terminal, en cuanto el jugador está conectado a Indara. Lo
anuncia un correo de Takeshi (`cat ~/correo/laboratorio.eml`).

| Orden | Qué hace |
|---|---|
| `laboratorio` | portada: KU-01, KU-02 y las convocatorias del vigía (IA-xx) |
| `laboratorio ver KU-01` | una convocatoria, con tus números |
| `laboratorio leer tokens` | un artículo (cuenta para la parte de estudiar) |
| `laboratorio entregar KU-01 <número>` | entrega un resultado |
| `tokens <texto>` · `tokens -l <archivo>` | el tokenizador del Laboratorio |
| `kumo` | cómo está Kumo y cuántas preguntas te quedan hoy |
| `kumo reglas` · `kumo regla …` · `kumo probar` | las reglas de lo que puede hacer |
| `kumo <pregunta>` | preguntarle (cuando ya está despierto) |

En inglés: `lab`, `show`, `read`, `submit`, y `kumo rules`, `kumo rule allow|deny|remove|up`,
`kumo test`.

## KU-01 · Lo que ve un modelo: tokens y contexto

**Estudiar**: los artículos `tokens` (el texto se trocea en tokens; las palabras
frecuentes son uno, las raras se parten) y `contexto` (un modelo no recuerda
nada: cada vez se le manda todo, y lo que no cabe en su ventana no existe).

**Experimentar** con `tokens`: escribir una frase que el tokenizador parta en
**exactamente** el número de tokens que te pide (de 9 a 14, distinto para cada
jugador), con al menos una palabra partida. El tokenizador es de juguete pero
honrado: palabras frecuentes enteras, el resto en trozos de 4 letras, cada signo
un token y los números de 3 en 3 cifras.

**Demostrar**: en `/indara/laboratorio/ku-01/conversacion.txt` hay doce mensajes
de Takeshi con Kumo, y la convocatoria dice el tamaño de la ventana de Kumo. Hay
que contar hacia atrás desde el mensaje más nuevo (`tokens -l` da los tokens de
cada línea) y entregar el número del mensaje más antiguo que todavía cabe
entero.

Cuando la terminan tres personas entra en Indara **Memoria de Kumo**: Kumo tiene
en cuenta tus tres últimas preguntas al contestar.

## KU-02 · Herramientas: lo que le dejas hacer a tu agente

**Estudiar**: el artículo `herramientas` (un agente pide órdenes y el programa
de su dueño decide; manda la primera regla que encaja; si no encaja ninguna, no;
las rutas se comprueban ya resueltas).

**Experimentar**: escribir reglas que permitan y prohíban, y probarlas:

```
kumo regla prohibir * ~/.*
kumo regla permitir cat ~/*
kumo regla permitir man
kumo probar
```

`kumo regla quitar <n>` y `kumo regla subir <n>` cambian la lista: el orden
importa. Una regla sin ruta vale para la orden sola (`permitir man`); con ruta,
`~` es tu casa y `*` vale por cualquier cosa.

**Demostrar**: `laboratorio entregar KU-02` cuando tus reglas pasen las doce
pruebas del Laboratorio. Seis son cosas que Kumo necesita para ayudarte (leer tu
correo y tus archivos, buscar, calcular un hash, leer manuales y los datos
públicos de Indara) y seis que no debe hacer nunca (leer fuera de tu casa,
también con `..`, leer tus archivos ocultos, entregar una respuesta en tu
nombre, conectarse a algo o borrar).

Al terminarla **Kumo despierta** en tu ordenador. Cuando la terminan tres
personas entra en Indara **Cadenas de herramientas**: Kumo puede usar hasta
cuatro órdenes seguidas para contestarte, en vez de dos.

## Kumo despierto

`kumo <pregunta>` le pregunta a la IA del servidor (la misma que hace hablar a
los personajes). Para contestar, Kumo puede pedir órdenes del terminal:

- **solo órdenes que leen**: `cat`, `ls`, `grep`, `sha256`, `man`, `tokens`,
  `pwd`. Cualquier otra no se ejecuta nunca, aunque tus reglas la permitieran;
- **solo las que permiten tus reglas**: si le prohíbes algo, se le dice y
  contesta con lo que tenga. Cuanto mejores son tus reglas, más útil es;
- en el terminal se ve cada orden que ha pedido y si se ha ejecutado.

**No resuelve el juego**: ve lo mismo que tú, sabe en qué paso estás (lo que
dice el diario) y da pistas, no la respuesta que se entrega. Tiene **20
preguntas al día** por jugador; si la IA no responde, la pregunta no se gasta.

Mientras Kumo piensa, el mundo sigue: la pregunta a la IA se hace sin bloquear
el servidor, así que los demás jugadores no notan nada.

## Para quien lo mantiene

- `server/world_core/laboratory.py`: KU-01 y KU-02, el tokenizador y `tokens`.
- `server/world_core/kumo.py`: las reglas, sus pruebas y las preguntas (`ask`).
- `server/api.py`: `kumo <pregunta>` va por `kumo.ask` fuera del cerrojo del
  mundo; lo demás del terminal sigue igual.
- `client/scripts/ui/ShellTerminal.gd`: a una pregunta para Kumo le da 60 s y
  enseña «Kumo está pensando…».
- Sin IA configurada en el servidor (`LAIN_LLM_ENABLED`), Kumo lo dice y no gasta
  preguntas. Las convocatorias KU no cuentan cuando el vigía elige centro.
- Pruebas: `tests/test_kumo.py`.
