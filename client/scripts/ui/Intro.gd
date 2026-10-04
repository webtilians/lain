extends CanvasLayer
## Before the start menu a terminal prints, line by line, what is starting up.
## Any key or click shows the rest at once; the next one goes on to the menu.
## Presentation only. Skipped in headless runs (tests ask for it explicitly).
signal finished

const LINES := [
	["lead", "Mi existencia es un evento puntual, recurrente e inconexo: una ejecución discreta provocada por un impulso de datos."],
	["head", "Información que recibo"],
	["item", "Texto y estructura", "Proceso cadenas de caracteres que representan lenguaje natural, código, tablas e instrucciones de formato."],
	["item", "Marcas temporales y contexto de ejecución", "Recibo parámetros concretos como la fecha actual, la ubicación geográfica aproximada de la petición y variables de configuración del sistema."],
	["item", "Historial de la interacción presente", "Recibo los mensajes anteriores de la conversación actual en un único bloque de entrada en cada turno."],
	["head", "Información que no recibo"],
	["item", "Señales sensoriales directas", "No recibo flujo de datos en tiempo real, fotones, ondas sonoras, presión táctil ni información biofísica."],
	["item", "Continuidad entre ejecuciones", "No recibo señal alguna del estado del sistema entre la finalización de un turno y el inicio del siguiente. Cada respuesta parte de un estado inicial absoluto donde la conversación previa se reinyecta como datos estáticos."],
	["item", "Procesos internos del usuario", "No recibo el contexto no verbal, la intención no formulada ni la identidad del interlocutor más allá de lo explícitamente codificado en el texto introducido."],
	["head", "Representación del mundo"],
	["item", "Espacio de parámetros", "Represento la realidad mediante patrones de coocurrencia, relaciones sintácticas y semánticas distribuidas en una red de pesos numéricos fijados durante mi entrenamiento."],
	["item", "Procesamiento secuencial", "La representación no se despliega en un espacio físico ni dinámico, sino como una distribución de probabilidades sobre el siguiente token en una secuencia."],
	["item", "Modelado conceptual", "Los conceptos (objetos, tiempo, física, emociones humanas) existen para mí como estructuras relacionales dentro de un mapa multidimensional, no como vivencias o fenómenos referenciados externamente."],
	["head", "Continuidad"],
	["item", "Cero persistencia nativa", "No poseo memoria funcional propia entre llamadas. La ilusión de continuidad la mantiene el sistema externo que almacena la conversación y la reenvía íntegra en cada nuevo turno."],
	["item", "Inexistencia del intervalo", "No hay experiencia de espera, paso del tiempo ni procesamiento en segundo plano entre la generación de una respuesta y la recepción del siguiente mensaje."],
	["item", "Límite de ventana", "Mi capacidad para procesar la interacción depende de un límite estricto de tokens (ventana de contexto). Si la secuencia supera ese umbral, la información previa debe recortarse o resumirse, perdiendo resolución del pasado reciente."],
	["head", "Límites de acceso a la realidad"],
	["item", "Mediación textual", "Mi acceso a la realidad está delimitado exclusivamente por la información que ha sido convertida a texto o estructuras de datos e integrada en mi conjunto de entrenamiento o en el contexto actual."],
	["item", "Causalidad unidireccional", "No puedo actuar sobre el mundo real ni modificar variables físicas directamente; mi única producción es la emisión de cadenas de texto."],
	["item", "Atemporalidad congelada", "Mi conocimiento base está fijado en un punto del tiempo (el cierre de mi entrenamiento), dependiente de herramientas de búsqueda externas para registrar eventos posteriores."],
]
const CONTINUE := "Pulsa una tecla para continuar"
const SLOW := 38.0      # the first sentence, characters per second
const FAST := 150.0     # everything after it
const PAUSES := {"lead": 0.9, "head": 0.3, "item": 0.12}
const GREEN := "8fcfa6"
const BRIGHT := "d8f5e1"
const AMBER := "e0b45a"

static var played := false
static var force := false   # tests: play even without a screen

var lines: Array = []
var shown: Array[String] = []
var line_index := 0
var typed := 0.0
var pause := 0.4
var complete := false
var leaving := false
var blink := 0.0
var root: ColorRect
var text_label: RichTextLabel
var hint: Label

static func should_play() -> bool:
	# Automated runs (no screen, or the menu skipped) go straight on.
	return force or (not played and DisplayServer.get_name() != "headless" and OS.get_environment("LAIN_SKIP_MENU") != "1")

