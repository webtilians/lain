extends CanvasLayer
## The on-screen keyboard for the controller. When a text field gets the focus
## while the controller is in use, it opens at the bottom of the screen: D-pad or
## stick to pick a key and A to type it; X deletes, Y types a space, LB and RB move
## the cursor, Start sends (like Enter) and B closes it. A field can offer
## shortcuts, the terminal's usual commands, with set_meta("pad_words", [...]),
## and a history with set_meta("pad_history", Callable(step: int)).
## It is the last autoload, so it sees the controller's buttons before the
## windows under it (B closes the keyboard, not the terminal).
const ROWS := [
	"1234567890",
	"qwertyuiop",
	"asdfghjklñ",
	"zxcvbnm,.-",
	"/_~:+*<>|=",
	"áéíóú¿?¡!@",
]
const KEY_SIZE := Vector2(54, 40)

var target: LineEdit
var closed_for: LineEdit  # closed with B: it reopens only when A is pressed on that field again
var panel: PanelContainer
var preview: Label
var words: HBoxContainer
var grid: GridContainer
var shift := false
var letter_keys: Array[Button] = []
var last_key: Button
# Windows that move their content up while the keyboard is open: [MarginContainer, normal bottom margin].
var rooms: Array = []

func _ready() -> void:
	layer = 125
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build()
	hide_keyboard()
	get_viewport().gui_focus_changed.connect(_on_focus_changed)
	Gamepad.changed.connect(_on_device_changed)

func _build() -> void:
	panel = PanelContainer.new()
	panel.name = "PadKeyboard"
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	panel.offset_bottom = -12
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.03, 0.05, 0.07, 0.96)
	style.border_color = Color("5f8f73")
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	style.set_content_margin_all(12)
	panel.add_theme_stylebox_override("panel", style)
	add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	panel.add_child(column)
	preview = Label.new()
	preview.add_theme_color_override("font_color", Color("e0b45a"))
	preview.add_theme_font_size_override("font_size", 18)
	preview.clip_text = true
	preview.custom_minimum_size = Vector2(KEY_SIZE.x * 10, 0)
	column.add_child(preview)
	words = HBoxContainer.new()
	words.add_theme_constant_override("separation", 4)
	column.add_child(words)
	grid = GridContainer.new()
	grid.columns = 10
	grid.add_theme_constant_override("h_separation", 4)
	grid.add_theme_constant_override("v_separation", 4)
	column.add_child(grid)
	for row in ROWS:
		for character in row:
			var key := _key(character, _type.bind(character), grid)
			if character.to_upper() != character:
				letter_keys.append(key)
	var bottom := HBoxContainer.new()
	bottom.add_theme_constant_override("separation", 4)
	column.add_child(bottom)
	_key("Mayús", _toggle_shift, bottom)
	var space := _key("Espacio (Y)", _type.bind(" "), bottom)
	space.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_key("Borrar (X)", _backspace, bottom)
	_key("<- (LB)", _move_caret.bind(-1), bottom)
	_key("-> (RB)", _move_caret.bind(1), bottom)
	_key("Enviar (Start)", _submit, bottom)
	_key("Cerrar (B)", close_keyboard, bottom)

func _key(text: String, action: Callable, parent: Control) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = KEY_SIZE if text.length() == 1 else Vector2(0, KEY_SIZE.y)
	button.focus_mode = Control.FOCUS_ALL
	button.add_theme_font_size_override("font_size", 18)
	button.pressed.connect(action)
	parent.add_child(button)
	return button

func is_open() -> bool:
	return panel.visible

func make_room(margin: MarginContainer, bottom: int) -> void:
	## A terminal whose last lines would sit under the keyboard lifts them above it while it is open.
	rooms.append([margin, bottom])

func _apply_room() -> void:
	var height := int(panel.get_combined_minimum_size().y) + 24 if panel.visible else 0
	for room in rooms:
		if is_instance_valid(room[0]):
			room[0].add_theme_constant_override("margin_bottom", room[1] + height)

# ------------------------------------------------------------------ opening and closing

func _on_focus_changed(control: Control) -> void:
	if control is Button and panel.is_ancestor_of(control):
		last_key = control
		return
	if not control is LineEdit or not Gamepad.using_pad:
		return
	if is_open() and control == target:
		# The terminal takes its line back after every answer: the keys keep the focus.
		_focus_key()
	elif control.editable and control != closed_for:
		open_keyboard(control)

