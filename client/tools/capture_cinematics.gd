extends SceneTree
## Offline frames of the intro terminal and the cinematics (never calls the server):
##   Godot --path client --script res://tools/capture_cinematics.gd --resolution 1280x720 -- C:/out/folder
var folder := ""

func _initialize() -> void:
	call_deferred("capture")

func shot(name: String) -> void:
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(folder.path_join(name + ".png"))
	print("CAPTURE_SAVED ", name)

func capture() -> void:
	folder = OS.get_cmdline_user_args()[0]
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_capture.cfg"
	guide.hidden_by_player = true
	# The terminal before the menu.
	var intro: Node = load("res://scripts/ui/Intro.gd").new()
	root.add_child(intro)
	await create_timer(4.0).timeout
	await shot("intro-typing")
	intro.show_all()
	await create_timer(0.3).timeout
	await shot("intro-complete")
	intro.queue_free()
	# The cinematics, over the apartment.
	var cinematic := root.get_node("Cinematic")
	cinematic.enabled = true
	cinematic.config_path = "user://cinematics_capture.cfg"
	cinematic.seen = []
	api.snapshot = {"minute": 3, "player": {"location": "APARTMENT", "energy": 1.0}, "visible_actors": [], "known_nodes": [],
		"prologue": {"enabled": true, "stage": "FIND_TEACHER", "hint": ""}}
	var scene: Node3D = load("res://scenes/apartment/ApartmentIso.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	await create_timer(6.0).timeout
	await shot("opening-text")
	while cinematic.title.text.is_empty():
		await process_frame
	await create_timer(0.6).timeout
	await shot("opening-returned")
	while root.get_node_or_null("CinematicCamera") == null:
		await process_frame
	await create_timer(2.6).timeout
	await shot("opening-camera")
	await create_timer(3.6).timeout
	await shot("opening-camera-end")
	while cinematic.is_playing():
		await process_frame
	cinematic.play({"id": "wired"})
	await create_timer(4.5).timeout
	await shot("wired")
	while cinematic.is_playing():
		await process_frame
	cinematic.play({"id": "fragment", "layer": "layer_three", "count": 3})
	await create_timer(4.8).timeout
	await shot("fragment")
	while cinematic.is_playing():
		await process_frame
	cinematic.play({"id": "ending", "decision": "DISCONNECT", "count": 7})
	while cinematic.title.text.is_empty():
		await process_frame
	await create_timer(2.5).timeout
	await shot("ending")
	cinematic.skipping = true
	while cinematic.is_playing():
		await process_frame
	for file in ["user://guide_capture.cfg", "user://cinematics_capture.cfg"]:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(file))
	quit()
