extends Node
## Presentation only. Never reads or writes world state, actor data or SQLite.
## Applies the same lighting/material pipeline to saved and scripted locations.
const MATERIALS = preload("res://scripts/art/RealismMaterials.gd")
const QUALITY_NAMES := ["Ligera", "Equilibrada", "Alta"]
const CONFIG_PATH := "user://graphics10.cfg"
# Visual 0.12 eternal night. The photographed twilight sky (Poly Haven, CC0)
# has its bright disc clamped out and is dimmed to a faint blue-violet
# gradient for reflections. Godot samples panoramas from -Z; the clamped disc
# at u = 0.600 lies at this bearing, expressed as atan2(x, z) toward it.
const SKY_HDRI := "res://art/gothic12/sky/qwantani_moonrise_puresky_2k_night.hdr"
const SKY_SUN_AZIMUTH := -36.1
const SKY_ENERGY := .045
# A low, rose-violet moon on the authored district bearing.
const SUN_AZIMUTH := -32.0
const SUN_ELEVATION := 34.0
const RAIN_DROPS := [1200, 2800, 5200]
var materials = MATERIALS.new()
var soft_edges = preload("res://scripts/art/SoftEdges.gd").new()
var dresser = preload("res://scripts/art/InteriorDresser.gd").new(materials)
const ANIME_LOOK = preload("res://scripts/art/AnimeLook.gd")
var anime_look = ANIME_LOOK.new()
var anime := true  # the anime look (ARTE.md); F9 switches to the realistic one and back
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
		anime = bool(config.get_value("graphics","anime",true))
	if "--render-balanced" in OS.get_cmdline_user_args():
		quality = 1
	elif "--render-high" in OS.get_cmdline_user_args():
		quality = 2
	if "--render-realistic" in OS.get_cmdline_user_args():
		anime = false
	get_tree().node_added.connect(_on_node_added)

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
	elif event.keycode == KEY_F9:
		set_anime(not anime, true)
		get_viewport().set_input_as_handled()

func set_anime(on: bool, persist: bool = false) -> void:
	anime = on
	if is_instance_valid(scene_ref):
		anime_look.apply(scene_ref, anime, forward_plus)
	apply_quality(quality, persist)

func _on_node_added(node: Node) -> void:
	# People and things that arrive later (residents, other players, a cinematic camera),
	# once they are set up; the look may have been switched off in between.
	if anime and is_instance_valid(scene_ref) and scene_ref.is_ancestor_of(node) 			and (node is GeometryInstance3D or node is Camera3D):
		_dress_late.call_deferred(node)

func _dress_late(node: Node) -> void:
	if not anime or not is_instance_valid(node) or not node.is_inside_tree():
		return
	if node is Camera3D:
		anime_look.outline(node, forward_plus)
	else:
		anime_look.dress(node, true)

func apply_scene(scene: Node3D) -> void:
	scene_ref = scene
	environments.clear()
	exterior = scene.scene_file_path.contains("apartment_district")
	visit(scene, false)
	if not exterior:
		dresser.dress(scene, location_of(scene))
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
		add_rain(scene)
	var overlay := scene.get_node_or_null("RetroOverlay/CRT") as ColorRect
	if overlay != null:
		var grade := ShaderMaterial.new()
		grade.shader = load("res://shaders/gothic_grade.gdshader")
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
	anime_look.apply(scene, anime, forward_plus)
	apply_quality(quality, false)

func location_of(scene: Node) -> String:
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for location in paths:
		if paths[location] == scene.scene_file_path:
			return location
	return ""

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
		if exterior:
			# The isometric camera sits ~46 m back and sees a ~25 m deep slab of
			# street. Depth splits would leave that slab in the coarse far
			# cascades and cut seams across the screen; one map fits it evenly.
			node.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
			node.directional_shadow_max_distance = 80
		node.shadow_normal_bias = .7
		node.shadow_bias = .04
		node.light_angular_distance = .55 if exterior else 1.2
		node.light_indirect_energy = .85
		if exterior:
			# Direction toward the moon is the light's +Z axis.
			node.rotation_degrees = Vector3(-SUN_ELEVATION, SUN_AZIMUTH, 0)
			node.light_color = Color("c9a3b4")
			node.light_energy = .6
		else:
			node.light_energy *= .35
	elif node is OmniLight3D:
		node.light_indirect_energy = .65
		if not exterior:
			# Visual 0.22: the room's own fill lamps stay steady and slightly warm;
			# the fixtures added by InteriorDresser do the real lighting.
			node.light_color = node.light_color.lerp(Color("ffd2a0"), .25)
			node.light_energy *= 1.1
			node.light_size = .45
			node.shadow_enabled = false
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