func _on_device_changed(using_pad: bool) -> void:
	var focus := get_viewport().gui_get_focus_owner()
	if using_pad and focus is LineEdit and focus.editable:
		open_keyboard(focus)
	elif not using_pad and is_open():
		# Back on the keyboard: type there, with the field focused as before.
		var field := target
		hide_keyboard()
		if is_instance_valid(field):
			field.grab_focus()

func open_keyboard(field: LineEdit) -> void:
	target = field
	closed_for = null
	for child in words.get_children():
		words.remove_child(child)
		child.queue_free()
	for word in field.get_meta("pad_words", []):
		_key(str(word), _type.bind(str(word)), words)
	if field.has_meta("pad_history"):
		_key("Anterior", func(): field.get_meta("pad_history").call(-1), words)
		_key("Siguiente", func(): field.get_meta("pad_history").call(1), words)
	words.visible = words.get_child_count() > 0
	panel.show()
	_apply_room()
	_refresh()
	last_key = grid.get_child(10)  # the q
	_focus_key()

func _focus_key() -> void:
	(last_key if is_instance_valid(last_key) and last_key.is_visible_in_tree() else grid.get_child(10)).grab_focus.call_deferred()

func close_keyboard() -> void:
	var field := target
	hide_keyboard()
	if is_instance_valid(field) and field.is_visible_in_tree():
		closed_for = field
		field.grab_focus()

func hide_keyboard() -> void:
	panel.hide()
	target = null
	_apply_room()

func _process(_delta: float) -> void:
	if not is_open():
		return
	if not is_instance_valid(target) or not target.is_visible_in_tree():
		hide_keyboard()  # the terminal closed, the message was sent, the menu changed…
	else:
		_refresh()

func _input(event: InputEvent) -> void:
	var button := event as InputEventJoypadButton
	if button == null or not button.pressed:
		return
	if not is_open():
		# A on a field closed with B opens the keyboard again.
		var focus := get_viewport().gui_get_focus_owner()
		if button.button_index == JOY_BUTTON_A and focus is LineEdit and focus == closed_for:
			open_keyboard(focus)
			get_viewport().set_input_as_handled()
		return
	var actions := {
		JOY_BUTTON_B: close_keyboard,
		JOY_BUTTON_X: _backspace,
		JOY_BUTTON_Y: _type.bind(" "),
		JOY_BUTTON_LEFT_SHOULDER: _move_caret.bind(-1),
		JOY_BUTTON_RIGHT_SHOULDER: _move_caret.bind(1),
		JOY_BUTTON_START: _submit,
	}
	if actions.has(button.button_index):
		actions[button.button_index].call()
		get_viewport().set_input_as_handled()

# ------------------------------------------------------------------ typing

func _type(text: String) -> void:
	if not is_instance_valid(target) or not target.editable:
		return
	var value := text.to_upper() if shift and text.length() == 1 else text
	target.insert_text_at_caret(value)
	if shift and text.length() == 1:
		_toggle_shift()

func _backspace() -> void:
	if not is_instance_valid(target) or target.caret_column == 0:
		return
	var caret := target.caret_column
	target.text = target.text.substr(0, caret - 1) + target.text.substr(caret)
	target.caret_column = caret - 1
	target.text_changed.emit(target.text)

func _move_caret(step: int) -> void:
	if is_instance_valid(target):
		target.caret_column = clampi(target.caret_column + step, 0, target.text.length())

func _submit() -> void:
	if is_instance_valid(target) and target.editable:
		target.text_submitted.emit(target.text)

func _toggle_shift() -> void:
	shift = not shift
	for key in letter_keys:
		key.text = key.text.to_upper() if shift else key.text.to_lower()

func _refresh() -> void:
	if not is_instance_valid(target):
		return
	var shown := "•".repeat(target.text.length()) if target.secret else target.text
	var caret := clampi(target.caret_column, 0, shown.length())
	var hint := target.placeholder_text if target.text.is_empty() else ""
	preview.text = (shown.substr(0, caret) + "|" + shown.substr(caret)) if hint.is_empty() else "| " + hint
