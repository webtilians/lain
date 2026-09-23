extends SceneTree
## Offline render/check: never calls the server or opens the user's save.
func _initialize() -> void:
	call_deferred("capture")

func capture() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	api.snapshot = {"player": {"location": "APARTMENT", "energy": 1.0}, "minute": 0, "known_nodes": []}
	var scene = load("res://scenes/apartment/ApartmentIso.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	scene.get_node("Player").set_process_unhandled_input(false)
	root.get_node("EventDialog").set_process_unhandled_input(false)
	await process_frame
	await physics_frame
	await create_timer(0.6).timeout
	assert(scene.get_node("Art").find_children("*", "MeshInstance3D", true, false).size() > 200)
	assert(scene.get_node("ExitDoor").target_location == "APARTMENT_DISTRICT")
	assert(scene.get_node("Monitor").has_method("interact"))
	var options := OS.get_cmdline_user_args()
	if options.is_empty():
		await verify_navigation(scene)
	if not options.is_empty():
		await RenderingServer.frame_post_draw
		var image := root.get_texture().get_image()
		var error := image.save_png(options[0])
		if error != OK:
			push_error("Capture could not be saved")
			quit(1)
			return
		print("CAPTURE_SAVED ", options[0])
	print("APARTMENT_VISUAL_CHECK_OK")
	quit()

func walk_to(player: CharacterBody3D, target: Vector3) -> bool:
	for frame in range(240):
		var offset := target - player.global_position
		offset.y = 0
		if offset.length() < 0.14:
			player.velocity = Vector3.ZERO
			return true
		player.velocity = offset.normalized() * 3.5
		player.velocity.y = -1.0
		player.move_and_slide()
		await physics_frame
	return false

func verify_navigation(scene: Node3D) -> void:
	var player: CharacterBody3D = scene.get_node("Player")
	player.set_physics_process(false)
	for destination in [Vector3(1.5, 0.9, 2.5), Vector3(1.5, 0.9, -1.45), Vector3(-0.8, 0.9, -1.45)]:
		if not await walk_to(player, destination):
			push_error("Blocked terminal route at " + str(player.position))
			quit(1)
			return
	if player.global_position.distance_to(scene.get_node("Monitor").global_position) > player.interaction_distance:
		push_error("Terminal out of reach")
		quit(1)
		return
	scene.get_node("Monitor").interact()
	var terminal := get_first_node_in_group("terminal_ui")
	if not terminal.visible:
		push_error("Terminal did not open")
		quit(1)
		return
	terminal.hide()
	player.set_physics_process(false)
	for destination in [Vector3(1.5, 0.9, -1.45), Vector3(2.65, 0.9, -2.0)]:
		if not await walk_to(player, destination):
			push_error("Blocked exit route")
			quit(1)
			return
	if player.global_position.distance_to(scene.get_node("ExitDoor").global_position) > player.interaction_distance:
		push_error("Exit out of reach")
		quit(1)
		return
	print("NAVIGATION_AND_TERMINAL_OK")
