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
var chapter_controls: VBoxContainer
var first_clue: OptionButton
var second_clue: OptionButton
var link_kind: OptionButton
var hypothesis: LineEdit
var chapter_feedback: Label

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
	scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED
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
	var reading := VBoxContainer.new()
	reading.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	reading.size_flags_vertical=Control.SIZE_EXPAND_FILL
	body.add_child(reading)
	reading.add_child(details)
	_build_chapter_controls(reading)
	backdrop.visible = false
	WorldApi.snapshot_updated.connect(_on_snapshot_updated)
	call_deferred("_connect_chapter")

func _connect_chapter() -> void:
	ChapterOne.archive_saved.connect(_chapter_saved)


func _unhandled_input(event: InputEvent) -> void:
	var key_event := event as InputEventKey
	if key_event == null or not key_event.pressed or key_event.echo:
		return
	if key_event.keycode != JOURNAL_KEY:
		return
	# Text typed into the DOS command line is not a gameplay hotkey.
	# Opening the journal over a terminal would also reactivate the player
	# when it closes, while the command line still holds focus.
	if PrologueTerminal.surface != null and PrologueTerminal.surface.visible:
		return
	var legacy_terminal = get_tree().get_first_node_in_group("terminal_ui")
	if legacy_terminal != null and legacy_terminal.visible:
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
	button.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	button.tooltip_text=label_text
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.pressed.connect(_choose_view.bind(view, actor_id))
	navigation.add_child(button)


func _refresh_navigation() -> void:
	for child in navigation.get_children():
		navigation.remove_child(child)
		child.queue_free()
	_add_navigation("TU FICHA", "PLAYER")
	var prologue: Dictionary = WorldApi.snapshot.get("prologue", {})
	var offline: bool = (
		bool(prologue.get("enabled", false))
		and str(prologue.get("stage", "")) != "CONNECTED"
	)
	if bool(prologue.get("enabled", false)):
		_add_navigation("PRÓLOGO // ANTES DE LA WIRED", "PROLOGUE")
	if not offline:
		_add_navigation("CASO // EL PULSO AUSENTE", "CASE")
	if bool(WorldApi.snapshot.get("chapter_one",{}).get("active",false)):
		_add_navigation("ARCHIVO // YA HABÍAS ESTADO AQUÍ", "CHAPTER")
	if bool(WorldApi.snapshot.get("network_conflict",{}).get("active",false)):
		_add_navigation("RED // CONTROL DE ENLACES", "NETWORK")
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
	chapter_controls.visible=current_view=="CHAPTER"
	match current_view:
		"NETWORK":
			_render_network()
		"CHAPTER":
			_render_chapter()
		"PROLOGUE":
			_render_prologue()
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
		+ (
			"CONEXIÓN A LA WIRED  PENDIENTE"
			if str(data.get("case_status", "")) == "LOCKED"
			else "INVESTIGACIÓN NODE_07  " + str(data.get("case_status", "UNSEEN"))
		)
		+ "\n\nLas fichas solo incluyen conocimientos accesibles al jugador."
	)

func _render_network() -> void:
	var data: Dictionary=WorldApi.snapshot.get("network_conflict",{})
	var locations: Dictionary={"STATION":"Estación","SCHOOL_LAB":"Aula de informática","VIDEO_CLUB":"Video Hoshi"}
	var sources: Dictionary={"RELAY_TELEMETRY":"Lectura del enlace"}
	var text: String="RED // CONTROL DE ENLACES\n\n"+str(data.get("corporation",""))+" controla el "+str(data.get("corporate_control",0))+"%\n"
	text+="Tu exposición: "+str(int(data.get("trace",0)))+"/100\n"
	text+="Examinar un armario permite conocer a su administrador. Disputar su control puede desencadenar una intervención.\n"
	for item in data.get("relays",[]):
		sources[str(item.id)]=str(item.name)
		text+="\n"+str(item.name)+" · "+str(locations.get(str(item.location),item.location))+"\n"
		text+="Administrador: "+str(int(item.corporation))+"% · Tú: "+str(int(item.mine))+"% · Defensas: "+str(int(item.defense))+"/2\n"
	text+="\nINTERVENCIONES CONTRA TU CONEXIÓN\n"
	if data.get("pending",[]).is_empty(): text+="Ninguna detectada.\n"
	for op in data.get("pending",[]):
		var title: String=str(op.relay)
		for item in data.get("relays",[]):
			if item.id==op.relay: title=str(item.name)
		text+=title+": restan "+str(int(op.remaining))+" minutos del mundo.\n"
	text+="\nCONTROL POR CUENTA\n"
	for rank in data.get("rankings",[]):
		text+=str(rank.name)+" · "+str(rank.control)+"%\n"
	text+="\nINFORMES RECIBIDOS · DEL MÁS RECIENTE AL MÁS ANTIGUO\n"
	for report in data.get("reports",[]):
		text+="\nMinuto "+str(int(report.minute))+" · "+str(sources.get(str(report.source),report.source))+"\n"+str(report.text)+"\n"
	if details.text!=text:
		var scroll:=details.get_v_scroll_bar().value
		details.text=text
		details.get_v_scroll_bar().set_deferred("value",scroll)


