extends SceneTree
## Screenshots of actual gameplay scenes with the authored public population.
func _initialize() -> void:
	call_deferred("run")
func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		quit(1)
		return
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	for key in ["EventDialog","CharacterJournal","PrologueTerminal"]:
		root.get_node(key).set_process_unhandled_input(false)
		root.get_node(key).set_process_unhandled_key_input(false)
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	var catalog: Array = JSON.parse_string(FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://../server/world_core/data/residents09.json")))
	var views := [
		["apartment","APARTMENT",Vector3(0,.91,1)],
		["street","APARTMENT_DISTRICT",Vector3(-3,.91,-4)],
		["shops","APARTMENT_DISTRICT",Vector3(14,.91,9.7)],
		["park","APARTMENT_DISTRICT",Vector3(11,.91,-30)],
		["video-exterior","APARTMENT_DISTRICT",Vector3(17,.91,-42)],
		["videoclub","VIDEO_CLUB",Vector3(0,.91,1)],
		["izakaya","IZAKAYA",Vector3(0,.91,1)],
		["school","SCHOOL",Vector3(0,.91,1)],
		["arcade","ARCADE",Vector3(0,.91,1)],
		["station","STATION",Vector3(0,.91,1)],
		["nightclub","NIGHTCLUB",Vector3(0,.91,1)],
	]
	for view in views:
		var requested := ""
		for arg in args:
			if arg.begins_with("--view="):
				requested=arg.trim_prefix("--view=")
		if not requested.is_empty() and str(view[0])!=requested:
			continue
		var location: String = view[1]
		var actors: Array = []
		for item in catalog:
			if item.location==location:
				actors.append({"id":item.id,"name":item.name,"slot":item.slot,"patrol_step":0,"appearance":item.appearance,"activity":item.activities[0]})
		api.snapshot={"minute":0,"player":{"location":location,"energy":1.0},"visible_actors":actors,"known_nodes":[]}
		var scene: Node3D = load(paths[location]).instantiate()
		root.add_child(scene)
		current_scene=scene
		var player: CharacterBody3D=scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		player.position=view[2]
		player._update_camera()
		if location not in ["APARTMENT_DISTRICT","APARTMENT"]:
			player.camera.size=20
		await create_timer(3.0).timeout
		await RenderingServer.frame_post_draw
		var result := root.get_texture().get_image().save_png(args[0].path_join(str(view[0])+".png"))
		if result!=OK:
			quit(1)
			return
		print("REALISM10_CAPTURE ",view[0]," fps=",Engine.get_frames_per_second()," draws=",Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
		scene.queue_free()
		await process_frame
	quit()
