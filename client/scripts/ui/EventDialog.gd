extends CanvasLayer
## Every conversation and notice, in the style of a visual novel: the scene stays
## visible behind, the text sits in a box along the bottom with the speaker's name
## on a coloured tab, the answers are rounded buttons above it on the right, and a
## character with a drawn portrait appears on the left. Narration reads dimmer than
## what people say («…»).

signal choice_selected(
	owner_id: String,
	choice_id: String
)
signal dialog_closed(owner_id: String)
signal message_submitted(owner_id: String, message: String)

## Characters with a drawn portrait, by the name the dialogue shows (the server's
## speaker, in either language).
const PORTRAITS := {
	"RYOKO": "res://art/portraits/ryoko.svg",
	"PROFESOR": "res://art/portraits/profesor.svg",
	"TEACHER": "res://art/portraits/profesor.svg",
	"K": "res://art/portraits/k.svg",
}
## Each one's colour, for the name tab and the box's edge.
const ACCENTS := {"RYOKO": Color("e0397a"), "PROFESOR": Color("c98a2e"), "TEACHER": Color("c98a2e"), "K": Color("c4202f")}
const ACCENT := Color("3d7fa6")
const PORTRAIT_SIZE := Vector2(510, 645)
const PORTRAIT_LEFT := 20.0
const BOX_SIDE := 40.0
const BOX_HEIGHT := 196.0
const BOX_BOTTOM := 22.0
const TEXT_LEFT := 28.0
const TEXT_LEFT_PORTRAIT := 430.0  # the text starts past the portrait's face
const CHOICES_WIDTH := 430.0
const TEXT := Color("f4ecf7")
const NARRATION := Color("ab9fc4")
const LETTERS_PER_SECOND := 90.0

var background: ColorRect
var title_label: Label
var name_tab: PanelContainer
var body_label: RichTextLabel
var continue_button: Button
var choices_box: VBoxContainer
var choices_scroll: ScrollContainer
var message_row: HBoxContainer
var message_input: LineEdit
var send_button: Button
var current_owner_id := ""
var panel: PanelContainer
var text_margin: MarginContainer
var portrait: TextureRect
var portrait_key := ""
var box_style: StyleBoxFlat
var tab_style: StyleBoxFlat
var field_focus: StyleBoxFlat
var reveal: Tween

var active_player: Node = null

