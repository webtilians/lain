extends SceneTree
## Real leaf geometry, replacing flat textured cards without changing collisions.
## Deterministic offline authoring; requires the renderer to read MultiMesh buffers.
var leaves := Node3D.new()
var rng := RandomNumberGenerator.new()
var leaf_mesh: ArrayMesh
var count := 0

func _initialize() -> void:
	call_deferred("build")

func make_leaf() -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var points := [Vector3(0,-.55,0),Vector3(-.23,-.12,.01),Vector3(-.20,.24,.01),
		Vector3(0,.60,-.02),Vector3(.22,.24,.01),Vector3(.24,-.14,.01)]
	var center := Vector3(0,0,.07)
	for i in range(points.size()):
		for v in [center,points[i],points[(i+1)%points.size()]]:
			surface.add_vertex(v)
	surface.generate_normals()
	return surface.commit()

func visit(node: Node) -> void:
	var original: Material
	if node is MultiMeshInstance3D:
		original = node.material_override
		if original == null:
			original = node.multimesh.mesh.surface_get_material(0)
	if original != null and original.resource_name in ["leaf","leaves"]:
		var unique := {}
		var transforms: Array[Transform3D] = []
		var colors: Array[Color] = []
		for i in range(node.multimesh.instance_count):
			var source: Transform3D = node.multimesh.get_instance_transform(i)
			var key := str(source.origin.snapped(Vector3.ONE*.05))
			if unique.has(key):
				continue
			unique[key] = true
			var sx := source.basis.x.length()
			var sy := source.basis.y.length()
			var amount := clampi(int(sx*sy*75),14,280)
			for j in range(amount):
				var direction := Vector3(rng.randf_range(-1,1),rng.randf_range(-1,1),rng.randf_range(-1,1)).normalized()
				var radius := pow(rng.randf(),.333)
				var offset := direction*Vector3(sx*.52,sy*.46,sx*.48)*radius
				var size := rng.randf_range(.10,.22)
				var basis := Basis.from_euler(Vector3(rng.randf_range(-1.1,1.1),rng.randf()*TAU,rng.randf()*TAU))*Basis.from_scale(Vector3.ONE*size)
				transforms.append(Transform3D(basis,source.origin+offset))
				colors.append([Color("667950"),Color("75845a"),Color("8b9466"),Color("536a46")][rng.randi_range(0,3)])
		var multimesh := MultiMesh.new()
		multimesh.transform_format = MultiMesh.TRANSFORM_3D
		multimesh.use_colors = true
		multimesh.mesh = leaf_mesh
		multimesh.instance_count = transforms.size()
		for i in range(transforms.size()):
			multimesh.set_instance_transform(i,transforms[i])
			multimesh.set_instance_color(i,colors[i])
		var instance := MultiMeshInstance3D.new()
		instance.name = "LeafCluster"
		instance.multimesh = multimesh
		instance.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
		var material := StandardMaterial3D.new()
		material.vertex_color_use_as_albedo = true
		material.vertex_color_is_srgb = true
		material.cull_mode = BaseMaterial3D.CULL_DISABLED
		material.roughness = .82
		material.backlight_enabled = true
		material.backlight = Color(.32,.38,.20)
		material.resource_name = "RealLeaf10"
		instance.material_override = material
		leaves.add_child(instance,true)
		instance.owner = leaves
		count += transforms.size()
	for child in node.get_children():
		visit(child)

func build() -> void:
	if DisplayServer.get_name() == "headless":
		push_error("Use a real renderer for MultiMesh authoring")
		leaves.free()
		quit(1)
		return
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	rng.seed = 100924
	leaves.name = "RealisticFoliage"
	leaf_mesh = make_leaf()
	var district: Node3D = load("res://art/reference09/Neighborhood.tscn").instantiate()
	visit(district)
	if count == 0:
		push_error("No foliage found; refusing to save an empty replacement")
		district.free()
		leaves.free()
		quit(1)
		return
	await RenderingServer.frame_post_draw
	var packed := PackedScene.new()
	if packed.pack(leaves) != OK or ResourceSaver.save(packed,"res://art/realism10/Foliage.tscn") != OK:
		push_error("Cannot save foliage")
		quit(1)
		return
	print("FOLIAGE10_BUILT leaves=",count," batches=",leaves.get_child_count())
	leaves.free()
	district.free()
	quit()
