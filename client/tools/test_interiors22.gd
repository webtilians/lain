extends SceneTree
## Visual 0.22: every interior gets its own fixtures, materials and clutter,
## and none of it touches collisions, actors or the world state.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func physical_state(node: Node, state: Array) -> void:
	if node is CollisionShape3D:
		state.append([str(node.get_path()), node.transform, node.disabled])
	if node is CollisionObject3D:
		state.append([str(node.get_path()), node.transform, node.collision_layer, node.collision_mask])
	for child in node.get_children():
		physical_state(child, state)

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var director := root.get_node("GraphicsDirector")
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for location in paths:
		if location == "APARTMENT_DISTRICT":
			continue
		api.snapshot = {"minute": 17, "player": {"location": location, "energy": .8}, "visible_actors": [], "known_nodes": []}
		var snapshot_before: Dictionary = api.snapshot.duplicate(true)
		var scene: Node3D = load(paths[location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		scene.get_node("Player").set_physics_process(false)
		var before: Array = []
		physical_state(scene, before)
		await process_frame
		await process_frame
		var dressing := scene.get_node_or_null("InteriorDressing")
		check(dressing != null, location + ": interior not dressed")
		if dressing != null:
			check(not dressing.find_children("*", "Light3D", true, false).is_empty(), location + ": no light fixtures")
			check(dressing.find_children("*", "CollisionObject3D", true, false).is_empty(), location + ": dressing has collisions")
		var after: Array = []
		physical_state(scene, after)
		check(before == after, location + ": dressing changed collisions")
		check(api.snapshot == snapshot_before, location + ": dressing changed the snapshot")
		for level in [0, 1, 2]:
			director.apply_quality(level, false)
			var probe := scene.get_node_or_null("InteriorDressing/InteriorProbe")
			check(probe == null or probe.visible == (level == 2), location + ": reflection probe ignores quality")
		if location == "VIDEO_CLUB":
			var restocked := 0
			for node in scene.find_children("Stock*", "MeshInstance3D", true, false):
				if node.material_override != null and node.material_override.resource_name == "PBR10_dress":
					restocked += 1
			check(restocked > 40, "VIDEO_CLUB: tapes keep their old grey covers (%d)" % restocked)
		if location == "ARCADE":
			check(scene.find_children("Dress_ScreenGlow", "OmniLight3D", true, false).size() >= 8, "ARCADE: screens do not glow")
		scene.queue_free()
		current_scene = null
		await process_frame
	print("INTERIORS22_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
