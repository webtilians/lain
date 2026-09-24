extends Node3D
## Functional entrances only; scenery is shipped as an offline-authored PackedScene.
const LAYOUT = preload("res://scripts/world/CityLayout.gd")
const EXIT_SCRIPT = preload("res://scripts/world/ExitDoor.gd")

func _ready() -> void:
	for target in LAYOUT.DOORS:
		var door := StaticBody3D.new()
		door.name = "Entrance_" + target
		door.position = LAYOUT.DOORS[target]
		if target in ["BOOKSHOP","GROCERY","VIDEO_CLUB","CAFE","IZAKAYA","ARCADE"]:
			# Sit in front of the deep wooden shopfront rather than inside its cladding.
			door.position.z += 0.7
		door.set_script(EXIT_SCRIPT)
		door.set("target_location", target)
		if target == "NIGHTCLUB":
			door.rotation.y = PI / 2
		elif target == "APARTMENT":
			door.rotation.y = PI
		var mesh := MeshInstance3D.new()
		var shape := BoxMesh.new()
		shape.size = Vector3(1.38, 2.3, 0.12)
		mesh.mesh = shape
		var material := StandardMaterial3D.new()
		material.albedo_color = Color("303b43")
		material.roughness = 0.74
		mesh.material_override = material
		door.add_child(mesh)
		# Insets/handles are attached to the real door, not a second decorative exit.
		var frame := StandardMaterial3D.new()
		frame.albedo_color = Color("747b7b")
		frame.metallic = 0.35
		frame.roughness = 0.6
		for x in [-0.74,0.74]:
			_detail(door,Vector3(x,0,0),Vector3(0.08,2.42,0.18),frame)
		_detail(door,Vector3(0,1.2,0),Vector3(1.55,0.10,0.18),frame)
		_detail(door,Vector3(0,-1.13,0.02),Vector3(1.50,0.06,0.25),frame)
		_detail(door,Vector3(0.45,-0.12,0.11),Vector3(0.04,0.30,0.06),frame)
		var glass := StandardMaterial3D.new()
		glass.albedo_color = Color("7a9290")
		glass.roughness = 0.45
		_detail(door,Vector3(0,0.38,0.075),Vector3(1.12,0.94,0.015),glass)
		_detail(door,Vector3(0,0.38,0.09),Vector3(0.04,0.95,0.02),frame)
		var collision := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = shape.size
		collision.shape = box
		door.add_child(collision)
		add_child(door)

func _detail(door: Node3D, at: Vector3, size: Vector3, material: Material) -> void:
	var mesh := MeshInstance3D.new()
	var shape := BoxMesh.new()
	shape.size = size
	mesh.mesh = shape
	mesh.material_override = material
	mesh.position = at
	door.add_child(mesh)
