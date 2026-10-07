extends SceneTree
## Frames of the interaction marks (never calls the server):
##   Godot --path client --script res://tools/capture_highlight.gd --resolution 1280x720 -- C:/out/folder
var folder := ""

func _initialize() -> void:
	call_deferred("capture")

func shot(name: String) -> void:
	for i in range(30):
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(folder.path_join(name + ".png"))
	print("CAPTURE_SAVED ", name)

func capture() -> void:
	folder = OS.get_cmdline_user_args()[0]
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_capture.cfg"
	guide.hidden_by_player = true
	root.get_node("WorldApi").snapshot = {"minute": 600, "player": {"location": "APARTMENT", "energy": 1.0},
		"visible_actors": [], "known_nodes": [], "prologue": {"enabled": true, "stage": "FIND_TEACHER", "hint": ""}}
	var home: Node3D = load("res://scenes/apartment/ApartmentIso.tscn").instantiate()
	root.add_child(home)
	current_scene = home
	var player: Node3D = home.get_node("Player")
	player.global_position = home.get_node("Monitor").global_position + Vector3(0.6, -0.4, 0.9)
	await shot("highlight-home")
	home.queue_free()
	await process_frame
	root.get_node("WorldApi").snapshot.player.location = "APARTMENT_DISTRICT"
	var district: Node3D = load("res://scenes/apartment_district/ApartmentDistrict.tscn").instantiate()
	root.add_child(district)
	current_scene = district
	await process_frame
	var street: Node3D = district.get_node("Player")
	var doors := get_nodes_in_group("interactable").filter(func(n): return n is Node3D and n.has_method("interact"))
	if not doors.is_empty():
		street.global_position = doors[0].global_position + Vector3(1.2, 0, 1.4)
	await shot("highlight-district")
	quit()
