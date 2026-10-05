extends SceneTree
## Echoes in the world: an ECHO_ actor in the snapshot appears as a translucent
## citizen with its echo label, can be talked to like anyone, and leaves when it
## walks on. Optional capture: -- C:/out/folder
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node_or_null("Guide")
	if guide != null:
		guide.hidden_by_player = true
	var echo := {"id": "ECHO_PLAYER_ANA", "name": "Eco de Ana", "kind": "echo"}
	api.snapshot = {"minute": 3, "player": {"location": "CAFE", "energy": 1.0}, "known_nodes": [],
		"visible_actors": [echo], "prologue": {"enabled": true, "stage": "CONNECTED"}}
	var scene: Node3D = load("res://scenes/city09/Cafe.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	scene.get_node("Player").set_physics_process(false)
	for i in range(4):
		await process_frame
	api.snapshot_updated.emit(api.snapshot)
	await process_frame
	var actor := scene.find_child("ECHO_PLAYER_ANA", true, false) as Node3D
	check(actor != null, "the echo is not in the scene")
	if actor != null:
		check(actor.has_meta("echo") and actor.get("actor_id") == "ECHO_PLAYER_ANA", "the echo is not an interactable actor")
		var meshes: Array = actor.get_meta("echo_meshes", [])
		check(not meshes.is_empty() and meshes.all(func(mesh): return mesh.transparency >= 0.5), "the echo is not translucent")
		var label := actor.get_node_or_null("Activity") as Label3D
		check(label != null and label.text == "eco · lo que queda de una sesión", "the echo label is missing")
		var name_label := actor.get_node_or_null("NameLabel") as Label3D
		check(name_label != null and name_label.text == "Eco de Ana", "the echo has no name")
		var options := OS.get_cmdline_user_args()
		if not options.is_empty():
			var player := scene.get_node("Player") as Node3D
			player.global_position = actor.global_position + Vector3(-1.2, 0, 0.6)
			await create_timer(0.8).timeout
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(options[0].path_join("echo.png"))
	# The echo walks on: it leaves the scene.
	api.snapshot.visible_actors = []
	api.snapshot_updated.emit(api.snapshot)
	await process_frame
	await process_frame
	check(scene.find_child("ECHO_PLAYER_ANA", true, false) == null, "the echo stays after walking on")
	scene.queue_free()
	current_scene = null
	await process_frame
	print("ECHO_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
