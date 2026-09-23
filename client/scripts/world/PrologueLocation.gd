extends Node3D
## Temporary three-dimensional prologue level kit. No server state is
## invented here: movement and dialogue are authorized by World Core.
@export_enum("SCHOOL", "SCHOOL_LAB", "NIGHTCLUB") var location_id := "SCHOOL"

const EXIT_SCRIPT = preload("res://scripts/world/ExitDoor.gd")
const NPC_SCRIPT = preload("res://scripts/world/PrologueNpc.gd")
const CONCRETE = preload("res://art/visual05/textures/concrete.png")
const WOOD = preload("res://art/visual05/textures/wood.png")


func _ready() -> void:
	_build_world()
	WorldApi.snapshot_updated.connect(_on_snapshot)
	_on_snapshot(WorldApi.snapshot)


func _on_snapshot(snapshot: Dictionary) -> void:
	var player: Dictionary = snapshot.get("player", {})
	if str(player.get("location", "")) != location_id:
		return
	var hint: Label = get_node("HUD/Hint")
	var atmosphere := "ESCUELA // PASILLO 02"
	if location_id == "SCHOOL_LAB":
		atmosphere = "AULA DE INFORMÁTICA // UN ORDENADOR SIGUE ENCENDIDO"
	elif location_id == "NIGHTCLUB":
		atmosphere = "SÓTANO AZUL // LAS CONVERSACIONES NO LLEGAN AL OTRO LADO"
	hint.text = atmosphere + "  //  E: INTERACTUAR   J: DIARIO"


func _mat(shade: Color, glowing: bool = false) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = shade
	material.roughness = 0.82
	if glowing:
		material.emission_enabled = true
		material.emission = shade
		material.emission_energy_multiplier = 1.2
	return material


func _solid(label: String, pos: Vector3, size: Vector3, shade: Color) -> void:
	var body := StaticBody3D.new()
	body.name = label
	body.position = pos
	var box := BoxMesh.new()
	box.size = size
	var surface := MeshInstance3D.new()
	surface.mesh = box
	var material := _mat(shade)
	if label == "Floor" or label.ends_with("Wall"):
		material.albedo_texture = CONCRETE
		material.uv1_triplanar = true
		material.uv1_world_triplanar = true
		material.uv1_scale = Vector3(0.52, 0.52, 0.52)
	elif label.begins_with("Desk") or label.begins_with("Locker"):
		material.albedo_texture = WOOD
		material.uv1_triplanar = true
		material.uv1_world_triplanar = true
	surface.material_override = material
	body.add_child(surface)
	var collider := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collider.shape = shape
	body.add_child(collider)
	add_child(body)


func _sign(title: String, pos: Vector3, shade: Color) -> void:
	var label := Label3D.new()
	label.text = title
	label.position = pos
	label.font_size = 32
	label.pixel_size = 0.006
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = shade
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(label)


func _door(title: String, target: String, pos: Vector3, shade: Color) -> void:
	var door := StaticBody3D.new()
	door.name = "Door_" + target
	door.set_script(EXIT_SCRIPT)
	door.set("target_location", target)
	door.position = pos
	var mesh := MeshInstance3D.new()
	var shape := BoxMesh.new()
	shape.size = Vector3(1.6, 2.2, 0.24)
	mesh.mesh = shape
	mesh.material_override = _mat(shade)
	door.add_child(mesh)
	var collision := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = shape.size
	collision.shape = box
	door.add_child(collision)
	add_child(door)
	_sign(title + "\n[E] ENTRAR", pos + Vector3(0, 1.7, 0.4), shade.lightened(0.32))


func _npc(name_text: String, actor_id: String, pos: Vector3,
		shade: Color) -> void:
	var actor := StaticBody3D.new()
	actor.name = actor_id
	actor.set_script(NPC_SCRIPT)
	actor.set("npc_id", actor_id)
	actor.position = pos
	var mesh := MeshInstance3D.new()
	mesh.name = "Body"
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.28
	capsule.height = 1.66
	mesh.mesh = capsule
	mesh.material_override = _mat(shade)
	actor.add_child(mesh)
	var collider := CollisionShape3D.new()
	var collision := CapsuleShape3D.new()
	collision.radius = 0.28
	collision.height = 1.66
	collider.shape = collision
	actor.add_child(collider)
	add_child(actor)
	_sign(name_text + "\n[E] HABLAR", pos + Vector3(0, 1.25, 0), shade.lightened(0.3))


func _light(pos: Vector3, shade: Color, power: float) -> void:
	var lamp := OmniLight3D.new()
	lamp.position = pos
	lamp.light_color = shade
	lamp.light_energy = power
	lamp.omni_range = 9.0
	add_child(lamp)


