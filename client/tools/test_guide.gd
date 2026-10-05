extends SceneTree
## The first-minutes guide: it advances as the player walks, opens the diary,
## goes out, finds the school and talks; then keeps the prologue objective on
## screen; F1 hides it; terminals get one tip; veterans skip the steps; and it
## never changes the world.
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

func reset(guide: Node, path: String) -> void:
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	guide.config_path = path
	guide.done = []
	guide.tips = []
	guide.decided = false
	guide.hidden_by_player = false
	guide.start_position = null
	guide.finished_left = 0.0

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node("Guide")
	var journal := root.get_node("CharacterJournal")
	var dialog := root.get_node("EventDialog")
	var shell := root.get_node("ShellTerminal")
	var path := "user://guide_test.cfg"
	reset(guide, path)
	var hint := "En el barrio está la antigua escuela."
	api.snapshot = {"minute": 17, "player": {"location": "APARTMENT", "energy": .8}, "visible_actors": [],
		"known_nodes": [], "prologue": {"enabled": true, "stage": "FIND_TEACHER", "hint": hint}}
	var snapshot_before: Dictionary = api.snapshot.duplicate(true)
	var scene: Node3D = load("res://scenes/apartment/ApartmentIso.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	var player: Node3D = scene.get_node("Player")
	player.set_physics_process(false)
	await frames()
	check(guide.panel.visible, "the guide does not appear for a new player")
	check(guide.title_label.text == "1/5 · CAMINAR", "the first step is not walking: " + guide.title_label.text)
	check(guide.WELCOME in guide.text_label.text, "the first step does not welcome the player")

	player.global_position += Vector3(3, 0, 0)
	await frames()
	check("move" in guide.done and guide.title_label.text == "2/5 · TU DIARIO", "walking does not advance the guide")

	journal.open_journal()
	await frames()
	check("journal" in guide.done, "opening the diary does not advance the guide")
	check(not guide.panel.visible, "the guide covers the open diary")
	journal.close_journal()

	api.snapshot.player.location = "APARTMENT_DISTRICT"
	await frames()
	check("leave" in guide.done and guide.title_label.text == "4/5 · EL COLEGIO", "going out does not advance the guide")
	api.snapshot.player.location = "SCHOOL_LAB"
	await frames()
	check(guide.title_label.text == "5/5 · HABLAR", "reaching the school does not advance the guide")

	# A plain notice (only «Continuar») is not talking to someone.
	dialog.show_event("AVISO", "Un aviso cualquiera.")
	await frames()
	check(not "talk" in guide.done, "a plain notice counts as talking")
	dialog.close_event()
	await frames()
	var greeting: Array[Dictionary] = [{"id": "INTRO", "text": "Hola"}]
	dialog.show_choices("guide-test", "Profesor", "«¿Has venido a por algún libro?»", greeting)
	await frames()
	check("talk" in guide.done, "talking does not finish the guide")
	dialog.close_event()
	await frames()
	check(guide.title_label.text == "GUÍA COMPLETADA" and guide.panel.visible, "the end of the guide is not shown")
	guide.finished_left = 0.0
	await frames()
	check(guide.title_label.text == "OBJETIVO" and guide.text_label.text == hint, "the prologue objective is not kept on screen")

	guide.toggle()
	await frames()
	check(not guide.panel.visible, "F1 does not hide the guide")
	guide.toggle()
	await frames()
	check(guide.panel.visible, "F1 does not bring the guide back")

	shell.surface.show()
	await frames()
	check(guide.SHELL_TIP in shell.output.text and not guide.panel.visible, "the terminal does not explain help and hints")
	shell.surface.hide()
	await frames()
	shell.surface.show()
	await frames()
	check(shell.output.text.count(guide.SHELL_TIP) == 1, "the terminal tip repeats")
	shell.surface.hide()
	shell.output.text = ""

	var saved := ConfigFile.new()
	check(saved.load(path) == OK and Array(saved.get_value("guide", "done", [])).size() == 5, "the guide does not remember its progress")
	check(api.snapshot.prologue == snapshot_before.prologue and api.snapshot.minute == snapshot_before.minute,
		"the guide changed the snapshot")

	# Someone who already played: no steps, only the objective.
	reset(guide, path)
	api.snapshot.prologue.stage = "FIND_RYOKO"
	api.snapshot.player.location = "APARTMENT_DISTRICT"
	await frames()
	check(guide.done.size() == 5 and guide.title_label.text == "OBJETIVO", "a returning player is taught again")
	api.snapshot.prologue.stage = "CONNECTED"
	await frames()
	check(not guide.panel.visible, "the guide stays after the prologue")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	scene.queue_free()
	current_scene = null
	await frames()
	print("GUIDE_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