func _ready() -> void:
	layer = 100
	visible = false

	# The scene stays in sight, darker towards the bottom where the text is.
	background = ColorRect.new()
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.color = Color(0.02, 0.015, 0.05, 0.42)
	background.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(background)
	var shade := TextureRect.new()
	var fade := GradientTexture2D.new()
	fade.gradient = Gradient.new()
	fade.gradient.set_color(0, Color(0.02, 0.015, 0.05, 0.0))
	fade.gradient.set_color(1, Color(0.02, 0.015, 0.05, 0.85))
	fade.fill_from = Vector2(0, 0)
	fade.fill_to = Vector2(0, 1)
	shade.texture = fade
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shade.stretch_mode = TextureRect.STRETCH_SCALE
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	shade.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	shade.offset_top = -320.0
	background.add_child(shade)

	# Under the text box, which covers the bottom of the bust.
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

	# The answers: rounded buttons on the right, just above the box.
	choices_scroll = ScrollContainer.new()
	choices_scroll.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	choices_scroll.offset_right = -BOX_SIDE
	choices_scroll.offset_left = -BOX_SIDE - CHOICES_WIDTH
	choices_scroll.offset_bottom = -BOX_BOTTOM - BOX_HEIGHT - 14.0
	choices_scroll.offset_top = choices_scroll.offset_bottom - 300.0
	choices_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	background.add_child(choices_scroll)
	choices_box = VBoxContainer.new()
	choices_box.add_theme_constant_override("separation", 8)
	choices_box.alignment = BoxContainer.ALIGNMENT_END
	choices_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	choices_box.custom_minimum_size.y = 300.0
	choices_scroll.add_child(choices_box)
	choices_box.visibility_changed.connect(func(): choices_scroll.visible = choices_box.visible)
	choices_box.visible = false

	# The text box along the bottom.
	panel = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	panel.offset_left = BOX_SIDE
	panel.offset_right = -BOX_SIDE
	panel.offset_top = -BOX_BOTTOM - BOX_HEIGHT
	panel.offset_bottom = -BOX_BOTTOM
	box_style = StyleBoxFlat.new()
	box_style.bg_color = Color(0.055, 0.045, 0.1, 0.93)
	box_style.set_border_width_all(2)
	box_style.set_corner_radius_all(16)
	box_style.shadow_color = Color(0, 0, 0, 0.45)
	box_style.shadow_size = 14
	panel.add_theme_stylebox_override("panel", box_style)
	background.add_child(panel)

	text_margin = MarginContainer.new()
	text_margin.add_theme_constant_override("margin_left", int(TEXT_LEFT))
	text_margin.add_theme_constant_override("margin_right", 26)
	text_margin.add_theme_constant_override("margin_top", 26)
	text_margin.add_theme_constant_override("margin_bottom", 14)
	panel.add_child(text_margin)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 8)
	text_margin.add_child(layout)

	body_label = RichTextLabel.new()
	body_label.bbcode_enabled = true
	body_label.scroll_active = true
	body_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body_label.custom_minimum_size = Vector2(0, 96)
	body_label.add_theme_font_size_override("normal_font_size", 19)
	body_label.add_theme_color_override("default_color", TEXT)
	body_label.add_theme_constant_override("line_separation", 4)
	layout.add_child(body_label)
	Gamepad.scroll_with_stick(body_label)

	message_row = HBoxContainer.new()
	message_row.add_theme_constant_override("separation", 8)
	layout.add_child(message_row)
	message_row.visible = false
	message_input = LineEdit.new()
	message_input.placeholder_text = "Escribe lo que quieras decir..."
	message_input.max_length = 500
	message_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	message_input.text_submitted.connect(_on_message_enter)
	message_input.add_theme_font_size_override("font_size", 17)
	for state in ["normal", "focus"]:
		var field := StyleBoxFlat.new()
		field.bg_color = Color(0.03, 0.025, 0.07, 0.95)
		field.border_color = Color("ff7ab8") if state == "focus" else Color("6b5f8c")
		field.set_border_width_all(2 if state == "focus" else 1)
		field.set_corner_radius_all(12)
		field.content_margin_left = 16
		field.content_margin_right = 16
		field.content_margin_top = 8
		field.content_margin_bottom = 8
		message_input.add_theme_stylebox_override(state, field)
		if state == "focus":
			field_focus = field
	message_row.add_child(message_input)
	send_button = _pill("ENVIAR")
	send_button.pressed.connect(_on_message_send)
	message_row.add_child(send_button)

	var bottom := HBoxContainer.new()
	bottom.alignment = BoxContainer.ALIGNMENT_END
	layout.add_child(bottom)
	continue_button = _pill("CONTINUAR  ▸")
	continue_button.pressed.connect(close_event)
	bottom.add_child(continue_button)

	# The speaker's name on a slanted tab over the box's edge.
	name_tab = PanelContainer.new()
	name_tab.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	name_tab.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tab_style = StyleBoxFlat.new()
	tab_style.skew = Vector2(0.25, 0.0)
	tab_style.set_corner_radius_all(3)
	tab_style.content_margin_left = 22
	tab_style.content_margin_right = 22
	tab_style.content_margin_top = 4
	tab_style.content_margin_bottom = 5
	name_tab.add_theme_stylebox_override("panel", tab_style)
	background.add_child(name_tab)
	title_label = Label.new()
	title_label.uppercase = true
	title_label.add_theme_font_size_override("font_size", 19)
	title_label.add_theme_color_override("font_color", Color("fff3f8"))
	name_tab.add_child(title_label)
	_lay_out("")

func _pill(text: String, accent := Color("e0397a")) -> Button:
	## A rounded button: dark and outlined, lit in the speaker's colour under the mouse or the controller.
	var button := Button.new()
	button.text = text
	button.focus_mode = Control.FOCUS_ALL
	button.add_theme_font_size_override("font_size", 16)
	for state in ["normal", "hover", "pressed", "focus", "disabled"]:
		var style := StyleBoxFlat.new()
		style.set_corner_radius_all(22)
		style.set_border_width_all(2 if state in ["hover", "focus"] else 1)
		style.content_margin_left = 20
		style.content_margin_right = 20
		style.content_margin_top = 9
		style.content_margin_bottom = 9
		match state:
			"hover", "focus":
				style.bg_color = Color(accent, 0.92)
				style.border_color = accent.lightened(0.6)
			"pressed":
				style.bg_color = accent.darkened(0.3)
				style.border_color = accent.lightened(0.4)
			_:
				style.bg_color = Color(0.07, 0.055, 0.13, 0.9)
				style.border_color = Color("6b5f8c")
		button.add_theme_stylebox_override(state, style)
	for colour in ["font_color", "font_hover_color", "font_focus_color", "font_pressed_color"]:
		button.add_theme_color_override(colour, Color("f4ecf7"))
	return button

