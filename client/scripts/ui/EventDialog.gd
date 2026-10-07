extends CanvasLayer

signal choice_selected(
	owner_id: String,
	choice_id: String
)
signal dialog_closed(owner_id: String)
signal message_submitted(owner_id: String, message: String)

## Characters with a drawn portrait, by the name the dialogue shows (the server's
## speaker, in either language). It appears beside the text, like a visual novel.
const PORTRAITS := {
	"RYOKO": "res://art/portraits/ryoko.svg",
	"PROFESOR": "res://art/portraits/profesor.svg",
	"TEACHER": "res://art/portraits/profesor.svg",
}
const PORTRAIT_SIZE := Vector2(510, 645)
const PORTRAIT_LEFT := 20.0
const PORTRAIT_SHIFT := 170.0  # the text panel moves right to leave the portrait room

var background: ColorRect
var title_label: Label
var body_label: Label
var continue_button: Button
var choices_box: VBoxContainer
var choices_scroll: ScrollContainer
var message_row: HBoxContainer
var message_input: LineEdit
var send_button: Button
var current_owner_id := ""
var panel: PanelContainer
var portrait: TextureRect
var portrait_key := ""

var active_player: Node = null

func _ready() -> void:
	layer = 100
	visible = false

	background = ColorRect.new()
	background.set_anchors_and_offsets_preset(
		Control.PRESET_FULL_RECT
	)
	background.color = Color(
		0.01, 0.02, 0.04, 0.82
	)
	background.mouse_filter = (
		Control.MOUSE_FILTER_STOP
	)
	add_child(background)

	# Under the panel, which overlaps its shoulder a little.
	portrait = TextureRect.new()
	portrait.name = "Portrait"
	portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	portrait.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	portrait.offset_left = PORTRAIT_LEFT
	portrait.offset_right = PORTRAIT_LEFT + PORTRAIT_SIZE.x
	portrait.offset_top = -PORTRAIT_SIZE.y
	portrait.offset_bottom = 0.0
	portrait.visible = false
	background.add_child(portrait)

	panel = PanelContainer.new()
	background.add_child(panel)
	panel.set_anchors_and_offsets_preset(
		Control.PRESET_CENTER
	)
	# Five investigative dialogue choices need room. The previous 330px
	# panel clipped the final question and made the UI feel noninteractive.
	panel.offset_left = -315.0
	panel.offset_top = -235.0
	panel.offset_right = 315.0
	panel.offset_bottom = 235.0

	var style := StyleBoxFlat.new()
	style.bg_color = Color(
		0.09, 0.12, 0.18, 1.0
	)
	style.border_color = Color(
		0.34, 0.48, 0.62, 1.0
	)
	style.set_border_width_all(2)
	style.set_corner_radius_all(4)
	panel.add_theme_stylebox_override(
		"panel",
		style
	)

	var margin := MarginContainer.new()
	margin.add_theme_constant_override(
		"margin_left",
		16
	)
	margin.add_theme_constant_override(
		"margin_right",
		16
	)
	margin.add_theme_constant_override(
		"margin_top",
		14
	)
	margin.add_theme_constant_override(
		"margin_bottom",
		14
	)
	panel.add_child(margin)

	var layout := VBoxContainer.new()
	layout.add_theme_constant_override(
		"separation",
		12
	)
	margin.add_child(layout)

	title_label = Label.new()
	layout.add_child(title_label)

	body_label = Label.new()
	body_label.autowrap_mode = (
		TextServer.AUTOWRAP_WORD_SMART
	)
	body_label.custom_minimum_size = (
		Vector2(0, 100)
	)
	layout.add_child(body_label)

	choices_box = VBoxContainer.new()
	choices_box.add_theme_constant_override(
		"separation",
		6
	)
	choices_scroll = ScrollContainer.new()
	choices_scroll.custom_minimum_size.y = 145
	choices_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	choices_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	layout.add_child(choices_scroll)
	choices_scroll.add_child(choices_box)
	choices_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	choices_box.visibility_changed.connect(func(): choices_scroll.visible=choices_box.visible)
	choices_box.visible = false

	message_row = HBoxContainer.new()
	message_row.add_theme_constant_override("separation", 6)
	layout.add_child(message_row)
	message_row.visible = false

	message_input = LineEdit.new()
	message_input.placeholder_text = "Escribe lo que quieras decir..."
	message_input.max_length = 500
	message_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	message_input.text_submitted.connect(_on_message_enter)
	message_row.add_child(message_input)

	send_button = Button.new()
	send_button.text = "ENVIAR"
	send_button.pressed.connect(_on_message_send)
	message_row.add_child(send_button)

	continue_button = Button.new()
	continue_button.text = "CONTINUAR"
	continue_button.pressed.connect(
		close_event
	)
	layout.add_child(continue_button)

