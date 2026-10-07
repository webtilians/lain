# Beta 0.2: IA compartida sin registro del jugador

Rama `experiment/distribution-0.2-shared-ai`, basada en la beta portable
`experiment/distribution-0.1-windows-beta` (`d6505ae`). No requiere fusionar
ramas. El cliente Godot y el formato SQLite del mundo no cambian. La partida
sigue en `%LOCALAPPDATA%\LAIN\Beta01\save.db` para conservar el progreso.

## Qué está preparado y qué falta

El ejecutable obtiene una sesión anónima automáticamente y pide respuestas
al servicio del autor. Solo el autor necesita cuentas de Groq y Cloudflare.
Todavía hay que crear esas cuentas, desplegar el servicio, guardar su clave
y rellenar la URL pública antes de repartir la beta con IA activa.
El archivo distribuido trae la URL vacía: no se afirma que haya un servicio
ya contratado o publicado. Sin configuración conserva el modo local/Ollama.

Esto comparte acceso a IA, no partidas. Cada equipo ejecuta su propio World
Core y conserva su propio SQLite. No sincroniza jugadores, inventarios ni
control de Indara entre equipos.

## Activarlo una vez como autor

1. Crea una cuenta en [Groq](https://console.groq.com/keys) y genera una clave.
   No la pegues en chats, GitHub, Godot ni `lain-ai.json`.
2. Crea una cuenta en [Cloudflare](https://dash.cloudflare.com/sign-up).
   El servicio usa Workers y un Durable Object SQLite, disponible en el
   [plan gratuito](https://developers.cloudflare.com/durable-objects/platform/pricing/).
   No hace falta contratar un dominio. No actives un plan de pago para esta prueba.
3. En esta rama, con Node.js 22 o posterior instalado, abre PowerShell:

   ```powershell
   cd C:\Users\ENRIQUE\lain-demo01\services\shared-ai
   npm ci
   npx wrangler login
   npm run deploy
   npx wrangler secret put GROQ_API_KEY
   ```

   El inicio de sesión abre el navegador para TU cuenta. El último comando
   pide la clave en la terminal y la guarda como secreto de Cloudflare.
   El despliegue muestra una URL `https://lain-shared-ai.<tu-cuenta>.workers.dev`.
   Antes de guardar la clave, el servicio devuelve `AI_NOT_CONFIGURED`.
4. Usa el ZIP **Beta 0.2**, extrae todo y edita `lain-ai.json` junto a `LAIN.exe`:

   ```json
   { "gateway_url": "https://lain-shared-ai.TU-CUENTA.workers.dev" }
   ```

   Sustituye el ejemplo por la URL real. No cambies `Game` ni `Server`.
   El lanzador Beta 0.1 anterior no interpreta este archivo: hay que usar
   el nuevo lanzador y servidor. La URL es pública; no es la clave de Groq.
5. Abre `<URL>/health`: debe mostrar `ready: true`. Abre `LAIN.exe` y prueba
   una pregunta libre a un PNJ. Los recuerdos exactos y las reglas del
   prólogo mantienen sus respuestas verificadas aunque la IA esté activa.
6. Comprime de nuevo la carpeta con la URL rellenada y comparte ese ZIP
   completo con tus dos o tres probadores. Solo deben extraerlo y abrirlo.

Si cambias la clave del proveedor, basta actualizar el secreto del servicio.
Si cambia la URL, actualiza el archivo público en las copias del juego.

## Cuotas y privacidad

- Modelo inicial: `qwen/qwen3.8-27b`, sin razonamiento visible. La selección
  pertenece al servicio. El cliente no puede elegir modelos, herramientas
  ni destinos arbitrarios. El modelo debe estar disponible en TU cuenta;
  eso no puede verificarse sin una clave real.
- [Groq aplica límites a toda la organización](https://console.groq.com/docs/rate-limits).
  El plan consultado permite 8.000 tokens/minuto y 200.000/día para ese modelo,
  además de límites de solicitudes. Consulta los de tu cuenta antes de publicar.
  Los recuerdos y las instrucciones también consumen tokens: no es uso ilimitado.
- El servicio limita a 24 peticiones/minuto y 800/día en total, reserva un
  presupuesto de 7.000 tokens/minuto y 160.000/día, y admite dos peticiones
  simultáneas. Estima el prompt y reconcilia el consumo declarado por Groq;
  los fallos conservan su reserva. El límite del proveedor puede llegar antes.
- También limita por sesión (10/minuto, 200/día) y red (12/minuto, 300/día).
  Personas con la misma conexión comparten el límite de red. Crear sesiones
  nuevas no reinicia los límites globales o de red. Sesiones anónimas no
  equivalen a personas verificadas: para esta beta distribuye la URL entre
  probadores conocidos. Un abuso puede consumir la cuota gratuita compartida.
- Una respuesta de diálogo puede ocasionar otra llamada para proponer una
  entidad. La búsqueda semántica es opcional y se mantiene apagada en la beta.
- Solo se transmite la proyección del personaje que habla, con origen,
  propietario y cronología de los recuerdos. K y Nora no comparten memorias.
  La IA propone texto; World Core sigue autorizando cambios de estado.
- Cloudflare/Groq procesan los textos para responder. El código del servicio
  no registra ni persiste prompts, respuestas, partidas o claves del proveedor. El objeto
  guarda contadores, identificadores anónimos y un resumen criptográfico de
  la red que rota a diario. Los contadores diarios se reemplazan al día siguiente.
  La observabilidad del Worker está desactivada; no actives registros de cuerpos.
- Si se agota la cuota o hay una caída, el cliente espera lo indicado y usa
  las respuestas de respaldo. No reintenta en bucle ni carga otra cuenta de pago.

## Comprobación de desarrollo

```powershell
cd C:\Users\ENRIQUE\lain-demo01
..\lain\.venv\Scripts\python.exe -m pytest -q
..\lain\.venv\Scripts\python.exe -m unittest discover -s packaging -p "test_*.py" -v
cd services\shared-ai
npm test
npm run check
```

Los tests no consumen Groq. Incluyen ejecución en el runtime de Workers con
SQLite y un proveedor simulado, sesiones, límites, reinicio del coordinador,
concurrencia, cruce de medianoche, aislamiento y fallos. `npm run check` empaqueta
el despliegue sin publicar. GitHub Actions construye además el ZIP Windows
Beta 0.2 y arranca su servidor congelado contra un guardado desechable.

Para una prueba real con la URL ya publicada, usando solo contexto ficticio:

```powershell
$env:LAIN_AI_GATEWAY_URL="https://lain-shared-ai.TU-CUENTA.workers.dev"
$env:LAIN_LLM_TIMEOUT="25"
..\lain\.venv\Scripts\python.exe -m tools.diagnose_llm
```

Ejecuta ese diagnóstico desde la raíz del repositorio. Consume una petición
real; no lee partidas, no imprime la respuesta ni revela secretos. La calidad
de diálogo y las cuotas reales quedan pendientes de esta prueba con tu cuenta.
