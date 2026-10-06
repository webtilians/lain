# Sesión Cero · Jugar con mando

Desde la 0.29 el juego se maneja entero con un mando: un mando de Xbox, cualquier mando
compatible con XInput o uno de PlayStation (en Windows y en Mac). Se puede cambiar en
cualquier momento entre el mando y el teclado y el ratón; el juego se da cuenta solo y
enseña los botones del que estés usando.

| Botón | Qué hace |
|---|---|
| Stick izquierdo o cruceta | moverse, y moverse por los menús |
| A | interactuar (puertas, gente, ordenadores) y aceptar |
| B | cerrar y volver |
| Y | diario |
| X | chat |
| View (Back, Select) | guía |
| Stick derecho | desplazar textos largos (terminal, diario) |

En PlayStation, A es ✕, B es ○, X es □ e Y es △.

## Escribir con el mando

El terminal, el chat, el inicio de sesión y lo que le escribes a la gente necesitan texto.
Cuando llegas a un campo de texto con el mando, sale un **teclado en pantalla**:

- **cruceta o stick** para elegir tecla y **A** para escribirla;
- **X** borra, **Y** pone un espacio, **LB** y **RB** mueven el cursor;
- **Start** envía (como Enter), **B** cierra el teclado; para volver a abrirlo, A sobre el
  campo;
- **Mayús** para mayúsculas; hay números, símbolos del terminal (`/ _ ~ : + * < > | =`) y
  vocales con tilde.

En el terminal el teclado trae arriba las órdenes de siempre (`help`, `ls`, `cat`, `cd`,
`man`, `pista`, `grep`, `sha256`) y **Anterior** y **Siguiente** para el historial. En el
terminal del prólogo trae `telnet` y `23`; la dirección la tienes que averiguar tú.

En el terminal, la primera **B** cierra el teclado y la segunda, el terminal.

## Cómo está hecho

- `client/scripts/core/Gamepad.gd` (autoload):
  - añade el mando a las acciones del juego (`move_*`, `interact`, `journal`, `chat`,
    `guide`) y A y B a `ui_accept` y `ui_cancel`, que en Godot 4 no los traen;
  - recuerda si lo último usado fue el mando o el teclado y cambia los avisos «[E]» del
    mundo por «[A]»;
  - pone el foco en el primer botón de lo que se abre;
  - desplaza el texto con el stick derecho.
- `client/scripts/ui/PadKeyboard.gd` (el último autoload, para ver los botones antes que las
  ventanas): el teclado en pantalla. Un campo ofrece atajos con `set_meta("pad_words", …)`
  y un historial con `set_meta("pad_history", Callable)`.
- El diario, la guía, el chat, las cinemáticas, la intro, el menú de inicio, los diálogos,
  el taller y los terminales usan esas acciones en vez de teclas fijas.
- Prueba: `client/tools/test_gamepad.gd`, con eventos de mando simulados.
