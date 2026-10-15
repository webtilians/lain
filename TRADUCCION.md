# LAIN en tres idiomas (español / English / русский)

El juego se escribe en **español**: es el idioma fuente. El inglés y el ruso salen
de un catálogo revisado cada uno:

- `server/content/i18n/en.json`: texto en español → texto en inglés.
- `server/content/i18n/ru.json`: texto en español → texto en ruso (las mismas claves).
- `client/translations/`: copias idénticas para el cliente
  (`python tools/sync_translations.py` las copia y comprueba los huecos).

## El ruso

- Se elige en el menú de inicio («Русский») o con **F8**, que pasa por los tres
  idiomas. Al elegirlo sale un saludo, «Привет, Оля! Мы тебя ждали.»: un guiño a
  Olya, que lleva el juego a sus amigos (`client/scripts/core/Language.gd`).
- Las órdenes del terminal se escriben como en inglés (`lab show KU-01`, `kumo rule
  allow …`); los textos rusos las citan así.
- Los personajes y Kumo contestan en ruso (la IA recibe la orden de hacerlo).
- Las convocatorias del vigía se escriben en español e inglés: en ruso se leen en
  inglés.
- Al jugador se le habla en masculino cuando el ruso obliga a elegir («ты вернулся»).
- La traducción es de Claude; conviene que la repase alguien nativo.

## Cómo funciona

- El jugador elige idioma en el menú de inicio (o con **F8**). El cliente lo
  guarda en el PC y lo manda en cada petición (`X-Lain-Language`).
- **Cliente:** Godot traduce solo los textos fijos de botones y etiquetas.
  Las frases con datos usan plantillas: `"Sesión: {v0}"` → `"Signed in: {v0}"`.
  Los datos (nombres, números, identificadores) no se traducen.
- **Servidor:** `i18n.payload()` traduce los campos de texto de cada respuesta
  (`text`, `line`, `title`, `goal`…). Nunca toca el chat, las hipótesis, los
  programas, los datos de cuenta ni los bytes del terminal. Lo guardado en la
  base de datos sigue en español.
- **IA:** los personajes responden en el idioma del jugador.
- **Lo que escribe el jugador:** los reconocedores de frases (contraseñas,
  «mi perro se llama…», «¿qué pasó la última vez…?») entienden español e
  inglés.
- **Capa 03:** las pruebas con huella (segmentos, diario) se generan en el
  idioma con el que el jugador empezó la capa y no cambian después.

## Al añadir una fase nueva

1. Escribe los textos en español, como siempre.
2. Añade su traducción a `server/content/i18n/en.json` **y a `ru.json`**. Usa `{v0}`,
   `{v1}`… para las partes variables (en ruso pueden cambiar de orden).
3. `python tools/sync_translations.py` (copia al cliente y valida).
   `tests/test_i18n_russian.py` falla si un texto con inglés no tiene ruso.
4. Las pruebas del CI fallan si un texto que ve el jugador no tiene
   traducción: el auditor (`tools/i18n_audit_plugin.py`) recorre toda la
   batería en modo estricto. Para buscarlos antes:

   ```powershell
   $env:LAIN_I18N_AUDIT = "outputs/i18n-audit.json"; python -m pytest -q -p tools.i18n_audit_plugin
   python tools/i18n_templates.py   # frases compuestas del cliente
   ```

`tests/test_i18n_english.py` recorre el prólogo, las conversaciones y el
terminal en inglés buscando texto en español; `client/tools/test_i18n.gd`
comprueba el menú y el cambio de idioma.
