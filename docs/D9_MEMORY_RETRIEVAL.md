# LAIN D9 · Memoria de declaraciones generales y recuperación por paráfrasis

D9 parte de D8-r3. No modifica el cliente Godot ni reinicia la partida.
La base de datos conserva el historial original y crea una tabla auxiliar
para indexar **declaraciones explícitas del jugador por destinatario**.

## 1. Recuperación de declaraciones recientes por tema

Ya no hace falta una regla específica para cada atributo del jugador.
D9 reconoce un conjunto delimitado de formas explícitas, por ejemplo:

- `Mi perro se llama Tango.` → después `Mi perro ahora se llama Lupo.`
- `Mi color favorito es azul.`
- `Mi lugar favorito ahora es Málaga.`

Al preguntar `¿Cómo se llama mi perro?`, `¿Qué nombre tiene mi perro?`
o `¿Cuál es mi color favorito?`, World Core devuelve una cita atribuida
de la **última declaración reconocida para ese tema**. Las versiones
anteriores no se borran: siguen en la conversación y sus recuerdos.
Esta respuesta aparece con `DIALOGUE // SOURCE = GROUNDED_RECALL`.

La cita es **testimonio del jugador**, no una verdad verificada del
universo del juego. Nora no recibe las declaraciones privadas de K.
Para consultas a un personaje sobre conversaciones anteriores, D9 puede
leer declaraciones compatibles del historial D7/D8 sin vaciar
`world.db`.

**Límite importante:** D9 no comprende todavía cualquier frase del
lenguaje natural ni resuelve contradicciones narrativas arbitrarias.
Reconoce las formas explícitas indicadas y las preguntas directas por
el mismo tema. No indexa como hechos afirmaciones inciertas, frases
incompletas ni testimonios de terceros. Las contraseñas conservan
la implementación particular y las protecciones D8-r3.

## 2. Búsqueda por paráfrasis con tu Ollama (opcional)

La recuperación episódica por defecto mantiene la búsqueda léxica y
los últimos recuerdos: no requiere instalar nada nuevo. Si quieres
experimentar con **preguntas formuladas con otras palabras**, D9 puede
pedirle al Qwen local que sugiera términos de búsqueda a partir de
la **pregunta del jugador solamente**, sin enviarle recuerdos para
esta expansión. Esas palabras solo afectan al orden de búsqueda:
**nunca crean nuevas memorias o hechos**.

Para habilitarla, antes de arrancar Uvicorn establece
`$env:LAIN_MEMORY_SEMANTIC="1"`. La opción está apagada por defecto
porque supone una llamada adicional al modelo (hasta 4 segundos); si
falla, se utiliza automáticamente la búsqueda léxica. Es **expansión
semántica de consultas mediante el LLM**, no embeddings vectoriales
ni integración con INFINITO. La fiabilidad dependerá de la calidad
de las sugerencias de Qwen.

Si habilitas un proveedor remoto para el diálogo, la expansión puede
enviar también la pregunta a ese proveedor. Con la configuración
local habitual, Ollama recibe la pregunta dentro del propio PC.

## 3. Prueba reproducible sin reiniciar tu mundo

Haz una copia de `world.db` fuera del repositorio y arranca la rama
`develop/isometric-0.2-d9` con tu configuración actual de Ollama.

Dile a K, en este orden:

1. `Mi perro se llama Tango.`
2. `Mi perro ahora se llama Lupo.`
3. `¿Qué nombre tiene mi perro?`

K debe citar **Lupo** atribuyéndoselo a lo que tú le contaste,
sin sustituirlo por **Tango**. Pregunta después a Nora: no debería
recuperar una declaración privada hecha exclusivamente a K.

Como segunda prueba, dile a Nora `Mi color favorito es azul.`
y pregunta `¿Cuál es mi color favorito?`. Nora debe poder citar
ese testimonio suyo, aunque no se lo hayas dicho a K.

Para probar la expansión, activa la variable indicada y haz a K
una pregunta sobre un recuerdo antiguo con términos diferentes.
Si falla la recuperación, copia el mensaje concreto y el resultado;
una prueba de paráfrasis no demuestra memoria semántica general.

## 4. Pruebas automáticas

```powershell
cd C:\Users\ENRIQUE\lain; .\.venv\Scripts\Activate.ps1; python -m pytest -q
```

El conjunto incluye regresiones de contraseñas, claves falsas de
NODE_07, privacidad entre agentes, versiones antiguas y nuevas,
historial legado, consultas con paráfrasis, proveedor simulado y
respaldo si el modelo local no responde. Las pruebas usan bases
temporales y no invocan Ollama real.
