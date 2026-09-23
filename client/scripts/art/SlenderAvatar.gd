extends Node3D
## Visual pose only; the player's existing collision and movement stay authoritative.
var stride := 0.0

func _process(delta: float) -> void:
	var player := get_parent() as CharacterBody3D
	if player == null:
		return
	var motion := Vector2(player.velocity.x,player.velocity.z)
	var walking := motion.length() > 0.1
	if walking:
		stride += delta * 9.0
		rotation.y = lerp_angle(rotation.y,atan2(motion.x,motion.y),minf(delta*12.0,1.0))
	var swing := sin(stride)*0.22 if walking else 0.0
	$LeftLeg.rotation.x = swing
	$RightLeg.rotation.x = -swing
	$LeftLeg/Knee.rotation.x = -maxf(0.0,-swing)*0.65
	$RightLeg/Knee.rotation.x = -maxf(0.0,swing)*0.65
	$LeftArm.rotation.x = -swing*0.55
	$RightArm.rotation.x = swing*0.55
