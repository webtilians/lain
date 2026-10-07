extends SceneTree
## Interactive objects stand out: a soft light over everything usable nearby, and
## over the one E would use now a ring and the button to press. The marked object is
## the one the player's interaction picks; with the controller it says [A]; nothing
## shows while the player is held by a window.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func frames(count: int = 3) -> void:
	for i in range(count):
		await process_frame

func shown_hints(highlight: Node) -> int:
	return highlight.hints.filter(func(hint): return hint.visible).size()

func run() -> void:
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_highlight_test.cfg"
	guide.hidden_by_player = true
	var scene: Node3D = load("res://scenes/apartment/ApartmentIso.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	var player: CharacterBody3D = scene.get_node("Player")
	var monitor: Node3D = scene.get_node("Monitor")
	var door: Node3D = scene.get_node("ExitDoor")
	var highlight: Node3D = player.get_node("InteractHighlight")
	await frames()

	# Next to the computer: it is the one marked, and the one E would use.
	player.global_position = monitor.global_position + Vector3(0.6, -0.4, 0.9)
	await frames()
	check(player.nearest_interactable() == monitor, "the player is not in reach of the computer")
	check(highlight.focused == monitor and highlight.ring.visible and highlight.marker.visible,
		"the computer in reach is not marked")
	check(highlight.prompt.text == "[E]", "the mark does not say which key: " + highlight.prompt.text)
	check(highlight.marker.global_position.y > monitor.global_position.y, "the arrow is not over the computer")
	check(absf(highlight.ring.global_position.x - monitor.global_position.x) < 0.01, "the ring is not under the computer")
	check(shown_hints(highlight) == 1, "the door nearby has no soft light")

	# Next to the door, the mark moves to it.
	player.global_position = door.global_position + Vector3(-0.5, -0.2, 1.0)
	await frames()
	check(highlight.focused == door and player.nearest_interactable() == door, "the mark does not follow to the door")

	# Out of reach of both: no ring, but both still glow softly.
	player.global_position = Vector3(0.3, player.global_position.y, 0.3)
	await frames()
	check(player.nearest_interactable() == null and not highlight.ring.visible and not highlight.marker.visible,
		"something is marked out of reach")
	check(shown_hints(highlight) == 2, "the usable things nearby do not glow: %d" % shown_hints(highlight))

	# With the controller, the button is A.
	player.global_position = monitor.global_position + Vector3(0.6, -0.4, 0.9)
	var pad := InputEventJoypadButton.new()
	pad.button_index = JOY_BUTTON_DPAD_LEFT
	pad.pressed = true
	Input.parse_input_event(pad)
	await frames()
	check(highlight.prompt.text == "[A]", "with the controller the mark still says [E]")
	pad.pressed = false
	Input.parse_input_event(pad)

	# Something with a visible shape glows along its own silhouette, and gets its looks back after.
	var figure := Node3D.new()
	var usable := GDScript.new()
	usable.source_code = "extends Node3D\nfunc interact() -> void:\n\tpass\n"
	usable.reload()
	figure.set_script(usable)
	figure.add_to_group("interactable")
	var body := MeshInstance3D.new()
	body.mesh = CapsuleMesh.new()
	figure.add_child(body)
	scene.add_child(figure)
	figure.global_position = Vector3(0.3, monitor.global_position.y - 0.4, 0.3)
	player.global_position = figure.global_position + Vector3(0.5, 0, 0.5)
	await frames()
	check(highlight.focused == figure and body.material_overlay == highlight.rim, "a figure in reach does not glow")
	check(not highlight.ring.visible and highlight.marker.visible, "a figure gets the floor glow instead of its silhouette")
	player.global_position = Vector3(0.3, player.global_position.y, 3.5)
	await frames()
	check(body.material_overlay == null, "the figure keeps the glow out of reach")
	figure.queue_free()
	await frames()

	# Held by a window (the player stops), nothing shows.
	player.global_position = monitor.global_position + Vector3(0.6, -0.4, 0.9)
	player.set_physics_process(false)
	await frames()
	check(not highlight.ring.visible and not highlight.marker.visible and shown_hints(highlight) == 0,
		"the marks stay over an open window")
	player.set_physics_process(true)
	await frames()
	check(highlight.ring.visible, "the marks do not come back when the window closes")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(guide.config_path))
	scene.queue_free()
	current_scene = null
	await frames()
	print("HIGHLIGHT_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
