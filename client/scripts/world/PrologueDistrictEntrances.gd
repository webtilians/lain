extends Node3D

const EXIT_SCRIPT = preload("res://scripts/world/ExitDoor.gd")


func _ready() -> void:
	_make_entrance(
		"ESCUELA\n[E] ENTRAR", "SCHOOL",
		Vector3(-2.4, 1.1, -9.2), Color(0.70, 0.78, 0.90),
	)
	_make_entrance(
		"DISCOTECA\n[E] ENTRAR", "NIGHTCLUB",
		Vector3(2.4, 1.1, -18.2), Color(0.85, 0.36, 0.79),
	)


func _make_entrance(text: String, target: String,
		pos: Vector3, shade: Color) -> void:
	var entrance := StaticBody3D.new()
	entrance.name = "Entrance_" + target
	entrance.set_script(EXIT_SCRIPT)
	entrance.set("target_location", target)
	entrance.position = pos
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(1.25, 2.2, 0.22)
	mesh.mesh = box
	var material := StandardMaterial3D.new()
	material.albedo_color = shade.darkened(0.5)
	material.emission_enabled = true
	material.emission = shade.darkened(0.65)
	mesh.material_override = material
	entrance.add_child(mesh)
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = box.size
	collision.shape = shape
	entrance.add_child(collision)
	add_child(entrance)
	var sign := Label3D.new()
	sign.position = pos + Vector3(0, 1.7, 0.1)
	sign.text = text
	sign.font_size = 32
	sign.pixel_size = 0.005
	sign.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sign.modulate = shade
	sign.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(sign)
