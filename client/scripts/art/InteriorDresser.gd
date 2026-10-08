extends RefCounted
## Visual 0.22 · interiors. Each kind of place gets its own floor and walls, real
## light fixtures (fluorescent tubes, paper lanterns, pendants, neon) and the
## clutter that makes it believable. Decoration only: everything hangs from one
## InteriorDressing node, has no collision and is invisible to World Core.
const FLOOR_SHADER := preload("res://shaders/interior_floor.gdshader")

const STYLES := {
	"VIDEO_CLUB": {"floor": "tiles", "a": Color("9a9890"), "b": Color("7d7b75"), "tile": .42,
		"wall": Color("d9d3c5"), "band": Color("7d2626"), "light": "tubes", "tint": Color("e6efff"), "power": 2.4, "stock": "vhs"},
	"GROCERY": {"floor": "tiles", "a": Color("dedad0"), "b": Color("bdb8aa"), "tile": .45,
		"wall": Color("e8e4d8"), "band": Color("2d6b5b"), "light": "tubes", "tint": Color("f2f6ff"), "power": 2.8, "stock": "products"},
	"BOOKSHOP": {"floor": "wood", "wood": Color("b59670"),
		"wall": Color("cfc2a3"), "band": Color("4f3c2a"), "light": "tubes", "tint": Color("ffe2b8"), "power": 2.0, "stock": "books"},
	"IZAKAYA": {"floor": "wood", "wood": Color("8d6a48"),
		"wall": Color("cdb68e"), "band": Color("5b3521"), "light": "lanterns", "tint": Color("ffb36e"), "power": 2.2, "stock": "bottles"},
	"ARCADE": {"floor": "carpet", "a": Color("1b1830"), "b": Color("6b2f8f"), "tile": .9,
		"wall": Color("3a3452"), "band": Color("1d1a2b"), "light": "neon", "tint": Color("c7b6ff"), "power": 1.7, "stock": ""},
	"CAFE": {"floor": "wood", "wood": Color("a17a52"),
		"wall": Color("bea47e"), "band": Color("3e2a1d"), "light": "pendants", "tint": Color("ffc58c"), "power": 2.0, "stock": ""},
	"SCHOOL": {"floor": "tiles", "a": Color("8e9a8b"), "b": Color("7b8778"), "tile": .5,
		"wall": Color("dadccf"), "band": Color("6d8877"), "light": "tubes", "tint": Color("eef4ff"), "power": 2.4, "stock": ""},
	"SCHOOL_LAB": {"floor": "tiles", "a": Color("bbbdb6"), "b": Color("9ea29b"), "tile": .5,
		"wall": Color("dcdcd2"), "band": Color("4e6a7f"), "light": "tubes", "tint": Color("eef4ff"), "power": 2.4, "stock": ""},
	"NIGHTCLUB": {"floor": "tiles", "a": Color("141219"), "b": Color("2a2337"), "tile": 1.0,
		"wall": Color("2b2537"), "band": Color("16131d"), "light": "club", "tint": Color("ff4fb8"), "power": 2.2, "stock": ""},
	"STATION": {"floor": "", "light": "tubes", "tint": Color("e9f1ff"), "power": 2.6, "stock": ""},
	"APARTMENT": {"floor": "", "light": "home", "tint": Color("ffcf9a"), "power": 2.8, "stock": ""},
}
const PALETTES := {
	"vhs": [Color("1b1b1f"), Color("e9e4d6"), Color("b5262c"), Color("23458f"), Color("e0b322"), Color("1f7f80"), Color("d9692a")],
	"products": [Color("d23a2f"), Color("f1c232"), Color("3f8f3a"), Color("f4f1e8"), Color("2f5fa8"), Color("e9822f")],
	"books": [Color("6e2a2a"), Color("2c3e63"), Color("3d5a3a"), Color("b08a3c"), Color("d8ccb0"), Color("5c5a58")],
	"bottles": [Color(.55, .32, .10, .78), Color(.18, .40, .20, .78), Color(.85, .85, .80, .55), Color(.35, .12, .10, .8)],
}

var materials
var cache: Dictionary = {}
var fixtures: Array[Light3D] = []
var probe: ReflectionProbe

func _init(shared_materials) -> void:
	materials = shared_materials

