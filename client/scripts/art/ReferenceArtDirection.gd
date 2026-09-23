extends Node3D
## Visual 0.5 art direction: presentation only, never modifies World Core.
## The reference is an elevated, muted environmental painting, not a low-poly
## material. Keep authored props/UV textures; give only large masonry and
## paving surfaces subtle, continuous, physically lit variation.

const MATTE_SHADER = preload("res://shaders/art_matte_surface.gdshader")

@export_enum("apartment", "district", "station", "old_district") var scene_style := "district"

var materials: Dictionary = {}

func _ready() -> void:
	var room := get_parent() as Node3D
	if room == null:
		return
	_make_materials()
	_grade_environment(room)
	_style_architecture(room)
	_style_lights(room)

func _make_matte(tint: Color, grain: float, wear: float) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = MATTE_SHADER
	material.set_shader_parameter("base_color", tint)
	material.set_shader_parameter("grain_size", grain)
	material.set_shader_parameter("wear", wear)
	material.set_shader_parameter("surface_roughness", 0.96)
	return material

func _make_materials() -> void:
	materials["asphalt"] = _make_matte(Color("50505a"), 13.0, 0.10)
	materials["paving"] = _make_matte(Color("77727c"), 15.0, 0.13)
	materials["plaster"] = _make_matte(Color("a19a9b"), 8.0, 0.09)
	materials["wall"] = _make_matte(Color("898389"), 10.0, 0.17)
	materials["platform"] = _make_matte(Color("6c6d74"), 15.0, 0.10)
	materials["ballast"] = _make_matte(Color("34343a"), 19.0, 0.20)
	materials["old_asphalt"] = _make_matte(Color("45424c"), 16.0, 0.20)
	materials["old_plaster"] = _make_matte(Color("827985"), 11.0, 0.20)

func _grade_environment(room: Node3D) -> void:
	var world_environment := room.get_node_or_null("WorldEnvironment") as WorldEnvironment
	if world_environment == null:
		var imported_environments := room.find_children("*", "WorldEnvironment", true, false)
		if imported_environments.is_empty():
			return
		world_environment = imported_environments[0] as WorldEnvironment
	if world_environment == null or world_environment.environment == null:
		return
	# Duplicate an imported environment: no changes leak to other instances.
	var environment: Environment = world_environment.environment.duplicate()
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.adjustment_enabled = true
	environment.adjustment_contrast = 1.045
	environment.adjustment_saturation = 0.78
	environment.adjustment_brightness = 1.03
	world_environment.environment = environment

func _set_material(room: Node3D, path: String, material_key: String) -> void:
	var surface := room.get_node_or_null(path) as GeometryInstance3D
	if surface != null:
		surface.material_override = materials[material_key]

func _style_architecture(room: Node3D) -> void:
	if scene_style == "apartment":
		# The apartment already has a textured plaster asset and authored
		# wooden boards. Do not flatten those materials into a single color.
		return
	if scene_style == "station":
		_set_material(room, "Floor", "platform")
		_set_material(room, "LeftWall", "wall")
		_set_material(room, "RightWall", "wall")
		_set_material(room, "BackWall", "wall")
		_set_material(room, "EntranceWall", "wall")
		_set_material(room, "TrackBed", "ballast")
	else:
		_set_material(
			room, "Ground", "old_asphalt" if scene_style == "old_district" else "asphalt"
		)
		for name in ["BuildingLeft", "BuildingRight", "EndBlock"]:
			_set_material(
				room, name,
				"old_plaster" if scene_style == "old_district" else "plaster"
			)
	var dressing := room.get_node_or_null("Dressing")
	if dressing == null:
		return
	for child in dressing.find_children("*", "MeshInstance3D", true, false):
		var instance := child as MeshInstance3D
		var name := instance.name
		if scene_style == "station":
			if name.begins_with("PlatformSlab"):
				instance.material_override = materials["platform"]
		elif name.begins_with("Sidewalk"):
			instance.material_override = materials["paving"]
		elif name.begins_with("HouseFacade") or name.begins_with("GardenWall"):
			instance.material_override = materials[
				"old_plaster" if scene_style == "old_district" else "plaster"
			]

func _style_lights(room: Node3D) -> void:
	# Warm private lamps versus cold public lighting; enable shadows on a
	# limited set of key lights instead of every small decorative fixture.
	if scene_style == "apartment":
		var room_light := room.get_node_or_null("RoomLight") as OmniLight3D
		if room_light != null:
			room_light.shadow_enabled = true
		var window_light := room.get_node_or_null("IsoFillLight") as DirectionalLight3D
		if window_light != null:
			window_light.shadow_enabled = true
	elif scene_style == "station":
		var platform_light := room.get_node_or_null("Light1") as OmniLight3D
		if platform_light != null:
			platform_light.shadow_enabled = true
	elif scene_style == "old_district":
		var sun := room.get_node_or_null("OvercastSun") as DirectionalLight3D
		if sun != null:
			sun.light_color = Color("9a8b9f")
			sun.light_energy = 0.52
