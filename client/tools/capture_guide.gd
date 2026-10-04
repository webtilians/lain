extends SceneTree
## Offline render of the first-minutes guide (never calls the server):
##   Godot --path client --script res://tools/capture_guide.gd --resolution 1280x720 -- C:/out/folder
## Writes guide-apartment.png (step 1) and guide-district.png (step 4).
func _initialize() -> void:
	call_deferred("capture")

func shot(path: String) -> void:
	await create_timer(0.8).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(path)
	print("CAPTURE_SAVED ", path)

func capture() -> void:
	var folder: String = OS.get_cmdline_user_args()[0]
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_capture.cfg"
	guide.done = []
	guide.decided = true
	guide.hidden_by_player = false
	api.snapshot = {"minute": 0, "player": {"location": "APARTMENT", "energy": 1.0}, "visible_actors": [], "known_nodes": [],
		"prologue": {"enabled": true, "stage": "FIND_TEACHER", "hint": "En el barrio está la antigua escuela."}}
	for step in [["APARTMENT", "res://scenes/apartment/ApartmentIso.tscn", [], "guide-apartment.png"],
			["APARTMENT_DISTRICT", "res://scenes/apartment_district/ApartmentDistrict.tscn", ["move", "journal", "leave"], "guide-district.png"]]:
		api.snapshot.player.location = step[0]
		guide.done = step[2]
		guide.start_position = null
		var scene: Node3D = load(step[1]).instantiate()
		root.add_child(scene)
		current_scene = scene
		scene.get_node("Player").set_physics_process(false)
		scene.get_node("Player").set_process_unhandled_input(false)
		await shot(folder.path_join(step[3]))
		scene.queue_free()
		await process_frame
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://guide_capture.cfg"))
	quit()