func dress(scene: Node3D, location: String) -> void:
	fixtures.clear()
	probe = null
	if not STYLES.has(location) or scene.has_node("InteriorDressing"):
		return
	var style: Dictionary = STYLES[location]
	var root := Node3D.new()
	root.name = "InteriorDressing"
	scene.add_child(root)
	var bounds := room_bounds(scene)
	var top := _ceiling(scene)
	_surfaces(scene, style, location)
	_lights(root, style, bounds, top, location)
	_restock(scene, style)
	_dress(root, location, style)
	probe = ReflectionProbe.new()
	probe.name = "InteriorProbe"
	probe.interior = true
	probe.update_mode = ReflectionProbe.UPDATE_ONCE
	probe.position = Vector3(bounds.get_center().x, top * .5, bounds.get_center().z)
	probe.size = Vector3(bounds.size.x, top + .5, bounds.size.z)
	probe.box_projection = true
	root.add_child(probe)

func apply_quality(level: int) -> void:
	# Light: no shadows; balanced: the two main fixtures; high: four and reflections.
	var shadowed: int = [0, 2, 4][clampi(level, 0, 2)]
	for index in range(fixtures.size()):
		if is_instance_valid(fixtures[index]):
			fixtures[index].shadow_enabled = index < shadowed
	if is_instance_valid(probe):
		probe.visible = level == 2

# ---------------------------------------------------------------- room shape

static func room_bounds(scene: Node3D) -> AABB:
	var floor := scene.get_node_or_null("Floor")
	if floor is CSGBox3D:
		return AABB(floor.global_position - floor.size * .5, floor.size)
	if floor != null:
		for child in floor.get_children():
			if child is MeshInstance3D:
				return child.global_transform * child.get_aabb()
	return AABB(Vector3(-7, -.4, -8.3), Vector3(14, .4, 16.7))

func _ceiling(scene: Node3D) -> float:
	var top := 0.0
	for child in scene.get_children():
		if not String(child.name).ends_with("Wall"):
			continue
		if child is CSGBox3D:
			top = maxf(top, child.global_position.y + child.size.y * .5)
		else:
			for part in child.get_children():
				if part is MeshInstance3D:
					top = maxf(top, (part.global_transform * part.get_aabb()).end.y)
	return top if top > 2.0 else 3.4

# ---------------------------------------------------------------- materials

func _material(color: Color, emission: float = 0.0, rough: float = .7) -> StandardMaterial3D:
	var key := str(color) + str(emission) + str(rough)
	if cache.has(key):
		return cache[key]
	var material := StandardMaterial3D.new()
	material.resource_name = "PBR10_dress"
	material.albedo_color = color
	material.roughness = rough
	if color.a < 1.0:
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.metallic_specular = .8
		material.roughness = .12
	if emission > 0.0:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = emission
	cache[key] = material
	return material

func _surfaces(scene: Node3D, style: Dictionary, location: String) -> void:
	var floor_material: Material = null
	match str(style.get("floor", "")):
		"tiles", "carpet":
			var shader := ShaderMaterial.new()
			shader.resource_name = "PBR10_floor_" + location
			shader.shader = FLOOR_SHADER
			shader.set_shader_parameter("pattern", 1 if style.floor == "carpet" else 0)
			shader.set_shader_parameter("color_a", style.a)
			shader.set_shader_parameter("color_b", style.b)
			shader.set_shader_parameter("grout", Color(style.b).darkened(.35))
			shader.set_shader_parameter("tile", style.tile)
			floor_material = shader
		"wood":
			floor_material = materials.pbr("wood_floor", style.wood, .44, .5, .8)
	var floor := scene.get_node_or_null("Floor")
	if floor_material != null and floor != null:
		_paint(floor, floor_material)
		for child in scene.get_children():
			if String(child.name).begins_with("FloorSeam") or String(child.name).begins_with("Floorboard"):
				child.visible = false
	if style.has("wall"):
		var plaster: Material = materials.pbr("plastered_wall_02", style.wall, .45, .35, .95)
		for child in scene.get_children():
			if String(child.name).ends_with("Wall"):
				_paint(child, plaster)

func _paint(node: Node, material: Material) -> void:
	if node is CSGShape3D:
		node.material = material
		return
	if node is MeshInstance3D:
		node.material_override = material
	for child in node.get_children():
		if child is MeshInstance3D:
			child.material_override = material