## Rain that follows the player: streaks falling through a box above the view.
func add_rain(scene: Node3D) -> void:
	var player := scene.get_node_or_null("Player") as Node3D
	if player == null or player.has_node("Rain12"):
		return
	var process := ParticleProcessMaterial.new()
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	process.emission_box_extents = Vector3(26, .5, 26)
	process.direction = Vector3(.12, -1, .05)
	process.spread = 2.0
	process.initial_velocity_min = 21.0
	process.initial_velocity_max = 25.0
	process.gravity = Vector3(0, -9.8, 0)
	var streak := QuadMesh.new()
	streak.size = Vector2(.016, .62)
	var look := StandardMaterial3D.new()
	look.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	look.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	look.albedo_color = Color(.72, .74, .86, .32)
	look.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
	look.billboard_keep_scale = true
	streak.material = look
	var rain := GPUParticles3D.new()
	rain.name = "Rain12"
	rain.process_material = process
	rain.draw_pass_1 = streak
	rain.lifetime = 1.15
	rain.preprocess = 1.2
	rain.amount = RAIN_DROPS[quality]
	rain.position = Vector3(0, 17, 0)
	rain.visibility_aabb = AABB(Vector3(-30, -25, -30), Vector3(60, 30, 60))
	rain.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	player.add_child(rain)

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
	if is_instance_valid(scene_ref) and scene_ref.has_node("Player/Rain12"):
		scene_ref.get_node("Player/Rain12").amount = RAIN_DROPS[quality]
	# Ligera keeps street, neon and door lights but drops window and corridor fill.
	if is_instance_valid(scene_ref):
		for light in scene_ref.find_children("*", "Light3D", true, false):
			if light.has_meta("detail_light"):
				light.visible = quality > 0
	dresser.apply_quality(quality)
	if is_instance_valid(quality_label):
		quality_label.text = "F6  ·  GRÁFICOS: " + QUALITY_NAMES[quality] + ("  ·  Compatibilidad" if not forward_plus else "") 			+ "   F9  ·  ESTILO: " + ("Anime" if anime else "Realista")
	if persist:
		var config := ConfigFile.new()
		config.set_value("graphics","quality",quality)
		config.set_value("graphics","anime",anime)
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
	# Wet streets need screen-space reflections of neon and lamps outdoors too.
	e.ssr_enabled = forward_plus and quality == 2
	e.ssr_max_steps = 48
	e.ssr_depth_tolerance = .3
	# SDFGI is off: under the isometric orthographic camera it draws a seam of
	# brighter indirect light that stays fixed on screen and follows the player.
	# Exterior bounce comes from SSIL and the photographed sky's ambient instead.
	e.sdfgi_enabled = false
	e.glow_enabled = forward_plus and quality > 0
	e.glow_intensity = .35
	e.glow_bloom = .02
	e.glow_hdr_threshold = 1.2
	e.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
	if exterior:
		if exterior_sky == null:
			exterior_sky = Sky.new()
			if ResourceLoader.exists(SKY_HDRI):
				var panorama := PanoramaSkyMaterial.new()
				panorama.panorama = load(SKY_HDRI)
				panorama.energy_multiplier = SKY_ENERGY
				exterior_sky.sky_material = panorama
			else:
				exterior_sky.sky_material = ProceduralSkyMaterial.new()
			exterior_sky.radiance_size = Sky.RADIANCE_SIZE_256
			exterior_sky.process_mode = Sky.PROCESS_MODE_QUALITY
		e.sky = exterior_sky
		e.background_mode = Environment.BG_SKY
		# Turn the photographed sun onto the same bearing as the scene's sun.
		e.sky_rotation = Vector3(0, deg_to_rad(SUN_AZIMUTH - SKY_SUN_AZIMUTH), 0)
		# Night: faint violet ambient; neon, lamps and lit windows do the work.
		e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		e.ambient_light_color = Color("3a3150")
		e.ambient_light_energy = 1.0
		e.ambient_light_sky_contribution = 0.0
		e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
		e.ssil_intensity = 1.0
		e.tonemap_exposure = 1.55
		e.glow_intensity = .75
		e.glow_bloom = .06
		e.glow_hdr_threshold = .9
		e.glow_hdr_luminance_cap = 12.0
		e.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
		# Dark haze with mist pooled at street level.
		e.fog_enabled = quality > 0
		e.fog_light_color = Color("1c1629")
		e.fog_light_energy = 1.0
		e.fog_density = .0022
		e.fog_sun_scatter = .15
		e.fog_height = 1.4
		e.fog_height_density = .35
		e.fog_aerial_perspective = .0
		e.fog_sky_affect = .0
		# Volumetric fog froxels assume a perspective frustum: under the isometric
		# orthographic camera they render as a polygonal wedge that follows the
		# player. Depth fog above provides the haze instead.
		e.volumetric_fog_enabled = false
	else:
		# Visual 0.22 interiors: a neutral bounce under real fixtures, so walls and
		# floors keep their colour instead of sinking into violet.
		e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		e.ambient_light_color = Color("5a554e")
		e.ambient_light_energy = .5
		e.ambient_light_sky_contribution = 0
		e.tonemap_exposure = 1.2
		e.glow_intensity = .55
		e.glow_hdr_threshold = 1.0
		e.fog_enabled = false
	ANIME_LOOK.environment(e, anime)