func _lay_out(key: String) -> void:
	## The text and its name tab start past the portrait's face when there is one.
	var left := TEXT_LEFT_PORTRAIT if not key.is_empty() else TEXT_LEFT
	text_margin.add_theme_constant_override("margin_left", int(left))
	var accent: Color = ACCENTS.get(key, ACCENT)
	box_style.border_color = Color(accent, 0.85)
	tab_style.bg_color = accent
	field_focus.border_color = accent.lightened(0.3)
	name_tab.offset_left = BOX_SIDE + left - 8.0
	name_tab.offset_top = -BOX_BOTTOM - BOX_HEIGHT - 18.0
	name_tab.offset_bottom = name_tab.offset_top + 34.0
	name_tab.offset_right = name_tab.offset_left + 10.0  # grows with the name

static func styled(text: String) -> String:
	## Narration dimmer, spoken words bright: «…» in Spanish, “…” in English.
	var safe := text.replace("[", "[lb]")
	if not ("«" in safe or "“" in safe):
		return safe
	var out := ""
	var chunk := ""
	var inside := false
	for letter in safe:
		if not inside and letter in ["«", "“"]:
			out += _narration(chunk)
			chunk = letter
			inside = true
		elif inside and letter in ["»", "”"]:
			out += chunk + letter
			chunk = ""
			inside = false
		else:
			chunk += letter
	return out + (chunk if inside else _narration(chunk))

static func _narration(text: String) -> String:
	return "" if text.is_empty() else "[color=#%s]%s[/color]" % [NARRATION.to_html(false), text]

func show_event(
	event_title: String,
	event_text: String
) -> void:
	title_label.text = event_title
	name_tab.visible = not event_title.strip_edges().is_empty()
	body_label.text = styled(event_text)
	body_label.scroll_to_line(0)
	_show_portrait(portrait_for(event_title))
	_reveal()
	choices_box.visible = false
	message_row.visible = false
	continue_button.visible = true
	visible = true

	active_player = get_tree().get_first_node_in_group("player")
	if active_player != null:
		active_player.set_physics_process(false)
		active_player.set_process_unhandled_input(false)

	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	Gamepad.focus_root(background)
	Gamepad.focus_first(background)

func _reveal() -> void:
	## The text appears as if typed, quickly; a new line replaces it at once.
	if reveal != null and reveal.is_valid():
		reveal.kill()
	body_label.visible_ratio = 0.0
	var letters := body_label.get_total_character_count()
	reveal = create_tween()
	reveal.tween_property(body_label, "visible_ratio", 1.0, clampf(letters / LETTERS_PER_SECOND, 0.15, 1.6))

func close_event() -> void:
	var previous_owner := current_owner_id
	current_owner_id = ""
	visible = false
	_show_portrait("")

	if is_instance_valid(active_player):
		active_player.set_physics_process(true)
		active_player.set_process_unhandled_input(true)

	active_player = null
	if not previous_owner.is_empty():
		dialog_closed.emit(previous_owner)

static func portrait_for(title: String) -> String:
	var key := title.strip_edges().to_upper()
	return key if PORTRAITS.has(key) else ""

func _show_portrait(key: String) -> void:
	_lay_out(key)
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
	show_event(event_title, event_text)
	current_owner_id = owner_id

	continue_button.visible = false
	choices_box.visible = true

	for child in choices_box.get_children():
		choices_box.remove_child(child)
		child.queue_free()

	var accent: Color = ACCENTS.get(portrait_key, Color("e0397a"))
	for choice in choices:
		var button := _pill(str(choice.get("text", "UNKNOWN")), accent)
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		button.custom_minimum_size = Vector2(0, 42)
		button.pressed.connect(_on_choice_pressed.bind(str(choice.get("id", ""))))
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
