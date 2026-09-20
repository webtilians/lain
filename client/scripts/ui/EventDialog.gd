extends CanvasLayer

signal choice_selected(
	owner_id: String,
	choice_id: String
)
signal dialog_closed(owner_id: String)

var background: ColorRect
var title_label: Label
var body_label: Label
var continue_button: Button
var choices_box: VBoxContainer
var current_owner_id := ""

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

	var panel := PanelContainer.new()
	background.add_child(panel)
	panel.set_anchors_and_offsets_preset(
		Control.PRESET_CENTER
	)
	panel.offset_left = -240.0
	panel.offset_top = -165.0
	panel.offset_right = 240.0
	panel.offset_bottom = 165.0

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
	layout.add_child(choices_box)
	choices_box.visible = false

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
	choices_box.visible = false
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

func close_event() -> void:
	var previous_owner := current_owner_id
	current_owner_id = ""
	visible = false

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
