extends Node3D
## Reuses the sculpted articulated rig, with deterministic civilian clothing.
var last_position := Vector3.ZERO
var stride := 0.0
var actor: Node3D
var player: Node3D

func configure(kind: String, variant: int) -> void:
	name = "CitizenBody"
	position.y = 0.9
	var colors := ["6e7272","7e6d62","52616e","7a7780","6d7764","78606a"]
	var cloth := Color(colors[posmod(variant,colors.size())])
	var pants := kind in ["worker","teacher","suit"] or (variant % 2 == 0 and kind != "student")
	var tall := 0.94 + float(variant%5)*0.035
	scale = Vector3(1.05 if pants else 1.0,tall,1.0)
	position.y = 0.86*tall
	for part in ["LongSideLock","HairClip","Ribbon"]:
		get_node(part).hide()
	if kind != "student":
		for part in ["Satchel","SatchelStrap","SatchelStrap2"]:
			get_node(part).hide()
	if pants:
		get_node("PleatedSkirt").hide()
		for side in ["Left","Right"]:
			for path in [side+"Leg/Thigh",side+"Leg/Knee/Calf",side+"Leg/Knee/Sock"]:
				var leg: MeshInstance3D = get_node(path)
				leg.scale.x = 1.27
				leg.scale.z = 1.2
				tint(leg, cloth.darkened(0.15))
		get_node("BobHair").scale = Vector3(1.0,0.7,1.0)
		get_node("BobHair").position.y = 0.21
	for path in ["TailoredBlouse","LeftArm/Sleeve","RightArm/Sleeve"]:
		tint(get_node(path),cloth)
	if kind == "elder":
		tint(get_node("BobHair"),Color("a09b94"))
		scale.y *= 0.93
		position.y *= 0.93
	if kind == "apron":
		var apron := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		mesh.size = Vector3(0.25,0.47,0.018)
		apron.mesh = mesh
		apron.position = Vector3(0,0.05,0.113)
		var material := StandardMaterial3D.new()
		material.albedo_color = Color("c0b7a0")
		material.roughness = 1
		apron.material_override = material
		add_child(apron)

func tint(mesh: MeshInstance3D, color: Color) -> void:
	var material := mesh.material_override.duplicate() as StandardMaterial3D
	material.albedo_color = color
	mesh.material_override = material

func _ready() -> void:
	actor = get_parent()
	last_position = actor.global_position
	player = get_tree().get_first_node_in_group("player")

func _process(delta: float) -> void:
	if is_instance_valid(player):
		for label_name in ["NameLabel","Activity"]:
			var label := actor.get_node_or_null(label_name) as Label3D
			if label != null:
				label.visible = actor.global_position.distance_to(player.global_position) < 5.0
	var motion := actor.global_position-last_position
	last_position = actor.global_position
	var walking := motion.length_squared() > 0.000001
	if walking:
		stride += delta*7
		rotation.y = lerp_angle(rotation.y,atan2(motion.x,motion.z),minf(1,delta*10))
	var swing := sin(stride)*0.25 if walking else 0.0
	$LeftLeg.rotation.x = swing
	$RightLeg.rotation.x = -swing
	$LeftLeg/Knee.rotation.x = -maxf(0,-swing)*0.6
	$RightLeg/Knee.rotation.x = -maxf(0,swing)*0.6
	$LeftArm.rotation.x = -swing*0.6
	$RightArm.rotation.x = swing*0.6
