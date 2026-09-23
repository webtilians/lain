extends Node3D
## Temporary three-dimensional prologue level kit. No server state is
## invented here: movement and dialogue are authorized by World Core.
@export_enum("SCHOOL", "SCHOOL_LAB", "NIGHTCLUB") var location_id := "SCHOOL"

const EXIT_SCRIPT = preload("res://scripts/world/ExitDoor.gd")
const NPC_SCRIPT = preload("res://scripts/world/PrologueNpc.gd")


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
	surface.material_override = _mat(shade)
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


func _build_world() -> void:
	var school := location_id != "NIGHTCLUB"
	var concrete := Color(0.29, 0.30, 0.34) if school else Color(0.105, 0.085, 0.17)
	var wall := Color(0.36, 0.37, 0.43) if school else Color(0.16, 0.12, 0.23)
	_solid("Floor", Vector3(0, -0.2, 0), Vector3(14, 0.4, 17), concrete)
	_solid("WestWall", Vector3(-7.1, 1.7, 0), Vector3(0.3, 3.4, 17), wall)
	_solid("EastWall", Vector3(7.1, 1.7, 0), Vector3(0.3, 3.4, 17), wall)
	_solid("BackWall", Vector3(0, 1.7, -8.3), Vector3(14, 3.4, 0.3), wall)
	_solid("FrontWall", Vector3(0, 1.7, 8.4), Vector3(14, 3.4, 0.3), wall)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-53, 135, 0)
	sun.light_energy = 0.75 if school else 0.28
	add_child(sun)
	var theme := Color(0.65, 0.76, 0.89) if school else Color(0.81, 0.22, 0.85)
	_light(Vector3(-3, 3.4, -4), theme, 0.85 if school else 1.5)
	_light(Vector3(3, 3.4, 3), theme, 0.8 if school else 1.2)
	if location_id == "SCHOOL":
		_sign("ESCUELA / PASILLO 02\nAULA DE INFORMATICA", Vector3(0, 2.75, -7), theme)
		_door("BARRIO", "APARTMENT_DISTRICT", Vector3(-3.2, 1.1, 6.7), theme)
		_door("AULA DE INFORMATICA", "SCHOOL_LAB", Vector3(2.7, 1.1, -6.6), theme)
		for i in range(3):
			_solid("Locker_" + str(i), Vector3(-5.3, 0.95, -4 + i * 2.4),
				Vector3(1.1, 1.9, 0.8), Color(0.27, 0.35, 0.41))
	elif location_id == "SCHOOL_LAB":
		_sign("AULA DE INFORMATICA\nORDENADORES SIN CONEXION",
			Vector3(0, 2.65, -7), theme)
		_door("PASILLO", "SCHOOL", Vector3(0, 1.1, 6.7), theme)
		for i in range(4):
			var x := -4.4 + float(i % 2) * 4.2
			var z := -4.6 + float(i / 2) * 2.8
			_solid("Desk_" + str(i), Vector3(x, 0.47, z),
				Vector3(1.6, 0.94, 0.75), Color(0.35, 0.32, 0.33))
			_solid("CRT_" + str(i), Vector3(x, 1.14, z - 0.12),
				Vector3(0.55, 0.49, 0.40), Color(0.11, 0.14, 0.15))
		_npc("PROFESOR", "PROFESSOR", Vector3(2.6, 0.9, -3.7),
			Color(0.54, 0.58, 0.67))
	elif location_id == "NIGHTCLUB":
		_sign("CLUB // 1998\nLOS ROSTROS SE PIERDEN EN EL RUIDO",
			Vector3(0, 2.7, -7), theme)
		_door("BARRIO", "APARTMENT_DISTRICT", Vector3(0, 1.1, 6.7), theme)
		_solid("DJDesk", Vector3(-2.9, 0.7, -6.2),
			Vector3(3.5, 1.4, 1.1), Color(0.12, 0.13, 0.20))
		for i in range(7):
			var x := -4.5 + float(i % 4) * 3.0
			var z := -2.7 + float(i / 4) * 2.5
			_solid("DanceTile_" + str(i), Vector3(x, 0.02, z),
				Vector3(2.3, 0.03, 2.1),
				Color(0.14 + 0.04 * float(i % 2), 0.12, 0.22))
		_npc("RYOKO", "RYOKO", Vector3(3.5, 0.9, -4.7),
			Color(0.77, 0.27, 0.62))
