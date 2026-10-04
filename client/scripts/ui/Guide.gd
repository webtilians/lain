extends CanvasLayer
## The first minutes. A short guide advances on its own as the player walks,
## opens the diary, goes out, finds the school and talks to someone; after
## that the prologue's objective stays on screen. The first time a terminal
## opens it explains how to ask for help. F1 hides or shows it.
## Presentation only: it reads the snapshot and the open windows, and keeps
## its progress in user://guide.cfg on this PC.
const STEPS := [
	{"id": "move", "title": "1/5 · CAMINAR", "text": "Camina con W A S D."},
	{"id": "journal", "title": "2/5 · TU DIARIO", "text": "Pulsa J para abrir tu diario. Ahí está siempre tu objetivo."},
	{"id": "leave", "title": "3/5 · SALIR", "text": "Acércate a la puerta y pulsa E para salir al barrio."},
	{"id": "school", "title": "4/5 · EL COLEGIO",
		"text": "Busca el colegio: es la C del mapa, arriba a la derecha. Entra con E junto a la puerta."},
	{"id": "talk", "title": "5/5 · HABLAR", "text": "Acércate a alguien y pulsa E. Puedes escribirle lo que quieras."},
]
const WELCOME := "Esta guía te acompaña los primeros minutos."
const FINISHED := "Ya sabes lo básico. Tu objetivo queda aquí; si te pierdes, abre el diario con J."
const SHELL_TIP := "Consejo: escribe help para ver las órdenes, y pista si te atascas."
const DOS_TIP := "Consejo: escribe una orden y pulsa Enter. Lo que te contó Ryoko está en tu diario (J)."
const WALK := 2.5
const FINISHED_SECONDS := 9.0

var config_path := "user://guide.cfg"
var done: Array = []
var tips: Array = []
var hidden_by_player := false
var decided := false
var start_position = null
var finished_left := 0.0
var shell_was_open := false
var dos_was_open := false
var panel: PanelContainer
var title_label: Label
var text_label: Label
var footer: Label

func _ready() -> void:
	layer = 85
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build()
	load_progress()

func _build() -> void:
	panel = PanelContainer.new()
	panel.name = "GuidePanel"
	panel.position = Vector2(24, 190)
	panel.custom_minimum_size = Vector2(380, 0)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.025, 0.03, 0.045, 0.84)
	style.border_color = Color("c2253f")
	style.border_width_left = 3
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_right = 4
	style.content_margin_left = 16
	style.content_margin_right = 14
	style.content_margin_top = 10
	style.content_margin_bottom = 10
	panel.add_theme_stylebox_override("panel", style)
	add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(box)
	title_label = _label(box, 13, Color("e7b493"))
	text_label = _label(box, 16, Color("dfe3ea"))
	footer = _label(box, 11, Color("8d95a5"))
	footer.text = "F1 · ocultar o mostrar la guía"
	panel.hide()

func _label(parent: Control, size: int, color: Color) -> Label:
	var label := Label.new()
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size = Vector2(350, 0)
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	label.add_theme_color_override("font_shadow_color", Color("0b0d10"))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label

func load_progress() -> void:
	var config := ConfigFile.new()
	if config.load(config_path) != OK:
		return
	done = Array(config.get_value("guide", "done", []))
	tips = Array(config.get_value("guide", "tips", []))
	hidden_by_player = bool(config.get_value("guide", "hidden", false))
	decided = bool(config.get_value("guide", "decided", false))

func save_progress() -> void:
	var config := ConfigFile.new()
	config.set_value("guide", "done", done)
	config.set_value("guide", "tips", tips)
	config.set_value("guide", "hidden", hidden_by_player)
	config.set_value("guide", "decided", decided)
	if config.save(config_path) != OK:
		push_warning("No se pudo guardar la guía.")

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F1:
		toggle()
		get_viewport().set_input_as_handled()

func toggle() -> void:
	hidden_by_player = not hidden_by_player
	save_progress()

func stage() -> String:
	return str(WorldApi.snapshot.get("prologue", {}).get("stage", "LEGACY"))

func location() -> String:
	return str(WorldApi.snapshot.get("player", {}).get("location", ""))

func current_step() -> Dictionary:
	for step in STEPS:
		if not step.id in done:
			return step
	return {}

func _decide() -> void:
	# Only someone at the very start of the prologue gets the steps; everyone
	# who already played keeps just the objective and the terminal tips.
	decided = true
	if stage() != "FIND_TEACHER":
		for step in STEPS:
			if not step.id in done:
				done.append(step.id)
	save_progress()

func _met(id: String, player: Node3D) -> bool:
	match id:
		"move":
			if start_position == null:
				start_position = player.global_position
			return player.global_position.distance_to(start_position) >= WALK
		"journal":
			return CharacterJournal.backdrop.visible
		"leave":
			return not location().is_empty() and location() != "APARTMENT"
		"school":
			return location() in ["SCHOOL", "SCHOOL_LAB"] or stage() not in ["FIND_TEACHER", "LEGACY"]
		"talk":
			return EventDialog.visible
	return false

func _process(delta: float) -> void:
	var player := get_tree().get_first_node_in_group("player") as Node3D
	if player == null or WorldApi.snapshot.is_empty() or ServerConnection.awaiting_login:
		panel.hide()
		return
	if not decided:
		_decide()
	_terminal_tips()
	var before := done.size()
	for step in STEPS:
		if not step.id in done and _met(step.id, player):
			done.append(step.id)
	if done.size() != before:
		AudioDirector.play("hint")
		if current_step().is_empty():
			finished_left = FINISHED_SECONDS
		save_progress()
	finished_left = maxf(0.0, finished_left - delta)
	_show(current_step())

func _show(step: Dictionary) -> void:
	var busy: bool = (SceneRouter.get("loading") == true or EventDialog.visible or Workshop.is_open()
		or ShellTerminal.is_open() or PrologueTerminal.surface.visible or CharacterJournal.backdrop.visible)
	if not step.is_empty():
		title_label.text = step.title
		text_label.text = (WELCOME + "\n" + step.text) if step.id == "move" else step.text
	elif finished_left > 0.0:
		title_label.text = "GUÍA COMPLETADA"
		text_label.text = FINISHED
	elif stage() in ["FIND_TEACHER", "FIND_RYOKO", "FIND_TERMINAL"]:
		title_label.text = "OBJETIVO"
		text_label.text = str(WorldApi.snapshot.get("prologue", {}).get("hint", ""))
	else:
		text_label.text = ""
	panel.visible = not hidden_by_player and not busy and not text_label.text.is_empty()

func _terminal_tips() -> void:
	# The first time each terminal opens, one line on how to get unstuck.
	var shell_open: bool = ShellTerminal.is_open()
	if shell_open and not shell_was_open and not "shell" in tips:
		ShellTerminal._print(Language.text(SHELL_TIP))
		tips.append("shell")
		save_progress()
	shell_was_open = shell_open
	var dos_open: bool = PrologueTerminal.surface.visible
	if dos_open and not dos_was_open and stage() == "FIND_TERMINAL" and not "dos" in tips:
		PrologueTerminal.transcript.text += "\n" + Language.text(DOS_TIP) + "\n"
		tips.append("dos")
		save_progress()
	dos_was_open = dos_open