func _detail(label: String, pos: Vector3, size: Vector3,
		shade: Color, luminous: bool = false) -> void:
	# Decorative details without invisible collision in the walkable room.
	var instance := MeshInstance3D.new()
	instance.name = label
	instance.position = pos
	var mesh := BoxMesh.new()
	mesh.size = size
	instance.mesh = mesh
	instance.material_override = _mat(shade, luminous)
	add_child(instance)


func _build_world() -> void:
	# Open isometric diorama: two camera-facing walls are only waist-high.
	# This removes the opaque "shoebox" that hid the room and the NPCs.
	var school := location_id != "NIGHTCLUB"
	var floor_shade := Color(0.44, 0.45, 0.46) if school else Color(0.18, 0.17, 0.24)
	var wall_shade := Color(0.57, 0.58, 0.56) if school else Color(0.24, 0.23, 0.31)
	_solid("Floor", Vector3(0, -0.2, 0), Vector3(14, 0.4, 17), floor_shade)
	_solid("WestWall", Vector3(-7.1, 1.86, 0),
		Vector3(0.24, 3.72, 17), wall_shade)
	_solid("BackWall", Vector3(0, 1.86, -8.3),
		Vector3(14, 3.72, 0.24), wall_shade)
	_solid("EastWall", Vector3(7.1, 0.38, 0),
		Vector3(0.24, 0.76, 17), wall_shade.darkened(0.17))
	_solid("FrontWall", Vector3(0, 0.38, 8.4),
		Vector3(14, 0.76, 0.24), wall_shade.darkened(0.17))
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-53, 135, 0)
	sun.light_energy = 0.7 if school else 0.22
	add_child(sun)
	var theme := Color(0.71, 0.78, 0.77) if school else Color(0.50, 0.31, 0.68)
	_light(Vector3(-3.1, 3.3, -4), theme, 0.9 if school else 1.3)
	_light(Vector3(3.1, 3.3, 1.8), theme, 0.75 if school else 1.15)
	for i in range(7):
		_detail("FloorSeam_" + str(i),
			Vector3(0, 0.014, -6.9 + float(i) * 2.2),
			Vector3(13.8, 0.006, 0.025), floor_shade.darkened(0.23))
	for i in range(4):
		_detail("Window_" + str(i),
			Vector3(-6.96, 2.25, -5.65 + float(i) * 3.15),
			Vector3(0.04, 1.16, 1.42),
			Color(0.18, 0.31, 0.35) if school else Color(0.11, 0.14, 0.22))
		_detail("WindowSill_" + str(i),
			Vector3(-6.84, 1.59, -5.65 + float(i) * 3.15),
			Vector3(0.18, 0.07, 1.6), wall_shade.lightened(0.12))
	if location_id == "SCHOOL":
		_hallway(theme)
	elif location_id == "SCHOOL_LAB":
		_lab(theme)
	else:
		_club(theme)


func _hallway(theme: Color) -> void:
	_sign("ESCUELA MUNICIPAL\nPABELLÓN B",
		Vector3(0, 2.72, -7.4), theme)
	_door("BARRIO", "APARTMENT_DISTRICT", Vector3(-3.2, 1.1, 6.7), theme)
	_door("AULA DE INFORMÁTICA", "SCHOOL_LAB",
		Vector3(2.7, 1.1, -6.6), theme)
	_detail("SchoolStripe", Vector3(0, 1.08, -8.11),
		Vector3(13.7, 0.28, 0.035), Color(0.34, 0.45, 0.44))
	_detail("SchoolNoticeboard", Vector3(-6.93, 1.91, 0.75),
		Vector3(0.06, 1.15, 2.45), Color(0.43, 0.33, 0.22))
	for i in range(4):
		var z := -4.65 + float(i) * 2.2
		_solid("Locker_" + str(i), Vector3(-5.22, 0.94, z),
			Vector3(0.79, 1.88, 0.79), Color(0.42, 0.51, 0.49))
		_detail("LockerFront_" + str(i), Vector3(-4.81, 0.98, z),
			Vector3(0.025, 1.68, 0.68), Color(0.31, 0.40, 0.41))
		_detail("LockerHandle_" + str(i),
			Vector3(-4.77, 1.06, z + 0.18),
			Vector3(0.035, 0.12, 0.05), Color(0.72, 0.73, 0.70))
	_sign("AULA 02\nEQUIPO ANTIGUO",
		Vector3(2.7, 2.69, -6.0), Color(0.70, 0.74, 0.72))


