extends SceneTree
## Offline Reality 0.3 test. No server, no world.db and no player mutation.
## godot --headless --path client --script res://tools/test_reality03_visual.gd

var failed := false

func _initialize() -> void:
	call_deferred("_run")


func check(condition: bool, reason: String) -> void:
	if not condition:
		failed = true
		push_error("REALITY03_VISUAL // " + reason)


func _run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	var cases := {
		"APARTMENT": "res://scenes/apartment/ApartmentIso.tscn",
		"APARTMENT_DISTRICT": "res://scenes/apartment_district/ApartmentDistrict.tscn",
		"STATION": "res://scenes/station/Station.tscn",
	}

	for location in cases.keys():
		api.snapshot = {
			"player": {"id": "PLAYER_1", "location": location, "energy": 1.0},
			"minute": 0,
			"known_nodes": [],
			"visible_actors": [
				{"id": "ENTITY_R03_TEST", "name": "Eco", "patrol_step": 0},
			],
		}
		var scene: Node3D = load(cases[location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		var player = scene.get_node_or_null("Player")
		if player != null:
			player.set_physics_process(false)
			player.set_process_unhandled_input(false)
		await process_frame

		var spawner: Node3D = scene.get_node("Actors")
		var actors: Dictionary = spawner.rendered_actors
		check(actors.has("ENTITY_R03_TEST"), location + ": spawn missing")
		if actors.has("ENTITY_R03_TEST"):
			var entity: Node3D = actors["ENTITY_R03_TEST"]
			var initial_position := entity.global_position
			check(entity.get("actor_id") == "ENTITY_R03_TEST",
				location + ": identity lost")
			api.snapshot["visible_actors"][0]["patrol_step"] = 1
			api.snapshot["minute"] = 10
			api.snapshot_updated.emit(api.snapshot)
			await create_timer(2.1).timeout
			check(entity.global_position.distance_to(initial_position) > 0.4,
				location + ": accepted local waypoint did not animate")
			check(entity.get("actor_id") == "ENTITY_R03_TEST",
				location + ": movement changed interaction target")
			check(int(spawner.patrol_steps.get("ENTITY_R03_TEST", -1)) == 1,
				location + ": waypoint not received")

		api.snapshot["visible_actors"] = []
		api.snapshot_updated.emit(api.snapshot)
		await process_frame
		check(not spawner.rendered_actors.has("ENTITY_R03_TEST"),
			location + ": off-scene actor not removed")
		current_scene = null
		scene.queue_free()
		await process_frame

	print("REALITY03_VISUAL_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
