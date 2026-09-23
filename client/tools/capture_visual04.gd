extends SceneTree
## Offline navigation check; pass district/station then optional PNG path to render.
var failed := false

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> void:
	if not condition:
		failed = true
		push_error(message)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var district := args.is_empty() or args[0] == "district"
	var location := "APARTMENT_DISTRICT" if district else "STATION"
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	api.snapshot = {"player": {"location": location, "energy": 1.0}, "minute": 0, "known_nodes": [], "visible_actors": [{"id":"AGENT_K","name":"K"},{"id":"AGENT_NORA","name":"Nora"}]}
	var path := "res://scenes/apartment_district/ApartmentDistrict.tscn" if district else "res://scenes/station/Station.tscn"
	var scene: Node3D = load(path).instantiate()
	root.add_child(scene)
	current_scene = scene
	var player: CharacterBody3D = scene.get_node("Player")
	player.set_process_unhandled_input(false)
	player.set_physics_process(false)
	root.get_node("EventDialog").set_process_unhandled_input(false)
	await process_frame
	if district:
		check(scene.get_node_or_null("CityArt/School") != null, "Missing saved city scenery")
	else:
		check(scene.get_node("Dressing").find_children("*", "MeshInstance3D", true, false).size() > 150, "Missing saved scenery")
	check(player.get_node("Silhouette/LeftLeg") != null, "Missing animated avatar")
	check(scene.get_node("Actors").rendered_actors.size() == 2, "Actor representation missing")
	var actors: Node3D = scene.get_node("Actors")
	check(actors.rendered_actors["AGENT_K"].get("actor_id") == "AGENT_K", "K identity changed")
	check(actors.rendered_actors["AGENT_NORA"].get("actor_id") == "AGENT_NORA", "Nora identity changed")
	# The same production spawner must render an arbitrary persistent ID,
	# preserve its chat target, and remove it when World Core hides it.
	api.snapshot["visible_actors"].append({"id":"ENTITY_TEST_01","name":"Eco"})
	api.snapshot_updated.emit(api.snapshot)
	await process_frame
	check(actors.rendered_actors.size() == 3, "Generated actor not rendered")
	check(actors.rendered_actors.has("ENTITY_TEST_01"), "Generated actor identity missing")
	if actors.rendered_actors.has("ENTITY_TEST_01"):
		var entity: Node3D = actors.rendered_actors["ENTITY_TEST_01"]
		check(entity.get("actor_id") == "ENTITY_TEST_01", "Generated actor chat target changed")
		check(entity.get_node_or_null("DigitalBody") != null, "Digital presence has no visual")
	api.snapshot["visible_actors"] = [{"id":"AGENT_K","name":"K"}]
	api.snapshot_updated.emit(api.snapshot)
	await process_frame
	check(actors.rendered_actors.size() == 1, "Hidden actor remained visible")
	api.snapshot["visible_actors"].append({"id":"AGENT_NORA","name":"Nora"})
	api.snapshot_updated.emit(api.snapshot)
	await process_frame
	check(actors.rendered_actors.size() == 2, "Actor failed to return")
	if args.size() > 1:
		player.position = Vector3(0, 0.9, -9 if district else -2)
		player._update_camera()
		await create_timer(0.4).timeout
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(args[1]) == OK, "Cannot save preview")
	else:
		if district:
			check(await walk_to(player, Vector3(0,0.9,5.7)), "Apartment frontage obstructed")
			check(await walk_to(player, Vector3(0,0.9,-104.5)), "Station approach obstructed")
			check(player.position.distance_to(scene.get_node("PrologueEntrances/Entrance_STATION").position) < player.interaction_distance, "Station door unreachable")
			check(scene.get_node("PrologueEntrances/Entrance_STATION").target_location == "STATION", "Station destination changed")
			check(await walk_to(player, Vector3(0,0.9,5.7)), "Apartment lane obstructed")
			check(await walk_to(player, Vector3(-12,0.9,5.7)), "Apartment approach obstructed")
			check(player.position.distance_to(scene.get_node("PrologueEntrances/Entrance_APARTMENT").position) < player.interaction_distance, "Apartment door unreachable")
		else:
			check(await walk_to(player, Vector3(0,0.9,-4.8)), "Signal approach obstructed")
			check(player.position.distance_to(scene.get_node("SignalSource").position) < player.interaction_distance, "Signal unreachable")
			check(scene.get_node("SignalSource").node_id == "NODE_07", "Signal identity changed")
			check(await walk_to(player, Vector3(0,0.9,9.1)), "Exit approach obstructed")
			check(player.position.distance_to(scene.get_node("ExitDoor").position) < player.interaction_distance, "Exit unreachable")
	print("VISUAL04_CHECK_", "FAILED" if failed else "OK", " ", location)
	quit(1 if failed else 0)

func walk_to(player: CharacterBody3D, target: Vector3) -> bool:
	for frame in range(2400):
		var offset := target - player.position
		offset.y = 0
		if offset.length() < 0.14:
			player.velocity = Vector3.ZERO
			return true
		player.velocity = offset.normalized() * 3.5
		player.velocity.y = -1
		player.move_and_slide()
		await physics_frame
	return false
