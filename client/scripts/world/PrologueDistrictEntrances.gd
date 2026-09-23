extends Node3D
## A district with two separate quarters and room for later missions.
## This is presentation only; all routes use existing World Core MOVE.
## Approximate playable bounds: x -11.5..11.5, z -68..9.

const EXIT_SCRIPT = preload("res://scripts/world/ExitDoor.gd")
const SCHOOL_ENTRANCE := Vector3(-11.18, 1.10, -20.0)
const NIGHTCLUB_ENTRANCE := Vector3(11.18, 1.10, -53.0)


func _ready() -> void:
	_make_streets()
	_make_buildings()
	_make_places()
	_make_entrance(
		"SCHOOL", SCHOOL_ENTRANCE,
		"ESCUELA MUNICIPAL", Color(0.67, 0.76, 0.82),
	)
	_make_entrance(
		"NIGHTCLUB", NIGHTCLUB_ENTRANCE,
		"AZUL // SOTANO", Color(0.73, 0.24, 0.73),
	)


func _material(shade: Color, lit: bool = false) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = shade
	mat.roughness = 0.92
	if lit:
		mat.emission_enabled = true
		mat.emission = shade
		mat.emission_energy_multiplier = 1.3
	return mat


func _block(name_text: String, pos: Vector3, size: Vector3,
		shade: Color, solid: bool = true) -> Node3D:
	var holder: Node3D
	if solid:
		holder = StaticBody3D.new()
	else:
		holder = Node3D.new()
	holder.name = name_text
	holder.position = pos
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = size
	mesh.mesh = box
	mesh.material_override = _material(shade)
	holder.add_child(mesh)
	if solid:
		var collider := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = size
		collider.shape = shape
		holder.add_child(collider)
	add_child(holder)
	return holder


func _sign(text_value: String, pos: Vector3,
		shade: Color, font_size: int = 32) -> void:
	var sign := Label3D.new()
	sign.name = "Sign_" + str(get_child_count())
	sign.text = text_value
	sign.position = pos
	sign.font_size = font_size
	sign.pixel_size = 0.005
	sign.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sign.modulate = shade
	sign.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(sign)


func _light(name_text: String, pos: Vector3, shade: Color) -> void:
	var light := OmniLight3D.new()
	light.name = name_text
	light.position = pos
	light.light_color = shade
	light.light_energy = 0.55
	light.omni_range = 10.0
	add_child(light)


func _make_streets() -> void:
	# Through-road, two broad pavements and a small mid-block square.
	for side in [-1.0, 1.0]:
		var side_id := "W" if side < 0.0 else "E"
		_block("Pavement_" + side_id, Vector3(side * 8.1, 0.015, -29.0),
			Vector3(7.1, 0.04, 77.4), Color(0.42, 0.43, 0.45), false)
		_block("Kerb_" + side_id, Vector3(side * 4.5, 0.07, -29.0),
			Vector3(0.16, 0.09, 77.4), Color(0.55, 0.55, 0.54), false)
		for stripe in range(12):
			var z := -64.0 + float(stripe) * 5.2
			_block("PavingJoin_" + side_id + str(stripe),
				Vector3(side * 8.1, 0.045, z), Vector3(7.0, 0.012, 0.05),
				Color(0.32, 0.33, 0.35), false)
	# A planted traffic island marks the transition from school to nightlife.
	_block("MidtownSquare", Vector3(-0.5, 0.012, -36.2),
		Vector3(7.8, 0.035, 4.8), Color(0.36, 0.38, 0.40), false)
	for stripe in range(8):
		_block("Crossing_" + str(stripe),
			Vector3(-3.1 + float(stripe) * 0.9, 0.043, -34.8),
			Vector3(0.50, 0.011, 1.4), Color(0.62, 0.63, 0.64), false)


func _building(name_text: String, side: float, z: float, depth: float,
		height: float, shade: Color) -> void:
	var x := side * 13.75
	_block(name_text, Vector3(x, height / 2.0, z),
		Vector3(4.35, height, depth), shade)
	# The front is on the outer edge of a real pavement, not in the road.
	# Individual windows are deliberately noninteractive until future quests.
	for floor_number in range(2):
		for window_number in range(int(depth / 3.4)):
			var wy := 1.95 + float(floor_number) * 1.7
			if wy + 0.6 >= height:
				continue
			var wz := z - depth * 0.36 + float(window_number) * 3.3
			_block(name_text + "_Window_" + str(floor_number)
				+ "_" + str(window_number),
				Vector3(side * 11.46, wy, wz), Vector3(0.035, 0.83, 1.12),
				Color(0.14, 0.24, 0.30), false)
			_block(name_text + "_Lintel_" + str(floor_number)
				+ "_" + str(window_number),
				Vector3(side * 11.42, wy + 0.45, wz),
				Vector3(0.08, 0.07, 1.22),
				Color(0.68, 0.69, 0.67), false)


