extends Node3D
## Hide only the upper visual shell if it obscures the avatar. Collision stays put.
@export var bounds := AABB()
@onready var upper: Node3D = $Upper
var player: CharacterBody3D
var elapsed := 0.0

func _ready() -> void:
	player = get_tree().get_first_node_in_group("player") as CharacterBody3D

func _process(delta: float) -> void:
	elapsed += delta
	if elapsed < 0.10:
		return
	elapsed = 0.0
	if not is_instance_valid(player):
		player = get_tree().get_first_node_in_group("player") as CharacterBody3D
		return
	var camera := player.get_node_or_null("Head/Camera3D") as Camera3D
	if camera == null:
		return
	var feet := to_local(player.global_position + Vector3(0, -0.25, 0))
	var head := feet + Vector3(0, 1.2, 0)
	# Orthographic sight rays are parallel, not rays toward a perspective eye.
	var toward_camera := global_basis.inverse() * camera.global_basis.z * 40.0
	upper.visible = bounds.intersects_segment(head, head+toward_camera) == null and bounds.intersects_segment(feet, feet+toward_camera) == null
