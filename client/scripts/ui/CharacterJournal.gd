extends CanvasLayer
## J — readable, privacy-scoped player and NPC technical sheets + case journal.
## UI only: all state comes from the existing read-only WorldApi snapshot.

const JOURNAL_KEY := KEY_J

var backdrop: ColorRect
var details: RichTextLabel
var navigation: VBoxContainer
var active_player: Node = null
var current_view := "PLAYER"
var selected_actor_id := ""

func _ready() -> void:
	layer = 90
	backdrop = ColorRect.new()
	backdrop.color = Color(0.008, 0.018, 0.030, 0.96)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(backdrop)

	var outer := MarginContainer.new()
	outer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	outer.add_theme_constant_override("margin_left", 65)
	outer.add_theme_constant_override("margin_right", 65)
	outer.add_theme_constant_override("margin_top", 45)
	outer.add_theme_constant_override("margin_bottom", 45)
	backdrop.add_child(outer)

	var panel := PanelContainer.new()
	outer.add_child(panel)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 16)
	panel.add_child(margin)
	var root_box := VBoxContainer.new()
	root_box.add_theme_constant_override("separation", 12)
	margin.add_child(root_box)

	var header := HBoxContainer.new()
	root_box.add_child(header)
	var title := Label.new()
	title.text = "LAIN // ARCHIVO DE PERSONAJES Y SEÑALES    [J]"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var close_button := Button.new()
	close_button.text = "CERRAR"
	close_button.pressed.connect(close_journal)
	header.add_child(close_button)

	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root_box.add_child(body)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(270, 0)
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_child(scroll)
	navigation = VBoxContainer.new()
	navigation.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(navigation)

	var separator := VSeparator.new()
	body.add_child(separator)
	details = RichTextLabel.new()
	details.bbcode_enabled = false
	details.scroll_active = true
	details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	details.size_flags_vertical = Control.SIZE_EXPAND_FILL
	details.add_theme_font_size_override("normal_font_size", 19)
	body.add_child(details)
	backdrop.visible = false
	WorldApi.snapshot_updated.connect(_on_snapshot_updated)


func _unhandled_input(event: InputEvent) -> void:
	var key_event := event as InputEventKey
	if key_event == null or not key_event.pressed or key_event.echo:
		return
	if key_event.keycode != JOURNAL_KEY:
		return
	if backdrop.visible:
		close_journal()
	elif not EventDialog.visible:
		open_journal()
	get_viewport().set_input_as_handled()


func open_journal() -> void:
	if WorldApi.snapshot.is_empty():
		return
	backdrop.visible = true
	active_player = get_tree().get_first_node_in_group("player")
	if is_instance_valid(active_player):
		active_player.set_physics_process(false)
		active_player.set_process_unhandled_input(false)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_refresh_navigation()
	_render_view()


func close_journal() -> void:
	backdrop.visible = false
	if is_instance_valid(active_player):
		active_player.set_physics_process(true)
		active_player.set_process_unhandled_input(true)
	active_player = null


func _on_snapshot_updated(_snapshot: Dictionary) -> void:
	if not backdrop.visible:
		return
	_refresh_navigation()
	_render_view()


func _add_navigation(label_text: String, view: String, actor_id: String = "") -> void:
	var button := Button.new()
	button.text = label_text
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.pressed.connect(_choose_view.bind(view, actor_id))
	navigation.add_child(button)


func _refresh_navigation() -> void:
	for child in navigation.get_children():
		navigation.remove_child(child)
		child.queue_free()
	_add_navigation("TU FICHA", "PLAYER")
	_add_navigation("CASO // EL PULSO AUSENTE", "CASE")
	var sheets: Dictionary = WorldApi.snapshot.get("character_sheets", {})
	var actors: Array = sheets.get("visible_npcs", [])
	for item in actors:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var actor: Dictionary = item
		var actor_id := str(actor.get("id", ""))
		_add_navigation(
			str(actor.get("name", actor_id)) + " // "
			+ str(actor.get("role_label", "Habitante")),
			"NPC", actor_id,
		)


func _choose_view(view: String, actor_id: String) -> void:
	current_view = view
	selected_actor_id = actor_id
	_render_view()


func _render_view() -> void:
	match current_view:
		"CASE":
			_render_case()
		"NPC":
			_render_npc()
		_:
			_render_player()


func _render_player() -> void:
	var sheets: Dictionary = WorldApi.snapshot.get("character_sheets", {})
	var data: Dictionary = sheets.get("player", {})
	details.text = (
		"FICHA TÉCNICA // JUGADOR\n\n"
		+ "IDENTIDAD  " + str(data.get("name", "Desconocido")) + "\n"
		+ "ID  " + str(data.get("id", "")) + "\n"
		+ "CONTROL  HUMANO // TUS DECISIONES\n"
		+ "AFILIACIÓN  " + str(data.get("faction", "")) + "\n"
		+ "UBICACIÓN  " + str(data.get("location", "")) + "\n"
		+ "ENERGÍA  %.2f\n" % float(data.get("energy", 0.0))
		+ "NODOS CONOCIDOS  %d\n" % int(data.get("known_nodes", 0))
		+ "INVESTIGACIÓN NODE_07  " + str(data.get("case_status", "UNSEEN"))
		+ "\n\nLas fichas solo incluyen conocimientos accesibles al jugador."
	)


func _render_case() -> void:
	var data: Dictionary = WorldApi.snapshot.get("station_case", {})
	var content := (
		"EXPEDIENTE // " + str(data.get("title", "El pulso ausente"))
		+ "\n\nESTADO  " + str(data.get("status", "UNSEEN"))
		+ "\n\n" + str(data.get("summary", ""))
	)
	if str(data.get("status", "")) == "TRACE_FOUND":
		content += (
			"\n\nVuelve a NODE_07 en la estación e interactúa "
			+ "para compartir el rastro o archivarlo."
		)
	elif str(data.get("status", "")) == "RESOLVED":
		content += (
			"\n\nDECISIÓN  " + str(data.get("resolution", ""))
			+ "\nTESTIGOS QUE RECIBIERON TU TESTIMONIO  "
			+ str(data.get("witness_count", 0))
		)
	var responses: Array = data.get("responses", [])
	if not responses.is_empty():
		content += "\n\nREACCIONES OBSERVABLES:"
	for item in responses:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var reaction: Dictionary = item
		content += (
			"\n\n" + str(reaction.get("name", "Desconocido"))
			+ " — " + str(reaction.get("reaction", ""))
		)
	details.text = content


func _render_npc() -> void:
	var sheets: Dictionary = WorldApi.snapshot.get("character_sheets", {})
	var actors: Array = sheets.get("visible_npcs", [])
	for item in actors:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var actor: Dictionary = item
		if str(actor.get("id", "")) != selected_actor_id:
			continue
		details.text = (
			"FICHA TÉCNICA // PNJ\n\n"
			+ "IDENTIDAD  " + str(actor.get("name", "")) + "\n"
			+ "ID  " + selected_actor_id + "\n"
			+ "ROL  " + str(actor.get("role_label", "Habitante")) + "\n"
			+ "TENDENCIA  " + str(actor.get("focus", "")) + "\n"
			+ "UBICACIÓN OBSERVADA  "
			+ str(actor.get("observed_location", "")) + "\n"
			+ "ASIGNACIÓN  "
			+ str(actor.get("role_assignment", "")) + "\n\n"
			+ "Los recuerdos, las creencias y los objetivos privados "
			+ "no se revelan por abrir una ficha."
		)
		return
	details.text = (
		"Esta presencia ya no está en tu localización.\n"
		+ "No se revela su paradero actual."
	)
