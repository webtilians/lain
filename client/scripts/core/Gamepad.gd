extends Node
## Playing with a controller. The left stick or the D-pad walks, A interacts and
## accepts, B closes, Y opens the diary, X the chat, View (Back) the guide, and the
## right stick scrolls long text; text fields get the on-screen keyboard
## (PadKeyboard). This adds the controller to the game's actions, remembers whether
## the last thing touched was the controller or the keyboard and mouse, swaps the
## «[E]» prompts in the world for «[A]», and puts the focus on the first button of
## whatever opens while the controller is in use.
signal changed(using_pad: bool)

const MOVES := {
	"move_left": [JOY_AXIS_LEFT_X, -1.0, JOY_BUTTON_DPAD_LEFT],
	"move_right": [JOY_AXIS_LEFT_X, 1.0, JOY_BUTTON_DPAD_RIGHT],
	"move_forward": [JOY_AXIS_LEFT_Y, -1.0, JOY_BUTTON_DPAD_UP],
	"move_backward": [JOY_AXIS_LEFT_Y, 1.0, JOY_BUTTON_DPAD_DOWN],
}
# action: [keyboard key (or none), controller button]
const BUTTONS := {
	"interact": [KEY_NONE, JOY_BUTTON_A],
	"journal": [KEY_J, JOY_BUTTON_Y],
	"chat": [KEY_ENTER, JOY_BUTTON_X],
	"guide": [KEY_F1, JOY_BUTTON_BACK],
	# Godot's menus already move with the D-pad and the stick, but do not accept or go back with it.
	"ui_accept": [KEY_NONE, JOY_BUTTON_A],
	"ui_cancel": [KEY_NONE, JOY_BUTTON_B],
}
const STICK_DEADZONE := 0.25
const SCROLL_DEADZONE := 0.2
const SCROLL_SPEED := 1400.0  # pixels a second with the stick pushed all the way
const PROMPTS := {false: "[E]", true: "[A]"}

var using_pad := false
# Long text the right stick scrolls; the last visible one registered wins.
var scroll_targets: Array[Control] = []
# Windows whose first button takes the focus when the controller is picked up with nothing focused.
var focus_roots: Array[Control] = []

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_controller_to_actions()
	get_tree().node_added.connect(_on_node_added)

func add_controller_to_actions() -> void:
	for action in MOVES:
		var stick := InputEventJoypadMotion.new()
		stick.axis = MOVES[action][0]
		stick.axis_value = MOVES[action][1]
		var pad := InputEventJoypadButton.new()
		pad.button_index = MOVES[action][2]
		_add(action, stick)
		_add(action, pad)
		InputMap.action_set_deadzone(action, STICK_DEADZONE)
	for action in BUTTONS:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
		if BUTTONS[action][0] != KEY_NONE:
			var key := InputEventKey.new()
			key.keycode = BUTTONS[action][0]
			_add(action, key)
		var button := InputEventJoypadButton.new()
		button.button_index = BUTTONS[action][1]
		_add(action, button)

func _add(action: String, event: InputEvent) -> void:
	for existing in InputMap.action_get_events(action):
		if existing.is_match(event):
			return
	InputMap.action_add_event(action, event)

# ------------------------------------------------------------------ which device

func _input(event: InputEvent) -> void:
	if event is InputEventJoypadButton and event.pressed:
		_set_pad(true)
	elif event is InputEventJoypadMotion and absf(event.axis_value) > 0.5:
		_set_pad(true)
	elif (event is InputEventKey and event.pressed) or (event is InputEventMouseButton and event.pressed):
		_set_pad(false)

func _set_pad(value: bool) -> void:
	if value == using_pad:
		return
	using_pad = value
	_swap_prompts(get_tree().root)
	if using_pad and get_viewport().gui_get_focus_owner() == null:
		# Nothing focused, the D-pad would have nowhere to go: start on the window in front.
		for index in range(focus_roots.size() - 1, -1, -1):
			if is_instance_valid(focus_roots[index]) and focus_roots[index].is_visible_in_tree():
				focus_first(focus_roots[index])
				break
	changed.emit(using_pad)

func label(action: String) -> String:
	## How a prompt names an action on the device in use: «J» or «Y», «E» or «A»…
	var names := {"interact": ["E", "A"], "journal": ["J", "Y"], "chat": ["Enter", "X"], "guide": ["F1", "View"],
		"cancel": ["Esc", "B"]}
	return names.get(action, ["", ""])[1 if using_pad else 0]

# ------------------------------------------------------------------ prompts in the world

func _on_node_added(node: Node) -> void:
	if node is Label3D and using_pad:
		# Signs often get their text right after being added.
		_swap_label.call_deferred(node)

func _swap_prompts(node: Node) -> void:
	if node is Label3D:
		_swap_label(node)
	for child in node.get_children():
		_swap_prompts(child)

func _swap_label(label3d: Label3D) -> void:
	if is_instance_valid(label3d):
		label3d.text = label3d.text.replace(PROMPTS[not using_pad], PROMPTS[using_pad])

# ------------------------------------------------------------------ focus

func focus_root(root: Control) -> void:
	if not focus_roots.has(root):
		focus_roots.append(root)

func focus_first(root: Node) -> void:
	## With the controller, whatever just opened gets the focus on its first button or field.
	if using_pad and root != null:
		_focus_first_now.call_deferred(root)

func _focus_first_now(root: Node) -> void:
	var first := first_focusable(root)
	if first != null:
		first.grab_focus()

func first_focusable(root: Node) -> Control:
	if not is_instance_valid(root):
		return null
	for child in root.get_children():
		var control := child as Control
		if control != null and control.is_visible_in_tree() and control.focus_mode == Control.FOCUS_ALL \
				and (control is BaseButton or control is LineEdit) and not (control is BaseButton and control.disabled):
			return control
		var inner := first_focusable(child)
		if inner != null:
			return inner
	return null

# ------------------------------------------------------------------ right stick scrolls

func scroll_with_stick(target: Control) -> void:
	if not scroll_targets.has(target):
		scroll_targets.append(target)

func _process(delta: float) -> void:
	var pads := Input.get_connected_joypads()
	if pads.is_empty():
		return
	var tilt := Input.get_joy_axis(pads[0], JOY_AXIS_RIGHT_Y)
	if absf(tilt) < SCROLL_DEADZONE:
		return
	for index in range(scroll_targets.size() - 1, -1, -1):
		var target := scroll_targets[index]
		if is_instance_valid(target) and target.is_visible_in_tree():
			scroll(target, tilt * SCROLL_SPEED * delta)
			return

func scroll(target: Control, pixels: float) -> void:
	if target is TextEdit:
		target.scroll_vertical += pixels / maxf(1.0, target.get_line_height())
	elif target is RichTextLabel:
		target.get_v_scroll_bar().value += pixels
	elif target is ScrollContainer:
		target.scroll_vertical += int(pixels)