func _render_prologue() -> void:
	var story: Dictionary = WorldApi.snapshot.get("prologue", {})
	details.text = (
		"PRÓLOGO // ANTES DE LA WIRED\n\n"
		+ "ESTADO  " + str(story.get("stage", "LEGACY"))
		+ "\n\nOBJETIVO\n" + str(story.get("hint", ""))
		+ "\n\nLos personajes solo pueden contarte lo que saben. "
		+ "La conexión a la Wired deberá descubrirse, no se activará "
		+ "por el mero hecho de pulsar un botón."
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
		if actor.has("public_objective"):
			details.text += "\n\nOBJETIVO PERSONAL\n" + str(actor.public_objective)
			details.text += "\n\nAHORA\n" + str(actor.get("activity", ""))
			details.text += "\n\nHABILIDADES (1–5)"
			var skills: Dictionary = actor.get("skills", {})
			for skill in skills:
				details.text += "\n" + str(skill) + "  " + str(skills[skill]) + "/5"
		return
	details.text = (
		"Esta presencia ya no está en tu localización.\n"
		+ "No se revela su paradero actual."
	)

func _build_chapter_controls(parent: VBoxContainer) -> void:
	chapter_controls=VBoxContainer.new()
	parent.add_child(chapter_controls)
	var label := Label.new()
	label.text="RELACIONAR DOS PISTAS · TU INTERPRETACIÓN"
	chapter_controls.add_child(label)
	var row := HBoxContainer.new()
	chapter_controls.add_child(row)
	first_clue=OptionButton.new()
	second_clue=OptionButton.new()
	for picker in [first_clue,second_clue]:
		picker.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		picker.fit_to_longest_item=false
		row.add_child(picker)
	var actions := HBoxContainer.new()
	chapter_controls.add_child(actions)
	link_kind=OptionButton.new()
	for relation in ["Se contradicen","Una apoya a la otra","Las relaciono"]:
		link_kind.add_item(relation)
	actions.add_child(link_kind)
	var link_button := Button.new()
	link_button.text="GUARDAR RELACIÓN"
	link_button.pressed.connect(_link_clues)
	actions.add_child(link_button)
	var note_row := HBoxContainer.new()
	chapter_controls.add_child(note_row)
	hypothesis=LineEdit.new()
	hypothesis.placeholder_text="Mi hipótesis, todavía sin verificar..."
	hypothesis.max_length=500
	hypothesis.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	note_row.add_child(hypothesis)
	var save := Button.new()
	save.text="ANOTAR"
	save.pressed.connect(func(): ChapterOne.save_hypothesis(hypothesis.text))
	note_row.add_child(save)
	chapter_feedback=Label.new()
	chapter_feedback.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	chapter_feedback.add_theme_font_size_override("font_size",13)
	chapter_controls.add_child(chapter_feedback)
	chapter_controls.hide()

func _link_clues() -> void:
	if first_clue.selected<0 or second_clue.selected<0:
		return
	ChapterOne.save_link(str(first_clue.get_item_metadata(first_clue.selected)),
		str(second_clue.get_item_metadata(second_clue.selected)),
		["CONTRADICTS","SUPPORTS","RELATED"][link_kind.selected])

func _chapter_saved(message: String) -> void:
	chapter_feedback.text=message

func _render_chapter() -> void:
	var chapter: Dictionary = WorldApi.snapshot.get("chapter_one",{})
	var types := {"MESSAGE":"MENSAJE RECIBIDO","TESTIMONY":"TESTIMONIO",
		"OBSERVATION":"OBSERVACIÓN PROPIA","DOCUMENT":"DOCUMENTO","RECORD":"REGISTRO · AUTENTICIDAD PENDIENTE"}
	var text := "ARCHIVO // YA HABÍAS ESTADO AQUÍ\n\n"
	text+="Lo que has presenciado, lo que te han contado y lo que conservan los archivos son fuentes distintas.\n"
	var clues: Array = chapter.get("evidence",[])
	var titles := {}
	for clue in clues:
		titles[str(clue.id)]=str(clue.title)
		text+="\n────────────────────────\n"+str(clue.title)+"\n"
		text+=str(types.get(str(clue.kind),clue.kind))+" · "+str(clue.source_label)+"\n"
		text+="Incorporado al archivo: minuto "+str(int(clue.acquired_minute))+"\n"
		text+="Fecha que la fuente atribuye: "+str(clue.claimed_time)+"\n\n"+str(clue.text)+"\n"
	text+="\nRELACIONES QUE HAS ANOTADO\n"
	for link in chapter.get("links",[]):
		var meaning: String = {"CONTRADICTS":" ↔ contradicción ↔ ","SUPPORTS":" ↔ apoyo ↔ ","RELATED":" ↔ relación ↔ "}.get(str(link.relation)," ↔ ")
		text+=str(titles.get(str(link.first),""))+meaning+str(titles.get(str(link.second),""))+"\n"
	text+="\nMI HIPÓTESIS · SIN VERIFICAR\n"+str(chapter.get("hypothesis",""))+"\n"
	if chapter.get("decision")!=null:
		text+="\nMI DECISIÓN\n"+("Entregué la copia al profesor y autoricé que avisara a Ryoko." if chapter.decision=="DISCLOSE" else "Sellé la copia con Ryoko. El profesor solo recibió la anomalía de la fecha.")
	if details.text!=text:
		var scroll_position := details.get_v_scroll_bar().value
		details.text=text
		details.get_v_scroll_bar().set_deferred("value",scroll_position)
	for picker in [first_clue,second_clue]:
		var previous := str(picker.get_item_metadata(picker.selected)) if picker.selected>=0 else ""
		picker.clear()
		for clue in clues:
			picker.add_item(str(clue.title))
			picker.set_item_metadata(picker.item_count-1,str(clue.id))
			if str(clue.id)==previous:
				picker.select(picker.item_count-1)
		if previous.is_empty() and picker==second_clue and clues.size()>1:
			picker.select(1)
	if not hypothesis.has_focus():
		hypothesis.text=str(chapter.get("hypothesis",""))