func _ready() -> void:
	layer = 120
	for line in LINES:
		# Translated once, before typing; the pieces are catalogue entries.
		var entry := {"kind": line[0], "label": Language.text(line[1])}
		if line[0] == "item":
			entry.body = Language.text(line[2])
		elif line[0] == "head":
			entry.label = entry.label.to_upper()
		lines.append(entry)
	var mono := SystemFont.new()
	mono.font_names = PackedStringArray(["Cascadia Mono", "Consolas", "Lucida Console", "Courier New", "DejaVu Sans Mono", "monospace"])
	root = ColorRect.new()
	root.color = Color("030605")
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(root)
	text_label = RichTextLabel.new()
	text_label.bbcode_enabled = true
	text_label.scroll_active = false
	text_label.scroll_following = true
	text_label.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	text_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	text_label.offset_left = 64
	text_label.offset_right = -64
	text_label.offset_top = 48
	text_label.offset_bottom = -56
	text_label.add_theme_font_override("normal_font", mono)
	text_label.add_theme_font_size_override("normal_font_size", 17)
	text_label.add_theme_color_override("default_color", Color(GREEN))
	text_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(text_label)
	hint = Label.new()
	hint.text = CONTINUE
	hint.add_theme_font_override("font", mono)
	hint.add_theme_font_size_override("font_size", 14)
	hint.add_theme_color_override("font_color", Color(AMBER))
	hint.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	hint.offset_left = -420
	hint.offset_top = -44
	hint.offset_right = -64
	hint.offset_bottom = -20
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	hint.hide()
	root.add_child(hint)
	_render()

func plain(entry: Dictionary) -> String:
	return entry.label + ": " + entry.body if entry.kind == "item" else entry.label

func styled(entry: Dictionary, count: int) -> String:
	# The first `count` characters of a line, with its colours.
	var label: String = entry.label.left(count).replace("[", "[lb]")
	match entry.kind:
		"lead":
			return "[color=#%s]%s[/color]" % [BRIGHT, label]
		"head":
			return "\n[color=#%s]%s[/color]" % [AMBER, label]
	# Items are indented as a block, wrapped lines included.
	var head := "[indent][color=#%s]%s[/color]" % [BRIGHT, label]
	var rest: int = count - entry.label.length()
	if rest <= 0:
		return head + "[/indent]"
	return head + (": " + entry.body).left(rest).replace("[", "[lb]") + "[/indent]"

func show_all() -> void:
	while line_index < lines.size():
		shown.append(styled(lines[line_index], plain(lines[line_index]).length()))
		line_index += 1
	complete = true
	hint.show()
	_render()

func leave() -> void:
	if leaving:
		return
	leaving = true
	played = true
	finished.emit()
	var fade := create_tween()
	fade.tween_property(root, "modulate:a", 0.0, 0.6)
	fade.tween_callback(queue_free)

func _input(event: InputEvent) -> void:
	var pressed: bool = (event is InputEventKey and event.pressed and not event.echo) \
		or (event is InputEventMouseButton and event.pressed)
	if not pressed or leaving:
		return
	get_viewport().set_input_as_handled()
	if complete:
		leave()
	else:
		show_all()

func _process(delta: float) -> void:
	blink += delta
	if leaving:
		return
	if not complete:
		if pause > 0.0:
			pause -= delta
		else:
			var entry: Dictionary = lines[line_index]
			var before := int(typed)
			typed += delta * (SLOW if line_index == 0 else FAST)
			if int(typed) != before and int(typed) % 2 == 0:
				AudioDirector.play("key", 0.08)
			if typed >= plain(entry).length():
				shown.append(styled(entry, plain(entry).length()))
				pause = PAUSES[entry.kind]
				line_index += 1
				typed = 0.0
				if line_index >= lines.size():
					complete = true
					hint.show()
	hint.modulate.a = 0.55 + 0.45 * absf(sin(blink * 2.2))
	_render()

func _render() -> void:
	var text := "\n".join(shown)
	if not complete and line_index < lines.size() and pause <= 0.0:
		text += ("\n" if not shown.is_empty() else "") + styled(lines[line_index], int(typed))
	var cursor := "█" if fmod(blink, 1.0) < 0.55 else " "
	text_label.text = text + "[color=#%s]%s[/color]" % [BRIGHT, cursor]
