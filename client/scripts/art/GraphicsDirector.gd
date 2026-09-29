extends Node
## Presentation only. Never reads or writes world state, actor data or SQLite.
## Applies the same lighting/material pipeline to saved and scripted locations.
const MATERIALS = preload("res://scripts/art/RealismMaterials.gd")
const QUALITY_NAMES := ["Ligera", "Equilibrada", "Alta"]
const CONFIG_PATH := "user://graphics10.cfg"
# Photographed late-afternoon sky (Poly Haven, CC0) with the solar disc clamped
# out: the DirectionalLight is the only sun. Godot samples panoramas
# from -Z (u = atan2(x, -z) / TAU); the photo's sun at u = 0.600 therefore lies
# at this bearing, expressed like SUN_AZIMUTH as atan2(x, z) toward the sun.
const SKY_HDRI := "res://art/photoreal11/sky/qwantani_late_afternoon_puresky_2k_nosun.hdr"
const SKY_SUN_AZIMUTH := -36.1
# Exterior sun: same compass direction as the authored district, lower and warmer.
const SUN_AZIMUTH := -32.0
const SUN_ELEVATION := 24.0
var materials = MATERIALS.new()
var soft_edges = preload("res://scripts/art/SoftEdges.gd").new()
var quality := 2
var current_id := 0
var environments: Array[Environment] = []
var scene_ref: Node3D
var exterior := false
var quality_label: Label
var forward_plus := false
var baseline := false
var exterior_sky: Sky

func _ready() -> void:
	baseline = "--render-baseline" in OS.get_cmdline_user_args()
	forward_plus = RenderingServer.get_current_rendering_method() == "forward_plus"
	var config := ConfigFile.new()
	if config.load(CONFIG_PATH) == OK:
		quality = clampi(int(config.get_value("graphics","quality",2)),0,2)
	if "--render-balanced" in OS.get_cmdline_user_args():
		quality = 1
	elif "--render-high" in OS.get_cmdline_user_args():
		quality = 2

func _process(_delta: float) -> void:
	if baseline:
		return
	var scene := get_tree().current_scene as Node3D
	if scene == null or scene.get_instance_id() == current_id:
		return
	current_id = scene.get_instance_id()
	apply_scene(scene)

func _unhandled_key_input(event: InputEvent) -> void:
	if baseline or not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_F6:
		apply_quality((quality+1)%3, true)
		get_viewport().set_input_as_handled()

func apply_scene(scene: Node3D) -> void:
	scene_ref = scene
	environments.clear()
	exterior = scene.scene_file_path.contains("apartment_district")
	visit(scene, false)
	if environments.is_empty():
		var environment := WorldEnvironment.new()
		environment.name = "RealismEnvironment"
		environment.environment = Environment.new()
		environment.environment.background_mode = Environment.BG_COLOR
		environment.environment.background_color = Color("20252d")
		scene.add_child(environment)
		environments.append(environment.environment)
	if exterior:
		add_shadow_shells(scene.get_node("CityArt"))
		if not scene.has_node("RealisticFoliage") and ResourceLoader.exists("res://art/realism10/Foliage.tscn"):
			var foliage: Node3D = load("res://art/realism10/Foliage.tscn").instantiate()
			foliage.name = "RealisticFoliage"
			scene.add_child(foliage)
	var overlay := scene.get_node_or_null("RetroOverlay/CRT") as ColorRect
	if overlay != null:
		var grade := ShaderMaterial.new()
		grade.shader = load("res://shaders/realism_grade.gdshader")
		overlay.material = grade
	var hud := CanvasLayer.new()
	hud.name = "GraphicsHUD"
	hud.layer = 21
	scene.add_child(hud)
	quality_label = Label.new()
	quality_label.position = Vector2(29,142) if scene.has_node("HUD/Info") else Vector2(29,61)
	quality_label.add_theme_font_size_override("font_size",11)
	quality_label.add_theme_color_override("font_color",Color("c0c7c8"))
	quality_label.add_theme_color_override("font_shadow_color",Color("242b36"))
	quality_label.add_theme_constant_override("shadow_offset_x",1)
	quality_label.add_theme_constant_override("shadow_offset_y",1)
	hud.add_child(quality_label)
	apply_quality(quality, false)

