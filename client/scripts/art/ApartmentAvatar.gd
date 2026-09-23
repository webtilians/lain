extends Node3D
var stride := 0.0

func _process(delta: float) -> void:
	var player := get_parent() as CharacterBody3D
	if player == null:
		return
	var rig: Node3D = self
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