# ---------------------------------------------------------------- light

func _box(root: Node3D, label: String, at: Vector3, size: Vector3, material: Material) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	var instance := MeshInstance3D.new()
	instance.name = "Dress_" + label
	instance.mesh = mesh
	instance.position = at
	instance.material_override = material
	instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if material is StandardMaterial3D and material.emission_enabled else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	root.add_child(instance)
	return instance

func _cylinder(root: Node3D, label: String, at: Vector3, radius: float, height: float, material: Material) -> MeshInstance3D:
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = 16
	var instance := MeshInstance3D.new()
	instance.name = "Dress_" + label
	instance.mesh = mesh
	instance.position = at
	instance.material_override = material
	root.add_child(instance)
	return instance

func _spot(root: Node3D, at: Vector3, color: Color, power: float, reach: float) -> SpotLight3D:
	var lamp := SpotLight3D.new()
	lamp.name = "Dress_Light"
	lamp.position = at
	lamp.rotation_degrees = Vector3(-90, 0, 0)
	lamp.light_color = color
	lamp.light_energy = power
	lamp.spot_range = reach
	lamp.spot_angle = 68
	lamp.spot_angle_attenuation = .7
	lamp.light_size = .3
	lamp.shadow_bias = .05
	lamp.shadow_normal_bias = .8
	root.add_child(lamp)
	fixtures.append(lamp)
	return lamp

func _omni(root: Node3D, at: Vector3, color: Color, power: float, reach: float, main: bool = false) -> OmniLight3D:
	var lamp := OmniLight3D.new()
	lamp.name = "Dress_Glow"
	lamp.position = at
	lamp.light_color = color
	lamp.light_energy = power
	lamp.omni_range = reach
	lamp.omni_attenuation = 1.4
	lamp.shadow_bias = .06
	root.add_child(lamp)
	if main:
		fixtures.append(lamp)
	return lamp

func _grid(bounds: AABB, step_x: float, step_z: float) -> Array:
	var cols := maxi(1, roundi(bounds.size.x / step_x))
	var rows := maxi(1, roundi(bounds.size.z / step_z))
	var points := []
	for col in range(cols):
		for row in range(rows):
			points.append(Vector2(bounds.position.x + bounds.size.x * (col + .5) / cols,
				bounds.position.z + bounds.size.z * (row + .5) / rows))
	return points

func _lights(root: Node3D, style: Dictionary, bounds: AABB, top: float, location: String) -> void:
	var tint: Color = style.tint
	var power: float = style.power
	var height := minf(top - .25, 3.4)
	match str(style.light):
		"tubes":
			# The ceiling is cut away for the isometric camera: the tubes hang out
			# of view and only their light reaches the room.
			for point in _grid(bounds, 6.5, 5.5):
				_spot(root, Vector3(point.x, height - .05, point.y), tint, power, height + 2.5)
		"lanterns":
			var paper := _material(tint, 3.2, .9)
			var rim := _material(Color("2a1a12"))
			for point in [Vector2(-4.3, -3.0), Vector2(-4.3, 1.3), Vector2(-4.3, 4.5), Vector2(3.2, -4.6), Vector2(5.4, -4.6), Vector2(.6, 1.0)]:
				_cylinder(root, "Lantern", Vector3(point.x, 2.45, point.y), .26, .62, paper)
				_cylinder(root, "LanternRim", Vector3(point.x, 2.79, point.y), .2, .05, rim)
				_box(root, "LanternCord", Vector3(point.x, 3.1, point.y), Vector3(.015, .6, .015), rim)
				_omni(root, Vector3(point.x, 2.35, point.y), tint, power, 5.5, fixtures.size() < 4)
		"pendants":
			var bulb := _material(tint, 6.0)
			var shade := _material(Color("2d3b33"), 0.0, .45)
			for point in [Vector2(-4.3, -3.0), Vector2(-4.3, 1.3), Vector2(-4.3, 4.5), Vector2(4.3, -5.0), Vector2(2.5, 2.5)]:
				_box(root, "PendantCord", Vector3(point.x, 3.05, point.y), Vector3(.015, 1.0, .015), shade)
				_cylinder(root, "PendantShade", Vector3(point.x, 2.5, point.y), .3, .2, shade)
				_cylinder(root, "PendantBulb", Vector3(point.x, 2.36, point.y), .09, .1, bulb)
				_spot(root, Vector3(point.x, 2.34, point.y), tint, power, 4.2)
		"neon":
			var colors := [Color("ff3c9a"), Color("39e3ff"), Color("ffe14a"), Color("6dff8a")]
			_box(root, "NeonBack", Vector3(bounds.get_center().x, 3.05, -8.12), Vector3(bounds.size.x - 1.0, .06, .06), _material(colors[0], 6.0))
			_box(root, "NeonWest", Vector3(bounds.position.x + .2, 3.05, bounds.get_center().z), Vector3(.06, .06, bounds.size.z - 1.0), _material(colors[1], 6.0))
			for point in _grid(bounds, 7.0, 6.0):
				_spot(root, Vector3(point.x, height, point.y), tint, power, height + 2.0)
		"club":
			var colors := [Color("ff4fb8"), Color("39c6ff"), Color("9b5cff")]
			var index := 0
			for point in _grid(bounds, 5.0, 5.0):
				var lamp := _spot(root, Vector3(point.x, height, point.y), colors[index % colors.size()], power, height + 2.5)
				lamp.spot_angle = 38
				index += 1
		"home":
			# A ceiling lamp and a low warm fill by the bed: a lived-in room at night.
			_omni(root, Vector3(bounds.get_center().x, top - .4, bounds.get_center().z), tint, power, 8.0, true)
			_omni(root, Vector3(bounds.get_center().x - 2.0, 1.2, bounds.get_center().z + 1.0), Color("ffb978"), power * .45, 4.5)

