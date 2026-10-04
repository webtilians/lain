extends SceneTree
## Cinematics: the opening plays once for a new player, the Wired connection,
## each Sesión Cero fragment and the ending play on live changes only, they wait
## for open terminals, freeze and give back the player and camera, Esc skips,
## and the snapshot never changes.
var failures: Array[String] = []
var cinematic: Node

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func frames(count: int) -> void:
	for i in range(count):
		await process_frame

func until_idle(limit: int = 900) -> bool:
	for i in range(limit):
		if not cinematic.is_playing() and cinematic.queue.is_empty():
			return true
		await process_frame
	return false

func watch(seen: Dictionary, limit: int = 40000) -> void:
	# Remember every caption, title and line shown while the cinematic plays.
	for i in range(limit):
		for text in [cinematic.caption.text, cinematic.title.text, cinematic.lines_label.get_parsed_text()]:
			if not str(text).is_empty():
				seen[str(text)] = true
		if not cinematic.is_playing() and cinematic.queue.is_empty():
			return
		await process_frame

func shown(seen: Dictionary, text: String) -> bool:
	for key in seen:
		if text in key:
			return true
	return false

func layers(decided: Dictionary, count: int) -> Dictionary:
	var result := {}
	for key in decided:
		result[key] = {"active": true, "decision": decided[key], "fragments": count}
	return result

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	cinematic = root.get_node("Cinematic")
	var guide := root.get_node("Guide")
	var shell := root.get_node("ShellTerminal")
	var path := "user://cinematics_test.cfg"
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://guide_cinematic_test.cfg"))
	guide.config_path = "user://guide_cinematic_test.cfg"
	cinematic.config_path = path
	cinematic.seen = []
	cinematic.enabled = true
	cinematic.pace = 40.0
	api.snapshot = {"minute": 3, "player": {"location": "APARTMENT", "energy": 1.0}, "visible_actors": [], "known_nodes": [],
		"prologue": {"enabled": true, "stage": "FIND_TEACHER", "hint": "En el barrio está la antigua escuela."}}
	var before: Dictionary = api.snapshot.duplicate(true)
	var scene: Node3D = load("res://scenes/apartment/ApartmentIso.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	var player: Node3D = scene.get_node("Player")
	var own_camera: Camera3D = player.get_node("Head/Camera3D")
	await frames(3)

	# The opening, for a new player at home.
	check(cinematic.playing == "opening", "the opening does not play for a new player")
	check(not player.is_physics_processing(), "the player can walk during a cinematic")
	check(not guide.panel.visible, "the guide shows over a cinematic")
	var seen := {}
	await watch(seen)
	for line in ["Antes de tu primera conexión", "La Sesión Cero.", "Uno de ellos te ha encontrado.", "Has vuelto."]:
		check(shown(seen, line), "the opening does not show: " + line)
	check(player.is_physics_processing(), "the player stays frozen after the opening")
	check(root.get_viewport().get_camera_3d() == own_camera, "the player's camera is not given back")
	check(root.get_node_or_null("CinematicCamera") == null, "the cinematic camera is left behind")
	var saved := ConfigFile.new()
	check(saved.load(path) == OK and "opening" in Array(saved.get_value("cinematics", "seen", [])), "the opening is not remembered")
	cinematic.opening_checked = false
	await frames(3)
	check(not cinematic.is_playing(), "the opening plays twice")

	# The first snapshot after starting never plays anything.
	cinematic.known = {}
	var state: Dictionary = api.snapshot.duplicate(true)
	state.prologue.stage = "FIND_TERMINAL"
	state.merge(layers({"layer_one": "SPLICE"}, 1), true)
	api.snapshot_updated.emit(state)
	await frames(2)
	check(not cinematic.is_playing() and cinematic.queue.is_empty(), "an old fragment replays on start")

	# Connecting to the Wired.
	state = state.duplicate(true)
	state.prologue.stage = "CONNECTED"
	api.snapshot_updated.emit(state)
	await frames(2)
	check(cinematic.playing == "wired", "connecting to the Wired has no cinematic")
	seen = {}
	await watch(seen)
	check(shown(seen, "THE WIRED") and shown(seen, "Tú eres la Sesión Uno."), "the Wired cinematic is incomplete")

	# A fragment waits until the terminal closes.
	shell.surface.show()
	state = state.duplicate(true)
	state.merge(layers({"layer_one": "SPLICE", "layer_two": "SHUTDOWN"}, 2), true)
	api.snapshot_updated.emit(state)
	await frames(5)
	check(not cinematic.is_playing() and cinematic.queue.size() == 1, "a cinematic starts over an open terminal")
	shell.surface.hide()
	await frames(2)
	check(cinematic.playing == "fragment", "the fragment does not play once the terminal closes")
	seen = {}
	await watch(seen)
	check(shown(seen, "FRAGMENTO 2/7 · SESIÓN CERO") and shown(seen, "Hay otra máquina con nuestra dirección"),
		"the fragment shows the wrong layer")

	# Esc skips.
	state = state.duplicate(true)
	state.merge(layers({"layer_one": "SPLICE", "layer_two": "SHUTDOWN", "layer_three": "FORWARD"}, 3), true)
	api.snapshot_updated.emit(state)
	cinematic.pace = 1.0
	await frames(3)
	check(cinematic.playing == "fragment", "the third fragment does not play")
	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	root.push_input(escape)
	check(await until_idle(30), "Esc does not skip the cinematic")
	check(player.is_physics_processing(), "skipping leaves the player frozen")
	cinematic.pace = 40.0

	# The end, with every fragment back.
	state = state.duplicate(true)
	var all := {"layer_one": "A", "layer_two": "B", "layer_three": "C", "layer_four": "D", "layer_five": "E", "layer_six": "F",
		"layer_seven": "PERSIST"}
	state.merge(layers(all, 7), true)
	api.snapshot_updated.emit(state)
	await frames(2)
	seen = {}
	await watch(seen)
	for line in ["Escribí mi nombre en el registro de NODO_07.", "Sesión Cero completa.", "L A I N", "Gracias por recibirla."]:
		check(shown(seen, line), "the ending does not show: " + line)
	check(not cinematic.root.visible, "the cinematic layer stays on screen")
	check(api.snapshot.prologue == before.prologue and api.snapshot.minute == before.minute, "a cinematic changed the snapshot")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://guide_cinematic_test.cfg"))
	scene.queue_free()
	current_scene = null
	await frames(2)
	print("CINEMATIC_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
