extends SceneTree
## Offline integration: rendering presets must never change the physical world.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func physical_state(node: Node, state: Array) -> void:
	if node is CollisionShape3D:
		state.append([str(node.get_path()),node.transform,node.shape.get_instance_id(),node.disabled])
	if node is CollisionObject3D:
		state.append([str(node.get_path()),node.transform,node.collision_layer,node.collision_mask])
	for child in node.get_children():
		physical_state(child,state)

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var director := root.get_node("GraphicsDirector")
	var settings_before := FileAccess.get_file_as_bytes(director.CONFIG_PATH) if FileAccess.file_exists(director.CONFIG_PATH) else PackedByteArray()
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for location in paths:
		api.snapshot={"minute":17,"player":{"location":location,"energy":.8},"visible_actors":[],"known_nodes":[]}
		var snapshot_before: Dictionary = api.snapshot.duplicate(true)
		var scene: Node3D = load(paths[location]).instantiate()
		root.add_child(scene)
		current_scene=scene
		var player: CharacterBody3D=scene.get_node("Player")
		player.set_physics_process(false)
		var before: Array = []
		physical_state(scene,before)
		var camera: Transform3D = player.camera.transform
		await process_frame
		await process_frame
		if DisplayServer.get_name()!="headless":
			# Existing procedural textures upload asynchronously on OpenGL.
			await create_timer(.5).timeout
			await RenderingServer.frame_post_draw
		check(scene.has_node("GraphicsHUD"),location+": presentation not applied")
		for level in [0,1,2,1]:
			director.apply_quality(level,false)
			var after: Array = []
			physical_state(scene,after)
			check(before==after,location+": quality changed collision or actor state")
			check(player.camera.transform==camera,location+": quality moved camera")
			check(api.snapshot==snapshot_before,location+": presentation changed snapshot")
			for environment in director.environments:
				check(environment.sdfgi_enabled==(director.forward_plus and level==2 and director.exterior),"SDFGI fallback incorrect")
				check(not environment.sdfgi_enabled or environment.sky!=null,"Exterior GI has no sky")
		if location=="APARTMENT_DISTRICT":
			var populated := 0
			var pbr_count := 0
			for node in scene.find_children("*","GeometryInstance3D",true,false):
				var material: Material = node.material_override
				if material!=null and material.resource_name.begins_with("PBR10_"):
					pbr_count+=1
			check(pbr_count>100,"Saved MultiMesh surfaces did not receive PBR materials")
			for batch in scene.get_node("RealisticFoliage").get_children():
				populated+=batch.multimesh.instance_count
				if DisplayServer.get_name()!="headless":
					check(batch.multimesh.get_instance_transform(0).origin.length()>0,"Foliage buffer lost at save")
			check(populated>20000,"Foliage asset empty or incomplete")
		print("REALISM10_LOCATION_OK ",location)
		scene.queue_free()
		await process_frame
		if DisplayServer.get_name()!="headless":
			await RenderingServer.frame_post_draw
	var settings_after := FileAccess.get_file_as_bytes(director.CONFIG_PATH) if FileAccess.file_exists(director.CONFIG_PATH) else PackedByteArray()
	check(settings_before==settings_after,"Loading scenes overwrote the user's graphics preference")
	# Bevels retain the original furniture bounds and use valid smooth normals.
	var box := BoxMesh.new()
	box.size=Vector3(1.5,.1,.8)
	var rounded: Mesh = director.soft_edges.furniture_mesh(box,"DeskTable")
	check(rounded is ArrayMesh,"Furniture still has razor-sharp primitive edges")
	check(rounded.get_aabb().size.is_equal_approx(box.size),"Bevel changed furniture size")
	for normal in rounded.surface_get_arrays(0)[Mesh.ARRAY_NORMAL]:
		check(normal.is_finite() and absf(normal.length()-1)<.001,"Invalid furniture normal")
	if failures.is_empty():
		print("REALISM10_CHECK_OK scenes=",paths.size()," presets=3 physics_unchanged=true")
	director.environments.clear()
	director.materials.cache.clear()
	director.soft_edges.cache.clear()
	await process_frame
	quit(0 if failures.is_empty() else 1)