func _make_buildings() -> void:
	# Separate façades leave an urban rhythm, alleys and plausible front doors.
	_building("Residencias_01", -1.0, 0.5, 9.0, 6.1, Color(0.43, 0.43, 0.45))
	_building("Escuela_Exterior", -1.0, -20.0, 14.5, 6.4,
		Color(0.52, 0.52, 0.50))
	_building("Biblioteca_Cerrada", -1.0, -37.0, 10.0, 5.3,
		Color(0.39, 0.45, 0.46))
	_building("Viviendas_02", -1.0, -55.5, 10.0, 7.1,
		Color(0.40, 0.37, 0.38))
	_building("Comercios_01", 1.0, -0.5, 10.0, 5.6,
		Color(0.46, 0.43, 0.43))
	_building("Taller_Cerrado", 1.0, -16.0, 9.0, 4.6,
		Color(0.36, 0.40, 0.43))
	_building("Bloque_Viviendas", 1.0, -32.3, 12.0, 7.5,
		Color(0.42, 0.43, 0.46))
	_building("Club_Exterior", 1.0, -53.0, 13.6, 5.6,
		Color(0.21, 0.20, 0.30))
	_sign("BIBLIOTECA\nCERRADA", Vector3(-10.75, 2.15, -37.0),
		Color(0.74, 0.76, 0.76), 24)
	_sign("TALLER DE REPARACION", Vector3(10.7, 2.1, -16.0),
		Color(0.70, 0.72, 0.71), 25)


func _tree(name_text: String, pos: Vector3) -> void:
	var trunk := StaticBody3D.new()
	trunk.name = name_text
	trunk.position = pos
	var bark := MeshInstance3D.new()
	var cylinder := CylinderMesh.new()
	cylinder.top_radius = 0.13
	cylinder.bottom_radius = 0.21
	cylinder.height = 2.4
	bark.mesh = cylinder
	bark.material_override = _material(Color(0.25, 0.19, 0.16))
	trunk.add_child(bark)
	var collision := CollisionShape3D.new()
	var shape := CylinderShape3D.new()
	shape.radius = 0.22
	shape.height = 2.4
	collision.shape = shape
	trunk.add_child(collision)
	add_child(trunk)
	var crown := MeshInstance3D.new()
	crown.name = "Crown"
	var globe := SphereMesh.new()
	globe.radius = 1.35
	globe.height = 2.2
	crown.mesh = globe
	crown.material_override = _material(Color(0.20, 0.28, 0.24))
	crown.position.y = 2.0
	trunk.add_child(crown)


func _make_places() -> void:
	# Empty landmarks invite future quests without inventing current NPCs.
	_sign("PLAZA / CALLE 03", Vector3(-0.25, 2.8, -36.2),
		Color(0.68, 0.71, 0.76), 25)
	_block("Parada_Espera", Vector3(7.3, 0.75, -27.0),
		Vector3(0.9, 1.5, 0.18), Color(0.19, 0.31, 0.36))
	_sign("LINEA 04\nFUERA DE SERVICIO", Vector3(7.3, 2.1, -27.0),
		Color(0.66, 0.76, 0.76), 22)
	_block("Cabina_Telefonica", Vector3(-7.3, 1.2, -47.0),
		Vector3(0.95, 2.4, 0.95), Color(0.24, 0.29, 0.33))
	_sign("TELEFONO\nSIN TONO", Vector3(-7.3, 2.75, -47.0),
		Color(0.66, 0.72, 0.76), 23)
	for i in range(6):
		var z := -5.0 - float(i) * 10.3
		var x := -5.15 if i % 2 == 0 else 5.15
		_tree("Arbol_" + str(i), Vector3(x, 1.2, z))
		_light("Farola_" + str(i), Vector3(x, 4.1, z),
			Color(0.76, 0.77, 0.72))
	_light("Letrero_Escuela", SCHOOL_ENTRANCE + Vector3(1.4, 2.4, 0.0),
		Color(0.72, 0.75, 0.85))
	_light("Letrero_Club", NIGHTCLUB_ENTRANCE + Vector3(-1.4, 2.4, 0.0),
		Color(0.78, 0.30, 0.84))


func _make_entrance(target: String, pos: Vector3,
		title: String, shade: Color) -> void:
	# The entrance is attached to the street-facing façade, off the road.
	var door := StaticBody3D.new()
	door.name = "Entrance_" + target
	door.set_script(EXIT_SCRIPT)
	door.set("target_location", target)
	door.position = pos
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(0.12, 2.1, 1.48)
	mesh.mesh = box
	mesh.material_override = _material(shade.darkened(0.62))
	door.add_child(mesh)
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = box.size
	collision.shape = shape
	door.add_child(collision)
	add_child(door)
	_block("DoorFrame_" + target, pos + Vector3(0, 1.12, 0),
		Vector3(0.17, 0.17, 1.65), shade, false)
	_sign(title, pos + Vector3(
		1.0 if target == "SCHOOL" else -1.0, 2.8, 0.0,
	), shade.lightened(0.25), 33)
	_sign("[E]", pos + Vector3(
		1.0 if target == "SCHOOL" else -1.0, 1.7, 0.0,
	), shade.lightened(0.32), 22)