# ---------------------------------------------------------------- stock and clutter

func _restock(scene: Node3D, style: Dictionary) -> void:
	var kind := str(style.get("stock", ""))
	for node in scene.find_children("*", "MeshInstance3D", true, false):
		var label := String(node.name)
		if kind != "" and PALETTES.has(kind) and label.contains("Stock"):
			var palette: Array = PALETTES[kind]
			var seed := absi(hash(Vector3i(node.global_position * 100.0)))
			node.material_override = _material(palette[seed % palette.size()], 0.0, .55)
			if kind == "vhs":
				node.scale.y = .9 + float(seed % 5) * .04
		elif label.contains("Poster") and not label.contains("Frame") and not label.contains("Print"):
			var posters := [Color("b8392f"), Color("2a4f8f"), Color("d9a02a"), Color("2d6f5a"), Color("7a3c8f")]
			node.material_override = _material(posters[absi(hash(Vector3i(node.global_position * 10.0))) % posters.size()], .25, .6)
		elif label.contains("ArcadeScreen") or label.contains("CRTScreen"):
			var screens := [Color("39e3ff"), Color("ff3c9a"), Color("ffe14a"), Color("6dff8a"), Color("8f7bff")]
			var color: Color = screens[absi(hash(Vector3i(node.global_position * 10.0))) % screens.size()]
			node.material_override = _material(color, 2.6, .3)
			if label.contains("ArcadeScreen"):
				var glow := OmniLight3D.new()
				glow.name = "Dress_ScreenGlow"
				glow.light_color = color
				glow.light_energy = .9
				glow.omni_range = 2.6
				glow.position = Vector3(0, 0, .5)
				node.add_child(glow)
		elif label.contains("FridgeGlass"):
			node.material_override = _material(Color("bfe6ff"), 1.4, .2)
		elif label.contains("PaperLantern"):
			node.visible = false   # replaced by lit lanterns

func _plant(root: Node3D, at: Vector3) -> void:
	_cylinder(root, "PlantPot", at + Vector3(0, .22, 0), .2, .44, _material(Color("6b4a35")))
	var leaves := SphereMesh.new()
	leaves.radius = .38
	leaves.height = .7
	var crown := MeshInstance3D.new()
	crown.name = "Dress_Plant"
	crown.mesh = leaves
	crown.position = at + Vector3(0, .82, 0)
	crown.material_override = _material(Color("3f6b3a"), 0.0, .9)
	root.add_child(crown)

