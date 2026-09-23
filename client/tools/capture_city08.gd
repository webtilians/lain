extends SceneTree
## Actual gameplay renderer, offline; output directory followed by optional 'before'.
func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		quit(1)
		return
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	root.get_node("WorldApi").snapshot = {
		"minute": 0, "player": {"location": "APARTMENT_DISTRICT", "energy": 1.0},
		"known_nodes": [], "visible_actors": [], "prologue": {"enabled": true, "stage": "FIND_TEACHER"},
	}
	var scene: Node3D = load("res://scenes/apartment_district/ApartmentDistrict.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	var player: CharacterBody3D = scene.get_node("Player")
	player.set_physics_process(false)
	player.set_process_unhandled_input(false)
	for singleton in ["EventDialog", "CharacterJournal", "PrologueTerminal"]:
		root.get_node(singleton).set_process_unhandled_input(false)
		root.get_node(singleton).set_process_unhandled_key_input(false)
	var views := {"residential": Vector3(0, 0.91, -4), "school": Vector3(-9, 0.91, -20), "club": Vector3(8.5, 0.91, -53)}
	if args.size() == 1:
		views = {"residential": Vector3(-3, 0.91, -4), "school": Vector3(-18, 0.91, -17.8), "plaza": Vector3(9, 0.91, -32), "club": Vector3(27.1, 0.91, -65), "station": Vector3(0, 0.91, -102)}
	for view in views:
		player.position = views[view]
		player._update_camera()
		await create_timer(0.5).timeout
		await RenderingServer.frame_post_draw
		var result := root.get_texture().get_image().save_png(args[0].path_join(view + ".png"))
		if result != OK:
			quit(1)
			return
		print("CAPTURE_CITY08 ", view, " draws=", Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	# A wider shot demonstrates the connected blocks, from the same saved scene.
	if args.size() == 1:
		player.position = Vector3(0,0.91,-37)
		player._update_camera()
		player.camera.global_position = Vector3(95,114,47)
		player.camera.look_at(Vector3(0,0,-48),Vector3.UP)
		player.camera.far = 400.0
		player.camera.size = 100.0
		await create_timer(0.3).timeout
		await RenderingServer.frame_post_draw
		if root.get_texture().get_image().save_png(args[0].path_join("district-overview.png")) != OK:
			quit(1)
			return
	quit()
