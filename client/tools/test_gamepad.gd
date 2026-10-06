extends SceneTree
## Playing with a controller: the stick walks, prompts say [A], Y opens the diary
## with the focus on it and B closes it, dialogs focus their first answer, the guide
## names the controller's buttons, the right stick scrolls, and text fields get the
## on-screen keyboard (type, shift, delete, shortcuts, history, send). In the
## terminal, B closes the keyboard first and the terminal after.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func frames(count: int = 2) -> void:
	for i in range(count):
		await process_frame

func pad(index: int, pressed := true) -> void:
	var event := InputEventJoypadButton.new()
	event.button_index = index
	event.pressed = pressed
	Input.parse_input_event(event)

func stick(axis: int, value: float) -> void:
	var event := InputEventJoypadMotion.new()
	event.axis = axis
	event.axis_value = value
	Input.parse_input_event(event)

func press(index: int) -> void:
	pad(index, true)
	await frames(1)
	pad(index, false)
	await frames(1)

func key_button(keyboard: Node, text: String) -> Button:
	for button in keyboard.panel.find_children("*", "Button", true, false):
		if button.text == text:
			return button
	check(false, "the on-screen keyboard has no key " + text)
	return Button.new()

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var gamepad := root.get_node("Gamepad")
	var keyboard := root.get_node("PadKeyboard")
	var journal := root.get_node("CharacterJournal")
	var dialog := root.get_node("EventDialog")
	var shell := root.get_node("ShellTerminal")
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_gamepad_test.cfg"
	DirAccess.remove_absolute(ProjectSettings.globalize_path(guide.config_path))
	api.snapshot = {"minute": 17, "player": {"location": "APARTMENT", "energy": .8, "name": "Mio"}, "visible_actors": [],
		"known_nodes": [], "prologue": {"enabled": true, "stage": "FIND_TEACHER", "hint": "En el barrio está la antigua escuela."}}
	var scene: Node3D = load("res://scenes/apartment/ApartmentIso.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	await frames()

	# The controller is in the game's actions, and touching it switches the prompts.
	var events: Array = InputMap.action_get_events("interact")
	check(events.any(func(e): return e is InputEventJoypadButton and e.button_index == JOY_BUTTON_A), "A does not interact")
	check(InputMap.has_action("journal") and InputMap.has_action("chat") and InputMap.has_action("guide"),
		"the diary, chat and guide actions are missing")
	var sign := Label3D.new()
	sign.text = "COLEGIO\n[E] ENTRAR"
	scene.add_child(sign)
	check(not gamepad.using_pad, "the game starts as if a controller were in use")
	stick(JOY_AXIS_LEFT_X, 0.9)
	await frames()
	check(gamepad.using_pad, "moving the stick does not switch to the controller")
	check(Input.get_vector("move_left", "move_right", "move_forward", "move_backward").x > 0.5, "the stick does not walk")
	check(sign.text == "COLEGIO\n[A] ENTRAR", "the prompt does not name the A button: " + sign.text)
	var late := Label3D.new()
	late.text = "Kissa  [E]"
	scene.add_child(late)
	await frames()
	check(late.text == "Kissa  [A]", "a sign that appears later keeps [E]")
	stick(JOY_AXIS_LEFT_X, 0.0)
	pad(JOY_BUTTON_DPAD_UP)
	await frames(1)
	check(Input.get_vector("move_left", "move_right", "move_forward", "move_backward").y < -0.5, "the D-pad does not walk")
	pad(JOY_BUTTON_DPAD_UP, false)
	await frames()

	# The guide names the controller's buttons.
	guide._show(guide.STEPS[1])
	check("Pulsa Y" in guide.text_label.text and guide.footer.text.begins_with("View"), "the guide still names the keyboard")

	# Y opens the diary with the focus on it, B closes it.
	await press(JOY_BUTTON_Y)
	check(journal.backdrop.visible, "Y does not open the diary")
	await frames()
	var focus := root.gui_get_focus_owner()
	check(focus is Button and journal.navigation.is_ancestor_of(focus), "the diary opens without the focus on it")
	await press(JOY_BUTTON_B)
	check(not journal.backdrop.visible, "B does not close the diary")

	# A dialog focuses its first answer.
	var answers: Array[Dictionary] = [{"id": "ONE", "text": "Primera"}, {"id": "TWO", "text": "Segunda"}]
	dialog.show_conversation("gamepad-test", "Profesor", "«Hola.»", answers)
	await frames()
	focus = root.gui_get_focus_owner()
	check(focus is Button and focus.text == "Primera", "the dialog does not focus its first answer")
	check(not keyboard.is_open(), "the keyboard opens over a dialog's answers")
	var chosen: Array = []
	dialog.choice_selected.connect(func(_owner: String, choice: String): chosen.append(choice), CONNECT_ONE_SHOT)
	await press(JOY_BUTTON_DPAD_DOWN)
	await press(JOY_BUTTON_A)
	check(chosen == ["TWO"], "the D-pad and A do not pick an answer: " + str(chosen))
	await press(JOY_BUTTON_B)
	check(not dialog.visible, "B does not close the dialog")

	# A text field gets the on-screen keyboard.
	var field := LineEdit.new()
	field.set_meta("pad_words", ["help", "ls"])
	var history: Array = []
	field.set_meta("pad_history", func(step: int): history.append(step))
	var sent: Array = []
	field.text_submitted.connect(func(text: String): sent.append(text))
	var holder := CanvasLayer.new()
	holder.add_child(field)
	root.add_child(holder)
	field.grab_focus()
	await frames()
	check(keyboard.is_open() and keyboard.target == field, "a text field does not open the keyboard")
	check(root.gui_get_focus_owner() is Button and keyboard.panel.is_ancestor_of(root.gui_get_focus_owner()),
		"the keyboard's keys do not get the focus")
	key_button(keyboard, "help").pressed.emit()
	await press(JOY_BUTTON_Y)
	key_button(keyboard, "Mayús").pressed.emit()
	key_button(keyboard, "Q").pressed.emit()
	key_button(keyboard, "a").pressed.emit()
	check(field.text == "help Qa", "typing with the keys fails: " + field.text)
	await press(JOY_BUTTON_X)
	await press(JOY_BUTTON_LEFT_SHOULDER)
	key_button(keyboard, "1").pressed.emit()
	check(field.text == "help 1Q", "delete or moving the cursor fails: " + field.text)
	key_button(keyboard, "Anterior").pressed.emit()
	check(history == [-1], "the history shortcut does not reach the field")
	await press(JOY_BUTTON_START)
	check(sent == ["help 1Q"], "Start does not send the text")
	await press(JOY_BUTTON_B)
	check(not keyboard.is_open() and root.gui_get_focus_owner() == field, "B does not close the keyboard back to the field")
	await press(JOY_BUTTON_A)
	check(keyboard.is_open(), "A on the field does not bring the keyboard back")
	await press(JOY_BUTTON_B)
	holder.queue_free()
	await frames()

	# In the terminal, B closes the keyboard first and then the terminal.
	shell.surface.show()
	shell.input.grab_focus()
	await frames()
	check(keyboard.is_open() and keyboard.target == shell.input, "the terminal's line does not get the keyboard")
	check(key_button(keyboard, "pista") != null and key_button(keyboard, "Siguiente") != null,
		"the terminal's shortcuts are missing")
	await press(JOY_BUTTON_B)
	check(not keyboard.is_open() and shell.is_open(), "B closed the terminal along with the keyboard")
	await press(JOY_BUTTON_B)
	check(not shell.is_open(), "the second B does not close the terminal")

	# The right stick scrolls long text.
	var text := TextEdit.new()
	text.size = Vector2(300, 100)
	text.text = "\n".join(range(200).map(func(n): return "línea %d" % n))
	root.add_child(text)
	await frames()
	gamepad.scroll(text, 600.0)
	check(text.scroll_vertical > 5, "the right stick does not scroll text")
	text.queue_free()

	# Back on the keyboard: prompts name keys again.
	var back := InputEventKey.new()
	back.keycode = KEY_SHIFT
	back.pressed = true
	Input.parse_input_event(back)
	await frames()
	check(not gamepad.using_pad and sign.text == "COLEGIO\n[E] ENTRAR", "the keyboard does not bring [E] back")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(guide.config_path))
	scene.queue_free()
	current_scene = null
	await frames()
	print("GAMEPAD_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
