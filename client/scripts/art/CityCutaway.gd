extends Node3D
## Clear the upper visual shell if it obscures the avatar. Collision stays put.
## Visual 0.11 models fade to see-through (their shadow twin keeps casting);
## legacy box shells are hidden as before.
@export var bounds := AABB()
@onready var upper: Node3D = $Upper
const SEE_THROUGH := 0.8
const FADE_SPEED := 5.0
var player: CharacterBody3D
var elapsed := 0.0
var fades := false
var faders: Array[GeometryInstance3D] = []
var fade := 0.0
var target := 0.0

func _ready() -> void:
	player = get_tree().get_first_node_in_group("player") as CharacterBody3D
	fades = upper.has_node("Block11") or upper.has_node("House11")
	if fades:
		for node in upper.find_children("*", "GeometryInstance3D", true, false):
			faders.append(node)

func _process(delta: float) -> void:
	if fades and fade != target:
		fade = move_toward(fade, target, delta * FADE_SPEED)
		for node in faders:
			node.transparency = fade
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
	var clear := bounds.intersects_segment(head, head+toward_camera) == null and bounds.intersects_segment(feet, feet+toward_camera) == null
	if fades:
		target = 0.0 if clear else SEE_THROUGH
	else:
		upper.visible = clear
