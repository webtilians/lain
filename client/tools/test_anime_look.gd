extends SceneTree
## The anime look (ARTE.md): people are cel-shaded (toon light, hard highlight, a
## rim), places keep their own materials, ink lines sit on the camera, colour is a
## little livelier; people who arrive later are dressed too; and F9's switch gives
## every material back exactly. Never calls the server.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func frames(count: int = 3) -> void:
	for i in range(count):
		await process_frame

func first_mesh(node: Node) -> MeshInstance3D:
	for mesh in node.find_children("*", "MeshInstance3D", true, false):
		if mesh.mesh != null and mesh.get_active_material(0) is BaseMaterial3D:
			return mesh
	return null

func run() -> void:
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_anime_test.cfg"
	guide.hidden_by_player = true
	var graphics := root.get_node("GraphicsDirector")
	graphics.anime = true
	var scene: Node3D = load("res://scenes/apartment/ApartmentIso.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	await frames(5)

	var person := first_mesh(scene.get_node("Player"))
	check(person != null, "the player has no mesh to dress")
	var cel: BaseMaterial3D = person.get_active_material(0)
	check(cel.diffuse_mode == BaseMaterial3D.DIFFUSE_TOON and cel.rim_enabled and not cel.normal_enabled,
		"the player is not cel-shaded")
	var furniture := first_mesh(scene.get_node("Monitor"))
	if furniture != null:
		check(furniture.get_active_material(0).diffuse_mode != BaseMaterial3D.DIFFUSE_TOON, "a place loses its own light")
	check(graphics.environments.all(func(e): return e.adjustment_enabled and e.adjustment_saturation > 1.0),
		"the colour is not livelier")

	# Someone who comes in later is dressed as well.
	var visitor := CharacterBody3D.new()
	var body := MeshInstance3D.new()
	body.mesh = CapsuleMesh.new()
	body.material_override = StandardMaterial3D.new()
	visitor.add_child(body)
	scene.add_child(visitor)
	await frames()
	check(body.material_override.diffuse_mode == BaseMaterial3D.DIFFUSE_TOON, "a newcomer is not cel-shaded")

	# The ink lines live on the camera.
	var camera := Camera3D.new()
	scene.add_child(camera)
	await frames()
	graphics.anime_look.outline(camera, true)
	var lines := camera.get_node_or_null("AnimeOutline") as MeshInstance3D
	check(lines != null and lines.material_override.shader.resource_path.ends_with("anime_outline.gdshader"),
		"the camera has no ink lines")

	# F9: the realistic look, with every material given back.
	graphics.set_anime(false)
	await frames()
	check(person.get_active_material(0).diffuse_mode != BaseMaterial3D.DIFFUSE_TOON and not person.has_meta("anime_original"),
		"switching off keeps the cel shading")
	check(body.material_override.diffuse_mode != BaseMaterial3D.DIFFUSE_TOON, "a newcomer keeps the cel shading")
	check(not lines.visible and graphics.environments.all(func(e): return not e.adjustment_enabled),
		"switching off keeps the lines or the colour")
	graphics.set_anime(true)
	await frames()
	check(person.get_active_material(0).diffuse_mode == BaseMaterial3D.DIFFUSE_TOON, "switching on again does nothing")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(guide.config_path))
	scene.queue_free()
	current_scene = null
	await frames()
	print("ANIME_LOOK_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
