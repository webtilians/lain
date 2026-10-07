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
	# A place without a visible shape of its own: the faint floor glow and the key.
	player.global_position = home.get_node("Monitor").global_position + Vector3(0.6, -0.4, 0.9)
	await shot("highlight-home")
	# Someone standing in the room: the glow along their silhouette.
	var figure: Node3D = load("res://art/characters/LainSlender.tscn").instantiate()
	var usable := GDScript.new()
	usable.source_code = "extends Node3D\nfunc interact() -> void:\n\tpass\n"
	usable.reload()
	var holder := Node3D.new()
	holder.set_script(usable)
	holder.add_to_group("interactable")
	holder.add_child(figure)
	home.add_child(holder)
	holder.global_position = Vector3(0.8, player.global_position.y - 0.9, 0.2)
	player.global_position = holder.global_position + Vector3(0.9, 0.9, 0.9)
	await shot("highlight-figure")
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://guide_capture.cfg"))
	quit()