func visit(node: Node, dynamic: bool) -> void:
	dynamic = dynamic or node.name in ["Player","Actors","PROFESSOR","RYOKO"]
	if node is WorldEnvironment and node.environment != null:
		node.environment = node.environment.duplicate()
		environments.append(node.environment)
	if node is GeometryInstance3D:
		# Characters receive lighting without being baked into static GI.
		node.gi_mode = GeometryInstance3D.GI_MODE_DISABLED if dynamic else GeometryInstance3D.GI_MODE_STATIC
	if node is MeshInstance3D or node is MultiMeshInstance3D:
		var mesh: Mesh = node.mesh if node is MeshInstance3D else node.multimesh.mesh
		var original: Material = node.material_override
		if original == null and mesh != null and mesh.get_surface_count() == 1:
			original = node.get_active_material(0) if node is MeshInstance3D else mesh.surface_get_material(0)
		if not dynamic and original != null:
			if exterior and original.resource_name in ["leaf","leaves"] and ResourceLoader.exists("res://art/realism10/Foliage.tscn"):
				node.visible = false
			node.material_override = materials.replacement(original,str(node.get_path()),not exterior)
			if not exterior and node is MeshInstance3D and mesh is BoxMesh:
				node.mesh = soft_edges.furniture_mesh(mesh,str(node.get_path()))
	elif node is CSGBox3D or node is CSGCylinder3D:
		if node.material != null:
			node.material = materials.replacement(node.material,str(node.get_path()),not exterior)
	if node is DirectionalLight3D:
		node.shadow_enabled = true
		node.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
		node.directional_shadow_max_distance = 85 if exterior else 35
		node.shadow_normal_bias = .7
		node.shadow_bias = .04
		node.light_angular_distance = .55 if exterior else 1.2
		node.light_indirect_energy = .85
		if exterior:
			# Direction toward the sun is the light's +Z axis.
			node.rotation_degrees = Vector3(-SUN_ELEVATION, SUN_AZIMUTH, 0)
			node.light_color = Color("ffd9ae")
			node.light_energy = 3.0
			node.light_volumetric_fog_energy = 1.4
	elif node is OmniLight3D:
		node.light_indirect_energy = .65
		if not exterior:
			node.light_energy *= 2.4
			node.light_size = .45
			node.shadow_enabled = true
			node.shadow_bias = .06
			node.shadow_normal_bias = .7
	for child in node.get_children():
		visit(child,dynamic)

func add_shadow_shells(node: Node) -> void:
	# Cutaway upper shells can disappear for readability. Permanent, invisible
	# shadow casters keep the building's sunlight occlusion and GI stable.
	# Visual 0.11 buildings carry a shadow-only twin of their real geometry instead.
	if node.get_script() == load("res://scripts/art/CityCutaway.gd") and not node.has_node("ShadowShell10") and not node.has_node("ShadowCaster11"):
		var box: AABB = node.bounds
		var proxy := MeshInstance3D.new()
		proxy.name = "ShadowShell10"
		var mesh := BoxMesh.new()
		mesh.size = box.size
		proxy.mesh = mesh
		proxy.position = box.get_center()
		proxy.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		proxy.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		node.add_child(proxy)
	for child in node.get_children():
		add_shadow_shells(child)

