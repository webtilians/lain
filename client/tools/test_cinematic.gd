extends SceneTree
## Cinematics: the opening plays once for a new player (the computer writes),
## the title once on the first step outside, the Wired connection,
## each Sesión Cero fragment, the ending and each finished research call play on
## live changes only, a technology entering the Malla plays once per PC, another
## account on the same PC gets the start of the story again (not the news), they wait
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
		for text in [cinematic.caption.text, cinematic.title.text, cinematic.lines_label.get_parsed_text(),
				cinematic.screen_text.get_parsed_text()]:
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
	for line in ["CAPA 00 · ARRANQUE", "FIRMA: SESIÓN CERO", "Has vuelto.", "En el colegio, en el aula de informática.",
			"CONEXIÓN PERDIDA"]:
		check(shown(seen, line), "the opening does not show: " + line)
	check(not cinematic.screen.visible, "the computer's screen stays over the game")
	check(player.is_physics_processing(), "the player stays frozen after the opening")
	check(root.get_viewport().get_camera_3d() == own_camera, "the player's camera is not given back")
	check(root.get_node_or_null("CinematicCamera") == null, "the cinematic camera is left behind")
	var saved := ConfigFile.new()
	check(saved.load(path) == OK and "opening" in Array(saved.get_value("cinematics", "seen", [])), "the opening is not remembered")
	cinematic.opening_checked = false
	await frames(3)
	check(not cinematic.is_playing(), "the opening plays twice")

	# The first step outside: the title over the neighbourhood, once.
	api.snapshot.player.location = "APARTMENT_DISTRICT"
	await frames(3)
	check(cinematic.playing == "title", "stepping out for the first time does not show the title")
	seen = {}
	await watch(seen)
	check(shown(seen, "SESIÓN CERO") and shown(seen, "PROTOCOLO DE PRESENCIA")
		and shown(seen, "Una red que nadie recuerda haber construido."), "the title cinematic is incomplete")
	saved = ConfigFile.new()
	check(saved.load(path) == OK and "title" in Array(saved.get_value("cinematics", "seen", [])), "the title is not remembered")
	cinematic.title_queued = false
	await frames(3)
	check(not cinematic.is_playing(), "the title plays twice")
	api.snapshot.player.location = "APARTMENT"

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
	check(shown(seen, "LA MALLA") and shown(seen, "Tú eres la Sesión Uno."), "the Wired cinematic is incomplete")
	check(shown(seen, "SYN-ACK") and shown(seen, "ENLACE ESTABLECIDO"), "the connection has no handshake")

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
	for i in range(200):
		if is_instance_valid(cinematic.stage_view):
			break
		await process_frame
	check(is_instance_valid(cinematic.stage_view), "the fragment has no camera shot of another place")
	check(root.get_viewport().get_camera_3d() == own_camera, "the shot took over the game's own camera")
	seen = {}
	await watch(seen)
	check(not is_instance_valid(cinematic.stage_view), "the shot is left behind after the cinematic")
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
	for line in ["Escribí mi nombre en el registro de NODO_07.", "Sesión Cero completa.", "SESIÓN CERO", "Gracias por recibirla."]:
		check(shown(seen, line), "the ending does not show: " + line)
	check(not cinematic.root.visible, "the cinematic layer stays on screen")
	check(api.snapshot.prologue == before.prologue and api.snapshot.minute == before.minute, "a cinematic changed the snapshot")

	# Research: a finished call plays live; a technology entering the Malla plays once, even on a first snapshot.
	state = state.duplicate(true)
	state["research"] = {"active": true, "unlocked": [], "completed": [{"id": "QB-01",
		"name": "El qubit y la clave que delata al espía", "centre": "Instituto de Física del Puerto"}]}
	api.snapshot_updated.emit(state)
	await frames(2)
	check(cinematic.playing == "research", "finishing a research call has no cinematic")
	seen = {}
	await watch(seen)
	check(shown(seen, "INSTITUTO DE FÍSICA DEL PUERTO · REGISTRO") and shown(seen, "El qubit y la clave que delata al espía")
		and shown(seen, "La Malla aprende."), "the research cinematic is incomplete")
	cinematic.known = {}
	state = state.duplicate(true)
	state.research.unlocked = [{"id": "qkd", "name": "QKD",
		"about": "La Malla reparte claves con fotones: si alguien escucha, se nota.",
		"next": "Desde hoy, cualquiera puede usar qkd en el terminal."}]
	api.snapshot_updated.emit(state)
	await frames(2)
	check(cinematic.playing == "evolve" and cinematic.queue.is_empty(),
		"a technology entering the Malla does not play once (or an old call replays)")
	seen = {}
	await watch(seen)
	check(shown(seen, "LA MALLA EVOLUCIONA") and shown(seen, "QKD") and shown(seen, "cualquiera puede usar qkd"),
		"the Malla's evolution cinematic is incomplete")
	saved = ConfigFile.new()
	check(saved.load(path) == OK and "malla:qkd" in Array(saved.get_value("cinematics", "seen", [])),
		"the technology's cinematic is not remembered")
	api.snapshot_updated.emit(state)
	await frames(3)
	check(not cinematic.is_playing() and cinematic.queue.is_empty(), "a technology's cinematic plays twice")

	# Another account on this PC: the opening and the title again, not the news already shown here.
	var server := root.get_node("ServerConnection")
	server.session_path = "user://test_cinematic_session.json"
	server.set_session("t".repeat(43), "Otra")
	check(not "opening" in cinematic.seen and not "title" in cinematic.seen and "malla:qkd" in cinematic.seen,
		"a new account on this PC skips the start of the story, or sees the Malla news again: " + str(cinematic.seen))
	cinematic._remember("opening")
	server.clear_session()
	check("title" in cinematic.seen and cinematic.seen_for == "cinematics", "the first account's cinematics are lost")
	saved = ConfigFile.new()
	check(saved.load(path) == OK and Array(saved.get_value("cinematics@otra", "seen", [])).has("opening")
		and Array(saved.get_value("cinematics", "seen", [])).has("malla:qkd"), "each account's cinematics are not kept")

	# Watching again from the diary: only what this player has reached.
	var journal := root.get_node("CharacterJournal")
	api.snapshot = state
	journal.open_journal()
	journal._choose_view("CINEMATICS", "")
	await frames(2)
	var labels: Array = journal.cinema_controls.get_children().map(func(button): return button.text)
	check(journal.cinema_controls.visible and labels.size() == 13, "the diary does not list every scene reached: " + str(labels))
	check("TÍTULO // SESIÓN CERO" in labels, "the title cannot be watched again")
	check("INVESTIGACIÓN // El qubit y la clave que delata al espía" in labels and "LA MALLA EVOLUCIONA // QKD" in labels,
		"research scenes missing from the diary")
	check("ARRANQUE // LA TERMINAL" in labels and "FINAL // GRACIAS POR RECIBIRLA" in labels, "start-up or ending missing from the diary")
	var third: Button = journal.cinema_controls.get_children().filter(func(button): return button.text.begins_with("FRAGMENTO 3/7")).front()
	third.pressed.emit()
	await frames(3)
	check(not journal.backdrop.visible and cinematic.playing == "fragment", "replaying from the diary does not play")
	seen = {}
	await watch(seen)
	check(shown(seen, "FRAGMENTO 3/7 · SESIÓN CERO") and shown(seen, "No cerré. Me terminaron."), "the replay shows the wrong fragment")
	cinematic.replay({"id": "intro"})
	await frames(3)
	check(cinematic.playing == "intro" and not player.is_physics_processing(), "the start-up terminal does not replay")
	for code in [KEY_SPACE, KEY_SPACE]:
		var press := InputEventKey.new()
		press.keycode = code
		press.pressed = true
		root.push_input(press)
		await frames(2)
	check(await until_idle(200), "the replayed terminal does not end")
	check(player.is_physics_processing(), "the player stays frozen after the terminal")
	state.prologue.stage = "FIND_TEACHER"
	api.snapshot = {"prologue": {"stage": "FIND_TEACHER"}}
	check(cinematic.available().size() == 3, "the title, once seen, cannot be watched again")
	cinematic.seen = []  # someone new on this PC
	check(cinematic.available().size() == 2, "a new player can watch scenes not reached yet")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://guide_cinematic_test.cfg"))
	scene.queue_free()
	current_scene = null
	await frames(2)
	print("CINEMATIC_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
