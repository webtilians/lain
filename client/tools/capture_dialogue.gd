extends SceneTree
## A frame of a prologue conversation in the computer room (never calls the server):
##   Godot --path client --script res://tools/capture_dialogue.gd --resolution 1280x720 -- C:/out/folder
func _initialize() -> void:
	call_deferred("capture")

func capture() -> void:
	var folder: String = OS.get_cmdline_user_args()[0]
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_capture.cfg"
	guide.hidden_by_player = true
	api.snapshot = {"minute": 600, "player": {"location": "SCHOOL_LAB", "energy": 1.0}, "visible_actors": [],
		"known_nodes": [], "prologue": {"enabled": true, "stage": "FIND_TEACHER", "hint": ""}}
	var scene: Node3D = load("res://scenes/prologue/ComputerLab.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	for i in range(20):
		await process_frame
	var choices: Array[Dictionary] = [
		{"id": "ASK_WHO", "text": "«¿A quién me parezco?»"},
		{"id": "ASK_CLASS", "text": "«¿Qué se hacía en esta aula?»"},
		{"id": "ASK_STUDENT", "text": "«Alguien me ha escrito. Dice que usted le enseñó a hablar con Indara.»"},
		{"id": "GOODBYE", "text": "Dejarle con su registro."},
	]
	root.get_node("EventDialog").show_choices("PROLOGUE_PROFESSOR", "Profesor",
		"El profesor no levanta la vista del registro de préstamos. «El aula cierra a las nueve. Si buscas un libro, la biblioteca está…» Entonces te mira, y el bolígrafo se le queda quieto. «Perdona. Te pareces mucho a alguien.»",
		choices)
	for i in range(20):
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(folder.path_join("dialogue-professor.png"))
	print("CAPTURE_SAVED dialogue-professor")
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://guide_capture.cfg"))
	quit()