func apply_quality(level: int, persist: bool = false) -> void:
	quality = clampi(level,0,2)
	var viewport := get_viewport()
	viewport.msaa_3d = Viewport.MSAA_4X if quality > 0 else Viewport.MSAA_2X
	# Temporal AA keeps thin overhead cables and roof tiles from crawling.
	viewport.use_taa = forward_plus and quality == 2
	var soft_shadows := RenderingServer.SHADOW_QUALITY_SOFT_HIGH
	if quality == 0:
		soft_shadows = RenderingServer.SHADOW_QUALITY_SOFT_LOW
	elif quality == 1:
		soft_shadows = RenderingServer.SHADOW_QUALITY_SOFT_MEDIUM
	RenderingServer.directional_soft_shadow_filter_set_quality(soft_shadows)
	RenderingServer.positional_soft_shadow_filter_set_quality(soft_shadows)
	for environment in environments:
		lighting(environment)
	if is_instance_valid(quality_label):
		quality_label.text = "F6  ·  GRÁFICOS: " + QUALITY_NAMES[quality] + ("  ·  Compatibilidad" if not forward_plus else "")
	if persist:
		var config := ConfigFile.new()
		config.set_value("graphics","quality",quality)
		var error := config.save(CONFIG_PATH)
		if error != OK:
			push_warning("No se pudo guardar la calidad gráfica.")

func lighting(e: Environment) -> void:
	e.tonemap_mode = Environment.TONE_MAPPER_AGX
	e.tonemap_exposure = 1.05 if exterior else 1.15
	e.ssao_enabled = forward_plus and quality > 0
	e.ssao_radius = .8
	e.ssao_intensity = 1.05
	e.ssao_power = 1.2
	e.ssao_detail = .55
	e.ssao_light_affect = .15
	e.ssil_enabled = forward_plus and quality > 0
	e.ssil_radius = 2.0
	e.ssil_intensity = .45
	e.ssr_enabled = forward_plus and quality == 2 and not exterior
	e.ssr_max_steps = 48
	e.ssr_depth_tolerance = .3
	e.sdfgi_enabled = forward_plus and quality == 2 and exterior
	e.sdfgi_cascades = 4
	e.sdfgi_min_cell_size = .3
	e.sdfgi_use_occlusion = true
	e.sdfgi_bounce_feedback = .4
	e.sdfgi_energy = 1.1
	e.sdfgi_read_sky_light = exterior
	e.sdfgi_y_scale = Environment.SDFGI_Y_SCALE_75_PERCENT
	e.sdfgi_normal_bias = 1.3
	e.glow_enabled = forward_plus and quality > 0
	e.glow_intensity = .07
	e.glow_bloom = .0
	e.glow_hdr_threshold = 3.0
	if exterior:
		if exterior_sky == null:
			exterior_sky = Sky.new()
			if ResourceLoader.exists(SKY_HDRI):
				var panorama := PanoramaSkyMaterial.new()
				panorama.panorama = load(SKY_HDRI)
				exterior_sky.sky_material = panorama
			else:
				exterior_sky.sky_material = ProceduralSkyMaterial.new()
			exterior_sky.radiance_size = Sky.RADIANCE_SIZE_256
			exterior_sky.process_mode = Sky.PROCESS_MODE_QUALITY
		e.sky = exterior_sky
		e.background_mode = Environment.BG_SKY
		# Turn the photographed sun onto the same bearing as the scene's sun.
		e.sky_rotation = Vector3(0, deg_to_rad(SUN_AZIMUTH - SKY_SUN_AZIMUTH), 0)
		e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		e.ambient_light_energy = .7
		e.ambient_light_sky_contribution = 1.0
		e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
		e.tonemap_exposure = 1.0
		e.glow_intensity = .12
		e.glow_bloom = .0
		e.glow_hdr_threshold = 1.6
		e.glow_hdr_luminance_cap = 6.0
		e.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
		e.fog_enabled = quality > 0
		e.fog_light_color = Color("a9a6a0")
		e.fog_density = .0006
		e.fog_aerial_perspective = .12
		e.fog_sky_affect = .0
		# Thin sunlit haze: depth between streets and visible late-sun scattering.
		e.volumetric_fog_enabled = forward_plus and quality == 2
		e.volumetric_fog_density = .0012
		e.volumetric_fog_albedo = Color("e6ddd0")
		e.volumetric_fog_anisotropy = .55
		e.volumetric_fog_length = 90.0
		e.volumetric_fog_ambient_inject = .15
		e.volumetric_fog_sky_affect = .0
	else:
		e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		e.ambient_light_color = Color("99a8c1")
		e.ambient_light_energy = .65
		e.ambient_light_sky_contribution = 0
		e.fog_enabled = false
