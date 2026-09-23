extends CanvasLayer
## A FICTIONAL DOS-like shell. Text is parsed by World Core; NEVER run it
## on the user's computer, via OS.execute, or by connecting to a real host.

var surface: ColorRect
var transcript: RichTextLabel
var command_line: LineEdit
var enter_wired: Button
var active_player: Node = null
var connected := false


func _ready() -> void:
	layer = 92
	surface = ColorRect.new()
	surface.color = Color(0.02, 0.02, 0.06, 0.985)
	surface.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	surface.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(surface)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 35)
	surface.add_child(margin)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 12)
	margin.add_child(layout)
	var header := Label.new()
	header.text = "LAIN-DOS  VERSION 1.0      (C) 1998     [ESC] SALIR"
	header.add_theme_color_override("font_color", Color(0.75, 0.78, 0.90))
	layout.add_child(header)
	var divider := HSeparator.new()
	layout.add_child(divider)
	transcript = RichTextLabel.new()
	transcript.bbcode_enabled = false
	transcript.scroll_following = true
	transcript.size_flags_vertical = Control.SIZE_EXPAND_FILL
	transcript.add_theme_font_size_override("normal_font_size", 20)
	transcript.add_theme_color_override("default_color", Color(0.68, 0.80, 0.72))
	layout.add_child(transcript)
	var row := HBoxContainer.new()
	layout.add_child(row)
	var prompt := Label.new()
	prompt.text = "C:\\>"
	row.add_child(prompt)
	command_line = LineEdit.new()
	command_line.placeholder_text = ""
	command_line.max_length = 80
	command_line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	command_line.text_submitted.connect(_on_command)
	row.add_child(command_line)
	enter_wired = Button.new()
	enter_wired.text = "ENTRAR EN LA WIRED"
	enter_wired.visible = false
	enter_wired.pressed.connect(_enter_wired)
	layout.add_child(enter_wired)
	surface.visible = false
	PrologueApi.terminal_received.connect(_on_server_result)
	PrologueApi.request_error.connect(_on_request_error)


func open_terminal() -> void:
	connected = false
	surface.visible = true
	var stage := str(WorldApi.snapshot.get("prologue", {}).get("stage", "LEGACY"))
	var text := (
		"LAIN-DOS [Version 1.0]\n"
		+ "C:\\> _\n\n"
		+ "Unidad C: / Directorio personal\n"
		+ "La consola esta lista.\n"
	)
	if stage == "FIND_TERMINAL":
		text += (
			"\nEl cursor parpadea. Las palabras de Ryoko "
			+ "siguen dando vueltas en tu cabeza.\n"
		)
	elif stage == "CONNECTED":
		text += (
			"\nLa orden fue aceptada, pero el enlace se interrumpio "
			+ "antes de abrir la Wired. Repite el comando para recuperar "
			+ "la conexion guardada.\n"
		)
	else:
		text += "\nSIN ACCESO REMOTO. Busca primero a alguien que te ensene.\n"
	transcript.text = text
	command_line.visible = true
	command_line.editable = true
	command_line.text = ""
	enter_wired.visible = false
	active_player = get_tree().get_first_node_in_group("player")
	if is_instance_valid(active_player):
		active_player.set_physics_process(false)
		active_player.set_process_unhandled_input(false)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	command_line.grab_focus()


func close_terminal() -> void:
	surface.visible = false
	if is_instance_valid(active_player):
		active_player.set_physics_process(true)
		active_player.set_process_unhandled_input(true)
	active_player = null


func _unhandled_input(event: InputEvent) -> void:
	if surface.visible and event.is_action_pressed("ui_cancel"):
		close_terminal()
		get_viewport().set_input_as_handled()


func _on_command(line: String) -> void:
	if not surface.visible or connected or not command_line.editable:
		return
	var command := line.strip_edges()
	command_line.text = ""
	if command.is_empty():
		return
	transcript.text += "\nC:\\> " + command + "\n"
	match command.to_lower():
		"cls":
			transcript.text = "LAIN-DOS\n"
		"ver":
			transcript.text += "LAIN-DOS 1.0 // TERMINAL LOCAL\n"
		"dir":
			transcript.text += "C:\\USUARIO\\  <DIR>    BOOT.LOG\n"
		"help":
			transcript.text += "CLS: limpiar   DIR: directorio   VER: version\n"
		_:
			command_line.editable = false
			PrologueApi.terminal_command(command)


func _on_server_result(result: Dictionary) -> void:
	if not surface.visible:
		return
	command_line.editable = true
	if bool(result.get("accepted", false)):
		connected = true
		transcript.text += (
			"Abriendo enlace remoto...\n"
			+ "WIRED:23 // ENLACE ESTABLECIDO\n\n"
			+ "NO ESTOY MUERTA. SOLO DEJE DE ESTAR AHI.\n"
			+ "El silencio del mundo ha cambiado.\n"
		)
		command_line.visible = false
		enter_wired.visible = true
	else:
		var reason := str(result.get("reason", "UNKNOWN"))
		if reason == "MISSING_CONNECTION_KNOWLEDGE":
			transcript.text += (
				"ACCESO DENEGADO. El sistema no dispone "
				+ "de los datos necesarios para abrir este enlace.\n"
			)
		else:
			transcript.text += (
				"Orden no reconocida o destino no disponible.\n"
			)
		command_line.grab_focus()


func _on_request_error(message: String) -> void:
	if not surface.visible:
		return
	command_line.editable = true
	transcript.text += "ERROR // " + message + "\n"
	command_line.grab_focus()


func _enter_wired() -> void:
	if not connected:
		return
	close_terminal()
	# Resume the existing REALITY 0.4 in-game mail / Wired interface.
	var old_terminal = get_tree().get_first_node_in_group("terminal_ui")
	if old_terminal != null:
		old_terminal.open_terminal()
