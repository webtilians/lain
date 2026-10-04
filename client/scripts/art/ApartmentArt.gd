extends Node3D
## Deterministic visual dressing. No World Core writes or gameplay state.

var room: Node3D
var wood: StandardMaterial3D
var dark: StandardMaterial3D
var ivory: StandardMaterial3D
var metal: StandardMaterial3D
var cloth: StandardMaterial3D
var paper: StandardMaterial3D
var stride := 0.0
var screen: StandardMaterial3D

func material(color: Color, glow: float = 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.88
	if glow > 0.0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = glow
	return m

func box(label: String, at: Vector3, size: Vector3, mat: Material, solid: bool = false) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	mesh.name = label
	var shape := BoxMesh.new()
	shape.size = size
	mesh.mesh = shape
	mesh.material_override = mat
	mesh.position = at
	add_child(mesh)
	if solid:
		var body := StaticBody3D.new()
		mesh.add_child(body)
		var collision := CollisionShape3D.new()
		var bounds := BoxShape3D.new()
		bounds.size = size
		collision.shape = bounds
		body.add_child(collision)
	return mesh

func cylinder(at: Vector3, radius: float, height: float, mat: Material) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	var shape := CylinderMesh.new()
	shape.top_radius = radius
	shape.bottom_radius = radius
	shape.height = height
	shape.radial_segments = 12
	mesh.mesh = shape
	mesh.material_override = mat
	mesh.position = at
	add_child(mesh)
	return mesh

func cable(points: Array[Vector3], radius: float = 0.014) -> void:
	for i in range(points.size() - 1):
		var delta := points[i + 1] - points[i]
		var part := cylinder((points[i + 1] + points[i]) / 2.0, radius, delta.length(), dark)
		part.quaternion = Quaternion(Vector3.UP, delta.normalized())

func _ready() -> void:
	room = get_parent()
	wood = material(Color("514642"))
	dark = material(Color("191d24"))
	ivory = material(Color("b6b2a1"))
	metal = material(Color("545d60"))
	cloth = material(Color("777186"))
	paper = material(Color("bdb7ab"))
	screen = material(Color("598f7d"), 0.4)
	var plaster := material(Color("a5a0ab"))
	plaster.albedo_texture = preload("res://art/apartment/plaster.png")
	plaster.uv1_scale = Vector3(2, 1, 1)
	room.get_node("LeftWall").material = plaster
	room.get_node("FrontWall").material = plaster
	room.get_node("RightWall").material = wood
	room.get_node("BackWall").material = wood
	_floor()
	_architecture()
	_workstation()
	_sleeping_area()
	_shelves()
	_kitchen()
	_lighting()
	_avatar()
	_interface()

func _floor() -> void:
	# Each plank is tinted deterministically, so saves/reloads never change the room.
	for z in range(22):
		for x in range(5):
			var tone := 0.90 + float((x * 7 + z * 3) % 9) * 0.018
			var m := ShaderMaterial.new()
			m.shader = preload("res://art/apartment/wood.gdshader")
			m.set_shader_parameter("tint", Color("5e5145") * Color(tone, tone, tone, 1))
			box("Floorboard", Vector3(-3.2 + x * 1.6, 0.016, -3.81 + z * 0.36), Vector3(1.589, 0.025, 0.349), m)
	box("Foundation", Vector3(0, -0.28, 0), Vector3(8.15, 0.38, 8.15), dark)
	box("Rug", Vector3(0.3, 0.044, 0.2), Vector3(2.1, 0.02, 2.9), material(Color("514d59")))
	for z in [-1.13, 1.53]:
		box("RugBorder", Vector3(0.3, 0.057, z), Vector3(1.96, 0.009, 0.045), cloth)

func _architecture() -> void:
	room.get_node("ExitDoor/Mesh").visible = false
	box("SkirtingNorth", Vector3(0, 0.14, -3.85), Vector3(7.8, 0.25, 0.1), wood)
	box("SkirtingWest", Vector3(-3.85, 0.14, 0), Vector3(0.1, 0.25, 7.8), wood)
	box("WallCrown", Vector3(0, 2.95, -3.9), Vector3(8.1, 0.12, 0.2), dark)
	box("WallCrown", Vector3(-3.9, 2.95, 0), Vector3(0.2, 0.12, 8.1), dark)
	# Window sits on the rear wall facing into the cutaway room.
	box("WindowRecess", Vector3(-1.65, 1.98, -3.82), Vector3(2.8, 1.55, 0.11), dark)
	var glass := material(Color("9a92af"), 0.25)
	box("WindowGlass", Vector3(-1.65, 2.0, -3.74), Vector3(2.62, 1.36, 0.025), glass)
	for x in [-3.0, -1.65, -0.3]:
		box("WindowMullion", Vector3(x, 1.98, -3.67), Vector3(0.045, 1.55, 0.05), metal)
	for y in [1.25, 2.7]:
		box("WindowRail", Vector3(-1.65, y, -3.65), Vector3(2.8, 0.05, 0.12), metal)
	box("WindowSill", Vector3(-1.65, 1.2, -3.59), Vector3(3.0, 0.08, 0.36), ivory)
	# Silhouetted rooftops and wires behind glass, made as flat in-world shapes.
	var silhouette := material(Color("6b687f"))
	for i in range(6):
		box("DistantRoof", Vector3(-2.75 + i * 0.42, 1.47, -3.70), Vector3(0.39, 0.26 + (i % 3) * 0.12, 0.015), silhouette)
	cable([Vector3(-2.85, 2.4, -3.62), Vector3(-2.0, 2.21, -3.62), Vector3(-0.4, 2.15, -3.62)], 0.008)
	for side in [-3.18, -0.12]:
		for i in range(5):
			box("CurtainFold", Vector3(side + i * 0.048, 1.96, -3.47 + (i % 2) * 0.05), Vector3(0.055, 1.88, 0.11), cloth)
	# Dress the existing working exit, whose collider and script remain authoritative.
	box("DoorSurround", Vector3(2.65, 1.22, -3.70), Vector3(1.5, 2.44, 0.16), wood)
	box("DoorPanel", Vector3(2.65, 1.14, -3.59), Vector3(1.24, 2.21, 0.09), material(Color("45454b")))
	box("DoorInset", Vector3(2.65, 1.35, -3.535), Vector3(1.02, 1.45, 0.015), material(Color("505056")))
	box("DoorHandle", Vector3(3.08, 1.0, -3.48), Vector3(0.2, 0.04, 0.07), ivory)
	box("EntryMat", Vector3(2.65, 0.06, -2.98), Vector3(1.35, 0.06, 0.78), material(Color("777365")))
	box("DoorLintelLight", Vector3(2.65, 2.54, -3.47), Vector3(0.62, 0.07, 0.12), material(Color("d3c2a1"), 1.1))

func _workstation() -> void:
	room.get_node("Desk").visible = false
	room.get_node("Monitor/Mesh").visible = false
	box("DeskTop", Vector3(-1.65, 0.82, -2.78), Vector3(2.55, 0.12, 1.12), wood)
	for x in [-2.72, -0.6]:
		for z in [-3.19, -2.38]:
			box("DeskLeg", Vector3(x, 0.4, z), Vector3(0.07, 0.8, 0.07), metal)
	box("CRTBody", Vector3(-1.7, 1.21, -2.98), Vector3(0.88, 0.67, 0.63), ivory)
	box("CRTBezel", Vector3(-1.7, 1.23, -2.64), Vector3(0.76, 0.53, 0.055), dark)
	box("CRTScreen", Vector3(-1.7, 1.24, -2.604), Vector3(0.66, 0.43, 0.025), screen)
	box("CRTStand", Vector3(-1.7, 0.9, -2.93), Vector3(0.49, 0.13, 0.45), ivory)
	var dim := material(Color("385f56"), 0.35)
	for i in range(7):
		box("TerminalLine", Vector3(-1.87 + (i % 2) * 0.03, 1.39 - i * 0.047, -2.586), Vector3(0.25 + (i % 3) * 0.08, 0.012, 0.004), dim)
	box("Keyboard", Vector3(-1.62, 0.911, -2.35), Vector3(0.69, 0.054, 0.21), ivory)
	for row in range(3):
		for key in range(11):
			box("Key", Vector3(-1.91 + key * 0.055, 0.944, -2.415 + row * 0.052), Vector3(0.043, 0.013, 0.04), paper)
	box("Mouse", Vector3(-1.03, 0.92, -2.36), Vector3(0.1, 0.05, 0.16), ivory)
	for i in range(3):
		var x := -3.16 + i * 0.34
		box("ComputerTower", Vector3(x, 0.36, -3.06), Vector3(0.29, 0.7, 0.65), ivory if i != 1 else metal, true)
		for slot in range(4):
			box("DriveSlot", Vector3(x, 0.51 - slot * 0.08, -2.726), Vector3(0.22, 0.012, 0.01), dark)
		box("ActivityLED", Vector3(x + 0.085, 0.17, -2.718), Vector3(0.025, 0.025, 0.008), screen)
	box("ChairSeat", Vector3(-1.75, 0.48, -1.78), Vector3(0.58, 0.1, 0.57), dark, true)
	box("ChairBack", Vector3(-1.75, 0.78, -1.49), Vector3(0.58, 0.6, 0.08), wood)
	for x in [-1.97, -1.53]:
		for z in [-2.0, -1.57]:
			box("ChairLeg", Vector3(x, 0.24, z), Vector3(0.04, 0.48, 0.04), metal)
	for i in range(4):
		cable([Vector3(-2.8 + i * 0.08, 0.07, -2.75), Vector3(-3.25, 0.055, -1.9 + i * 0.1), Vector3(-3.35, 0.055, -0.9), Vector3(-3.64, 0.055, -0.55)])
	# Loose notebook and small mug on the desk.
	box("Notebook", Vector3(-0.68, 0.895, -2.74), Vector3(0.3, 0.025, 0.38), paper)
	cylinder(Vector3(-2.65, 0.98, -2.45), 0.067, 0.18, cloth)

func _sleeping_area() -> void:
	box("BedBase", Vector3(-2.4, 0.13, 1.6), Vector3(1.65, 0.2, 2.48), wood, true)
	box("Futon", Vector3(-2.4, 0.28, 1.6), Vector3(1.57, 0.22, 2.38), paper)
	box("Duvet", Vector3(-2.4, 0.41, 1.88), Vector3(1.62, 0.13, 1.87), cloth)
	for i in range(7):
		var crease := box("FabricFold", Vector3(-3.05 + i * 0.22, 0.48, 1.88), Vector3(0.045, 0.015, 1.82), material(Color("6e687f")))
		crease.rotation.y = 0.025 * (i - 3)
	box("Pillow", Vector3(-2.4, 0.46, 0.72), Vector3(0.91, 0.19, 0.47), material(Color("b7afbd")))
	box("LowTable", Vector3(0.1, 0.36, 1.48), Vector3(1.22, 0.09, 0.7), wood, true)
	for x in [-0.4, 0.6]:
		for z in [1.23, 1.73]:
			box("TableLeg", Vector3(x, 0.17, z), Vector3(0.08, 0.34, 0.08), dark)
	box("BookOnTable", Vector3(-0.15, 0.435, 1.47), Vector3(0.36, 0.055, 0.26), paper)
	cylinder(Vector3(0.45, 0.49, 1.5), 0.07, 0.14, ivory)

func _shelves() -> void:
	box("ShelfBack", Vector3(-3.75, 1.03, 2.3), Vector3(0.1, 2.06, 1.8), wood)
	for z in [1.38, 3.22]:
		box("ShelfSide", Vector3(-3.53, 1.03, z), Vector3(0.54, 2.06, 0.075), wood, true)
	for level in range(5):
		var y := 0.1 + level * 0.45
		box("Shelf", Vector3(-3.5, y, 2.3), Vector3(0.6, 0.06, 1.85), wood)
		if level < 4:
			for book in range(13):
				var h := 0.22 + float((book * 3 + level) % 5) * 0.025
				var color := Color("737078") if book % 3 else Color("9b9386")
				box("Book", Vector3(-3.42, y + 0.04 + h / 2, 1.52 + book * 0.12), Vector3(0.33, h, 0.085), material(color))
	box("Pinboard", Vector3(-3.82, 1.97, -0.2), Vector3(0.07, 0.85, 0.74), wood)
	for i in range(3):
		box("Note", Vector3(-3.77, 1.75 + i * 0.17, -0.36 + i * 0.14), Vector3(0.01, 0.27, 0.23), paper)

func _kitchen() -> void:
	box("KitchenCabinet", Vector3(0.57, 0.47, -3.15), Vector3(1.48, 0.94, 0.88), material(Color("77777c")), true)
	box("Counter", Vector3(0.57, 0.98, -3.15), Vector3(1.55, 0.075, 0.94), metal)
	box("SinkRim", Vector3(0.33, 1.03, -3.15), Vector3(0.63, 0.03, 0.59), ivory)
	box("SinkBasin", Vector3(0.33, 1.047, -3.15), Vector3(0.51, 0.01, 0.47), dark)
	cable([Vector3(0.3, 1.03, -3.46), Vector3(0.3, 1.32, -3.46), Vector3(0.3, 1.32, -3.25)], 0.025)
	cylinder(Vector3(1.02, 1.04, -3.16), 0.18, 0.025, dark)
	for x in [0.08, 0.82]:
		box("CabinetDoor", Vector3(x, 0.5, -2.699), Vector3(0.68, 0.82, 0.022), ivory)
		box("CabinetHandle", Vector3(x + 0.22, 0.68, -2.67), Vector3(0.03, 0.15, 0.025), metal)
	box("Splashback", Vector3(0.65, 1.43, -3.79), Vector3(1.67, 0.75, 0.06), paper)
	for i in range(5):
		box("TileGrout", Vector3(-0.1 + i * 0.37, 1.43, -3.75), Vector3(0.012, 0.75, 0.012), metal)

func _lighting() -> void:
	var environment := WorldEnvironment.new()
	var settings := Environment.new()
	settings.background_mode = Environment.BG_COLOR
	settings.background_color = Color("171b25")
	settings.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	settings.ambient_light_color = Color("9b93b6")
	settings.ambient_light_energy = 0.30
	settings.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.environment = settings
	add_child(environment)
	var fill: DirectionalLight3D = room.get_node("IsoFillLight")
	fill.rotation_degrees = Vector3(-48, -28, 0)
	fill.light_color = Color("d3cbd7")
	fill.light_energy = 0.48
	fill.shadow_enabled = true
	fill.directional_shadow_max_distance = 35
	var lamp: OmniLight3D = room.get_node("RoomLight")
	lamp.position = Vector3(2.5, 2.1, -2.8)
	lamp.light_color = Color("dbc49f")
	lamp.light_energy = 0.7
	lamp.omni_range = 4.4
	var glow: OmniLight3D = room.get_node("MonitorGlow")
	glow.light_color = Color("89c7be")
	glow.light_energy = 0.65
	glow.omni_range = 2.2
	var window_light := OmniLight3D.new()
	window_light.position = Vector3(-1.65, 2.25, -3.15)
	window_light.light_color = Color("b9adc9")
	window_light.light_energy = 0.65
	window_light.omni_range = 5.8
	add_child(window_light)

func rounded_piece(at: Vector3, size: Vector3, mat: Material) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	var shape := SphereMesh.new()
	shape.radius = 0.5
	shape.height = 1.0
	shape.radial_segments = 16
	shape.rings = 8
	mesh.mesh = shape
	mesh.material_override = mat
	mesh.position = at
	mesh.scale = size
	add_child(mesh)
	return mesh

func _avatar() -> void:
	var player: Node3D = room.get_node("Player")
	player.get_node("CharacterMesh").visible = false
	var rig := Node3D.new()
	rig.name = "Silhouette"
	player.add_child(rig)
	var skin := material(Color("b7a59d"))
	var pieces: Array[MeshInstance3D] = []
	var coat := cylinder(Vector3(0, -0.04, 0), 0.25, 0.7, dark)
	coat.mesh.top_radius = 0.19
	coat.scale.z = 0.68
	pieces.append(coat)
	pieces.append(rounded_piece(Vector3(0, 0.43, 0.02), Vector3(0.3, 0.37, 0.29), skin))
	pieces.append(rounded_piece(Vector3(0, 0.50, -0.045), Vector3(0.33, 0.32, 0.3), wood))
	pieces.append(rounded_piece(Vector3(0, 0.32, -0.105), Vector3(0.29, 0.23, 0.15), wood))
	for side in [-1, 1]:
		pieces.append(cylinder(Vector3(side * 0.25, -0.05, 0), 0.07, 0.54, dark))
		pieces.append(rounded_piece(Vector3(side * 0.25, -0.35, 0), Vector3(0.1, 0.13, 0.1), skin))
		var leg := cylinder(Vector3(side * 0.115, -0.58, 0), 0.066, 0.44, material(Color("403e48")))
		leg.name = "LeftLeg" if side == -1 else "RightLeg"
		pieces.append(leg)
		pieces.append(rounded_piece(Vector3(side * 0.115, -0.82, 0.06), Vector3(0.16, 0.13, 0.3), dark))
	for piece in pieces:
		piece.reparent(rig, false)

func _interface() -> void:
	room.get_node("HUD/Crosshair").hide()
	var info: MarginContainer = room.get_node("HUD/Info")
	info.offset_right = 275
	info.offset_bottom = 130
	var panel: PanelContainer = room.get_node("HUD/Info/Panel")
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.06, 0.07, 0.09, 0.55)
	style.border_color = Color("74707c")
	style.border_width_left = 2
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 8
	style.content_margin_bottom = 8
	panel.add_theme_stylebox_override("panel", style)
	panel.add_theme_font_size_override("font_size", 13)
	room.get_node("HUD/Info/Panel/VBox/Knowledge").hide()
	var crt: ColorRect = room.get_node("RetroOverlay/CRT")
	crt.material = crt.material.duplicate()
	crt.material.set_shader_parameter("scanline_strength", 0.025)
	crt.material.set_shader_parameter("noise_strength", 0.007)
	crt.material.set_shader_parameter("color_levels", 128.0)

func _process(delta: float) -> void:
	var player: CharacterBody3D = room.get_node("Player")
	var rig: Node3D = player.get_node("Silhouette")
	var motion := Vector2(player.velocity.x, player.velocity.z)
	if motion.length() > 0.1:
		stride += delta * 9.0
		rig.rotation.y = lerp_angle(rig.rotation.y, atan2(motion.x, motion.y), minf(delta * 12.0, 1.0))
		var swing := sin(stride) * 0.23
		rig.get_node("LeftLeg").rotation.x = swing
		rig.get_node("RightLeg").rotation.x = -swing
	else:
		rig.get_node("LeftLeg").rotation.x = 0
		rig.get_node("RightLeg").rotation.x = 0
