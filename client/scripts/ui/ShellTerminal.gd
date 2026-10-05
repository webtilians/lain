extends CanvasLayer
## Capa 03 shell. The server owns every command, file and puzzle; this only
## shows text, keeps the current folder and a local command history.
const ERRORS := {
	"TERMINAL_NOT_PRESENT": "Tienes que estar delante del PC de casa.",
	"CONSOLE_NOT_PRESENT": "Tienes que estar junto a ese armario de enlace.",
	"LAYER_NOT_ACTIVE": "La consola no responde todavía.",
	"INVALID_COMMAND": "Esa orden no se puede enviar.",
}
var surface: ColorRect
var output: TextEdit
var prompt: Label
var input: LineEdit
var request: HTTPRequest
var host := "navi"
var cwd := "/"
var hostname := "navi"
var busy := false
var history: Array[String] = []
var history_index := 0
var held_player: Node

func _ready() -> void:
	layer = 106
	request = HTTPRequest.new()
	request.max_redirects = 0
	request.timeout = 20
	add_child(request)
	request.request_completed.connect(_completed)
	var mono := SystemFont.new()
	mono.font_names = PackedStringArray(["Cascadia Mono", "Consolas", "Lucida Console", "Courier New", "DejaVu Sans Mono", "monospace"])
	surface = ColorRect.new()
	surface.color = Color("05090b")
	surface.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(surface)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 24)
	surface.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	margin.add_child(column)
	var bar := HBoxContainer.new()
	column.add_child(bar)
	var title := Label.new()
	title.text = "LA MALLA · TERMINAL   ·   Esc para salir   ·   help · man <tema>"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.add_theme_color_override("font_color", Color("5f8f73"))
	bar.add_child(title)
	output = TextEdit.new()
	output.editable = false
	output.context_menu_enabled = true
	output.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	output.size_flags_vertical = Control.SIZE_EXPAND_FILL
	output.add_theme_font_override("font", mono)
	output.add_theme_font_size_override("font_size", 16)
	output.add_theme_color_override("font_readonly_color", Color("a8e6bd"))
	output.add_theme_color_override("background_color", Color("05090b"))
	var flat := StyleBoxFlat.new()
	flat.bg_color = Color("05090b")
	output.add_theme_stylebox_override("read_only", flat)
	output.add_theme_stylebox_override("normal", flat)
	column.add_child(output)
	var line := HBoxContainer.new()
	column.add_child(line)
	prompt = Label.new()
	prompt.add_theme_font_override("font", mono)
	prompt.add_theme_font_size_override("font_size", 16)
	prompt.add_theme_color_override("font_color", Color("e0b45a"))
	line.add_child(prompt)
	input = LineEdit.new()
	input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	input.max_length = 400
	input.add_theme_font_override("font", mono)
	input.add_theme_font_size_override("font_size", 16)
	input.text_submitted.connect(_submit)
	input.text_changed.connect(func(_text: String) -> void: pass)
	line.add_child(input)
	surface.hide()

func is_open() -> bool:
	return surface != null and surface.visible

func open_shell(target: String) -> void:
	if EventDialog.visible:
		EventDialog.close_event()
	if host != target:
		output.text = ""
		cwd = "/"
	host = target
	surface.show()
	# The PC already holds the player when the shell opens from it.
	if not Workshop.is_open():
		held_player = get_tree().get_first_node_in_group("player")
		if is_instance_valid(held_player):
			held_player.set_physics_process(false)
			held_player.set_process_unhandled_input(false)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_update_prompt()
	input.grab_focus()
	if output.text.is_empty():
		_send("cat /etc/motd", false)

func close_shell() -> void:
	surface.hide()
	if is_instance_valid(held_player):
		held_player.set_physics_process(true)
		held_player.set_process_unhandled_input(true)
	held_player = null

func _input(event: InputEvent) -> void:
	if not is_open():
		return
	if event.is_action_pressed("ui_cancel"):
		close_shell()
		get_viewport().set_input_as_handled()
	elif event is InputEventKey and event.pressed and input.has_focus() and not history.is_empty():
		if event.keycode == KEY_UP:
			history_index = maxi(0, history_index - 1)
		elif event.keycode == KEY_DOWN:
			history_index = mini(history.size(), history_index + 1)
		else:
			return
		input.text = history[history_index] if history_index < history.size() else ""
		input.caret_column = input.text.length()
		get_viewport().set_input_as_handled()

func _submit(text: String) -> void:
	var command := text.strip_edges()
	input.clear()
	if command.is_empty() or busy:
		return
	if history.is_empty() or history[-1] != command:
		history.append(command)
	history_index = history.size()
	pass
	_send(command, true)

func _send(command: String, echo: bool) -> void:
	if echo:
		_print(prompt.text + " " + command)
	busy = true
	input.editable = false
	var body := JSON.stringify({"host": host, "cwd": cwd, "command": command})
	var error := request.request(ServerConnection.base_url() + "/api/v1/layer-three/shell",
		ServerConnection.headers(), HTTPClient.METHOD_POST, body)
	if error != OK:
		_done("No se pudo conectar con el servidor.")

func _completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var payload = JSON.parse_string(body.get_string_from_utf8())
	if result != HTTPRequest.RESULT_SUCCESS or typeof(payload) != TYPE_DICTIONARY:
		_done("La respuesta se perdió. Vuelve a intentarlo.")
		return
	if code < 200 or code >= 300:
		_done(ERRORS.get(str(payload.get("detail", "")), "La consola rechazó la orden."))
		return
	var reply: Dictionary = payload.get("result", {})
	cwd = str(reply.get("cwd", cwd))
	hostname = str(reply.get("hostname", hostname))
	if typeof(payload.get("state")) == TYPE_DICTIONARY:
		WorldApi.snapshot = payload.state
		WorldApi.snapshot_updated.emit(payload.state)
	if bool(reply.get("clear", false)):
		output.text = ""
	_done(str(reply.get("output", "")))
	if bool(reply.get("exit", false)):
		close_shell()

func _done(text: String) -> void:
	busy = false
	input.editable = true
	if not text.is_empty():
		_print(text)
		pass
	_update_prompt()
	if is_open():
		input.grab_focus()

func _print(text: String) -> void:
	output.text += ("" if output.text.is_empty() else "\n") + text
	output.scroll_vertical = output.get_line_count()
	output.set_caret_line(output.get_line_count() - 1)

func _update_prompt() -> void:
	var player_name := str(WorldApi.snapshot.get("player", {}).get("name", "tú")).to_lower()
	prompt.text = player_name + "@" + hostname + ":" + cwd + "$"