func _lab(theme: Color) -> void:
	_sign("AULA DE INFORMÁTICA\nORDENADORES SIN CONEXIÓN",
		Vector3(0, 2.78, -7.45), theme)
	_door("PASILLO", "SCHOOL", Vector3(0, 1.1, 6.7), theme)
	_detail("LabBoard", Vector3(-2.0, 2.03, -8.10),
		Vector3(5.6, 1.6, 0.04), Color(0.12, 0.20, 0.17))
	_detail("LabBoardTray", Vector3(-2.0, 1.16, -8.03),
		Vector3(5.7, 0.07, 0.16), Color(0.65, 0.63, 0.53))
	_sign("EL QUE OBSERVA\nNO SIEMPRE ES VISTO",
		Vector3(-2.0, 2.04, -7.94), Color(0.68, 0.74, 0.69))
	for index in range(4):
		var x := -4.15 + float(index % 2) * 4.15
		var z := -4.12 + float(index / 2) * 3.13
		_solid("Desk_" + str(index), Vector3(x, 0.49, z),
			Vector3(1.55, 0.97, 0.86), Color(0.46, 0.41, 0.34))
		_solid("CRT_" + str(index), Vector3(x, 1.16, z - 0.17),
			Vector3(0.66, 0.54, 0.45), Color(0.36, 0.36, 0.34))
		_detail("CRTScreen_" + str(index),
			Vector3(x, 1.2, z + 0.067), Vector3(0.49, 0.39, 0.023),
			Color(0.07, 0.11, 0.13) if index != 2 else
			Color(0.23, 0.33, 0.30), index == 2)
		_detail("Keyboard_" + str(index),
			Vector3(x, 1.0, z + 0.33), Vector3(0.65, 0.035, 0.15),
			Color(0.24, 0.27, 0.28))
		_detail("Chair_" + str(index),
			Vector3(x, 0.39, z + 1.03), Vector3(0.50, 0.09, 0.48),
			Color(0.32, 0.33, 0.35))
	_detail("LabLight", Vector3(-1.5, 3.14, -3.6),
		Vector3(3.4, 0.07, 0.24), Color(0.76, 0.83, 0.77), true)
	_npc("PROFESOR", "PROFESSOR", Vector3(3.2, 0.9, -4.5),
		Color(0.47, 0.55, 0.62))
	_detail("TeacherTable", Vector3(3.5, 0.55, -6.25),
		Vector3(1.72, 1.0, 0.77), Color(0.46, 0.40, 0.33))


func _club(theme: Color) -> void:
	_sign("AZUL // SALA B\nLOS ROSTROS SE CONFUNDEN",
		Vector3(0, 2.78, -7.43), theme)
	_door("BARRIO", "APARTMENT_DISTRICT", Vector3(0, 1.1, 6.7), theme)
	_detail("ClubDarkBackdrop", Vector3(0, 1.55, -8.09),
		Vector3(13.8, 2.55, 0.04), Color(0.10, 0.10, 0.17))
	_detail("ClubBar", Vector3(5.25, 0.72, -0.8),
		Vector3(1.19, 1.42, 4.4), Color(0.16, 0.17, 0.25))
	_detail("ClubBarTop", Vector3(5.17, 1.5, -0.8),
		Vector3(1.49, 0.11, 4.5), Color(0.32, 0.30, 0.36))
	_detail("ClubBarLight", Vector3(4.40, 1.30, -0.8),
		Vector3(0.07, 0.05, 4.4), Color(0.44, 0.25, 0.53), true)
	_solid("DJDesk", Vector3(-2.85, 0.66, -6.2),
		Vector3(3.45, 1.32, 1.09), Color(0.12, 0.13, 0.20))
	for i in range(6):
		var x := -3.55 + float(i % 3) * 2.60
		var z := -3.13 + float(i / 3) * 2.6
		_detail("ClubDanceTile_" + str(i), Vector3(x, 0.019, z),
			Vector3(2.35, 0.016, 2.29),
			Color(0.20, 0.17, 0.27) if i % 2 == 0 else
			Color(0.14, 0.18, 0.25))
	for z in [-5.8, -1.5]:
		_detail("ClubSpeaker_" + str(z),
			Vector3(-6.75, 1.39, z), Vector3(0.50, 1.50, 0.76),
			Color(0.13, 0.13, 0.17))
		_detail("ClubSpeakerCone_" + str(z),
			Vector3(-6.47, 1.40, z), Vector3(0.04, 0.48, 0.48),
			Color(0.23, 0.24, 0.31))
	_detail("ClubLightViolet", Vector3(-3.5, 3.10, -4.1),
		Vector3(0.08, 0.10, 3.5), Color(0.52, 0.29, 0.67), true)
	_detail("ClubLightBlue", Vector3(2.0, 3.10, -4.1),
		Vector3(0.08, 0.10, 3.5), Color(0.25, 0.40, 0.57), true)
	_light(Vector3(-3.5, 2.85, -3.5), Color(0.54, 0.28, 0.67), 1.26)
	_light(Vector3(3.6, 2.85, 0.0), Color(0.25, 0.37, 0.55), 1.0)
	_npc("RYOKO", "RYOKO", Vector3(3.35, 0.9, -4.7),
		Color(0.50, 0.29, 0.46))