func _band(root: Node3D, scene: Node3D, style: Dictionary) -> void:
	# A painted dado on the two tall walls, with a lighter rail on top.
	if not scene.has_node("WestWall") or not scene.has_node("BackWall"):
		return
	var paint := _material(style.band, 0.0, .6)
	var rail := _material(Color(style.band).lightened(.35), 0.0, .5)
	_box(root, "DadoWest", Vector3(-6.965, .55, 0), Vector3(.02, 1.1, 16.6), paint)
	_box(root, "DadoBack", Vector3(0, .55, -8.165), Vector3(13.8, 1.1, .02), paint)
	_box(root, "RailWest", Vector3(-6.955, 1.12, 0), Vector3(.04, .05, 16.6), rail)
	_box(root, "RailBack", Vector3(0, 1.12, -8.155), Vector3(13.8, .05, .04), rail)

func _dress(root: Node3D, location: String, style: Dictionary) -> void:
	var scene := root.get_parent() as Node3D
	if style.has("band"):
		_band(root, scene, style)
	match location:
		"VIDEO_CLUB":
			_box(root, "ReturnBox", Vector3(-1.7, .45, 7.25), Vector3(.62, .9, .5), _material(Color("23345a")))
			_box(root, "ReturnSlot", Vector3(-1.7, .78, 7.0), Vector3(.4, .05, .02), _material(Color("0d0f14")))
			for i in range(4):
				_box(root, "NewRelease", Vector3(2.0 + i * 1.05, 2.15, -8.13), Vector3(.8, 1.15, .03),
					_material(PALETTES.vhs[(i * 3 + 2) % PALETTES.vhs.size()], .35, .6))
			_plant(root, Vector3(-6.3, 0, 7.4))
		"GROCERY":
			for i in range(6):
				var color: Color = [Color("e9822f"), Color("4f9a3a"), Color("d23a2f")][i % 3]
				_box(root, "Crate", Vector3(5.3 + (i % 2) * .7, .2, 3.6 + floorf(i / 2.0) * .62), Vector3(.62, .4, .52), _material(Color("8a6a45")))
				_box(root, "Produce", Vector3(5.3 + (i % 2) * .7, .43, 3.6 + floorf(i / 2.0) * .62), Vector3(.54, .08, .44), _material(color, 0.0, .8))
			_plant(root, Vector3(-6.3, 0, 7.4))
		"BOOKSHOP":
			for i in range(5):
				_box(root, "BookPile", Vector3(-1.8 + i * .5, .1 + (i % 3) * .06, -5.2), Vector3(.34, .2 + (i % 3) * .12, .26),
					_material(PALETTES.books[i % PALETTES.books.size()]))
			_plant(root, Vector3(-6.3, 0, 7.4))
			_plant(root, Vector3(6.3, 0, 7.4))
		"IZAKAYA":
			var indigo := _material(Color("27304f"), 0.0, .9)
			for x in [-.55, 0.0, .55]:
				_box(root, "Noren", Vector3(x, 2.05, 7.92), Vector3(.5, .7, .02), indigo)
			for x in [3.2, 4.2, 5.2]:
				_cylinder(root, "BarStool", Vector3(x, .38, -5.2), .19, .76, _material(Color("3b2418")))
			_plant(root, Vector3(-6.3, 0, 7.4))
		"CAFE":
			for i in range(8):
				_box(root, "Record", Vector3(5.85, .5 + floorf(i / 4.0) * .4, 2.0 + (i % 4) * .34), Vector3(.32, .32, .02),
					_material(PALETTES.vhs[i % PALETTES.vhs.size()], 0.0, .5))
			_plant(root, Vector3(-6.3, 0, 7.4))
			_plant(root, Vector3(6.3, 0, -7.4))
		"ARCADE":
			_box(root, "PrizeMachine", Vector3(-1.5, 1.0, -7.4), Vector3(1.2, 2.0, 1.0), _material(Color("d33b7a")))
			_box(root, "PrizeGlass", Vector3(-1.5, 1.35, -6.88), Vector3(1.0, 1.0, .02), _material(Color(.7, .9, 1.0, .35)))
			_box(root, "Changer", Vector3(1.4, .8, -7.6), Vector3(.7, 1.6, .5), _material(Color("e0c040"), .2))
		"SCHOOL", "SCHOOL_LAB":
			_plant(root, Vector3(6.3, 0, -7.4))