func show_event(
	event_title: String,
	event_text: String
) -> void:
	title_label.text = event_title
	body_label.text = event_text
	_show_portrait(portrait_for(event_title))
	choices_box.visible = false
	message_row.visible = false
	continue_button.visible = true
	visible = true

	active_player = (
		get_tree().get_first_node_in_group(
			"player"
		)
	)

	if active_player != null:
		active_player.set_physics_process(
			false
		)
		active_player.set_process_unhandled_input(
			false
		)

	Input.mouse_mode = (
		Input.MOUSE_MODE_VISIBLE
	)
	Gamepad.focus_root(continue_button.get_parent())
	Gamepad.focus_first(continue_button.get_parent())

func close_event() -> void:
	var previous_owner := current_owner_id
	current_owner_id = ""
	visible = false
	_show_portrait("")

	if is_instance_valid(active_player):
		active_player.set_physics_process(
			true
		)
		active_player.set_process_unhandled_input(
			true
		)

	active_player = null
	if not previous_owner.is_empty():
		dialog_closed.emit(previous_owner)

static func portrait_for(title: String) -> String:
	var key := title.strip_edges().to_upper()
	return key if PORTRAITS.has(key) else ""

func _show_portrait(key: String) -> void:
	var shift := 0.0 if key.is_empty() else PORTRAIT_SHIFT
	panel.offset_left = -315.0 + shift
	panel.offset_right = 315.0 + shift
	if key == portrait_key:
		return  # the same character keeps talking: no new entrance
	portrait_key = key
	portrait.visible = not key.is_empty()
	if key.is_empty():
		return
	portrait.texture = load(PORTRAITS[key])
	portrait.modulate.a = 0.0
	var entrance := create_tween().set_parallel()
	entrance.tween_property(portrait, "modulate:a", 1.0, 0.25)
	entrance.tween_property(portrait, "position:x", PORTRAIT_LEFT, 0.25).from(PORTRAIT_LEFT - 40.0) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)

func show_choices(
	owner_id: String,
	event_title: String,
	event_text: String,
	choices: Array[Dictionary]
) -> void:
	show_event(
		event_title,
		event_text
	)
	current_owner_id = owner_id

	continue_button.visible = false
	choices_box.visible = true

	for child in choices_box.get_children():
		choices_box.remove_child(child)
		child.queue_free()

	for choice in choices:
		var button := Button.new()
		button.text = str(
			choice.get(
				"text",
				"UNKNOWN"
			)
		)
		button.custom_minimum_size = Vector2(0, 34)

		var choice_id := str(
			choice.get(
				"id",
				""
			)
		)

		button.pressed.connect(
			_on_choice_pressed.bind(choice_id)
		)
		choices_box.add_child(button)
	Gamepad.focus_first(choices_box)

func show_conversation(
	owner_id: String,
	event_title: String,
	event_text: String,
	choices: Array[Dictionary]
) -> void:
	show_choices(owner_id, event_title, event_text, choices)
	message_row.visible = true
	message_input.text = ""
	# With the controller the answers come first; the text field (and its keyboard) is one press below.
	if not Gamepad.using_pad:
		message_input.grab_focus()


func _on_message_enter(_value: String) -> void:
	_on_message_send()


func _on_message_send() -> void:
	if current_owner_id.is_empty() or not message_row.visible:
		return
	var message := message_input.text.strip_edges()
	if message.is_empty():
		message_input.grab_focus()
		return
	# Clear only after we hand the message to the owning NPC.
	message_submitted.emit(current_owner_id, message)


func _on_choice_pressed(
	choice_id: String
) -> void:
	if current_owner_id.is_empty():
		return

	choice_selected.emit(
		current_owner_id,
		choice_id
	)

func _unhandled_input(
	event: InputEvent
) -> void:
	if not visible:
		return

	if event.is_action_pressed(
		"ui_cancel"
	):
		close_event()
		get_viewport().set_input_as_handled()
