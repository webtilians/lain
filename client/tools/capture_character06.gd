extends SceneTree
## Offline studio preview of the shipped character scenes.
func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	var stage := Node3D.new()
	root.add_child(stage)
	var models := ["LainInspired", "LainSlender", "LainSlender"]
	for i in range(3):
		var model: Node3D = load("res://art/characters/"+models[i]+".tscn").instantiate()
		stage.add_child(model)
		model.position = Vector3((i-1)*1.05, 0.87, 0)
		model.rotation.y = 1.1 if i==2 else 0.16
		var label := Label3D.new()
		label.text = ["ANTES", "AHORA", "TRES CUARTOS"][i]
		label.font_size = 32
		label.pixel_size = 0.003
		label.outline_size = 0
		label.position = Vector3((i-1)*1.05, -0.13, 0.1)
		stage.add_child(label)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("242630")
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color("9da3ba")
	env.environment.ambient_light_energy = 0.65
	stage.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-40,-28,0)
	light.light_color = Color("f4e5d0")
	light.light_energy = 1.2
	stage.add_child(light)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 2.2
	camera.position = Vector3(0.05,1.8,7)
	camera.look_at(Vector3(0,0.86,0))
	camera.current = true
	await process_frame
	await RenderingServer.frame_post_draw
	var args := OS.get_cmdline_user_args()
	if args.size() != 1 or root.get_texture().get_image().save_png(args[0]) != OK:
		quit(1)
		return
	print("CHARACTERS_PREVIEW_OK")
	quit()
