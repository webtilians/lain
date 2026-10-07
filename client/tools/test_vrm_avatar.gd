extends SceneTree
## Ryoko made in VRoid Studio (VROID.md) stands in the club instead of the old figure:
## anime-shaded, arms down from VRoid's T-pose, feet on the floor, headphones on, she
## blinks, turns her head to the player and walks when she moves. Never calls the server.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func frames(count: int = 3) -> void:
	for i in range(count):
		await process_frame

func run() -> void:
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_vrm_test.cfg"
	guide.hidden_by_player = true
	root.get_node("WorldApi").snapshot = {"minute": 1300, "player": {"location": "NIGHTCLUB", "energy": 1.0},
		"visible_actors": [], "known_nodes": [], "prologue": {"enabled": true, "stage": "FIND_RYOKO", "hint": ""}}
	var scene: Node3D = load("res://scenes/prologue/Nightclub.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	await frames(5)

	var ryoko: Node3D = scene.find_child("RYOKO", true, false)
	var avatar: Node3D = ryoko.get_node_or_null("VrmAvatar")
	check(avatar != null and avatar.skeleton != null, "Ryoko is not her VRoid model")
	check(ryoko.find_children("*", "Skeleton3D", true, false).size() == 1, "the old figure is still there too")
	var skeleton: Skeleton3D = avatar.skeleton
	var feet := skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone("J_Bip_L_Foot")).origin
	check(absf(feet.y - 0.11) < 0.08, "her feet are not on the floor: %.2f" % feet.y)

	# Arms down, not VRoid's T-pose.
	var shoulder := skeleton.get_bone_global_pose(skeleton.find_bone("J_Bip_L_UpperArm")).origin
	var elbow := skeleton.get_bone_global_pose(skeleton.find_bone("J_Bip_L_LowerArm")).origin
	check(elbow.y < shoulder.y - 0.15, "her arms are still out in a T")

	# Lit the anime way, with headphones.
	var lit := 0
	for mesh in avatar.find_children("*", "MeshInstance3D", true, false):
		for index in mesh.mesh.get_surface_count():
			var material := mesh.get_active_material(index) as BaseMaterial3D
			if material != null and material.shading_mode == BaseMaterial3D.SHADING_MODE_PER_PIXEL \
					and material.diffuse_mode == BaseMaterial3D.DIFFUSE_TOON:
				lit += 1
	check(lit >= 10, "her materials are still flat: %d lit" % lit)
	var phones := skeleton.get_node_or_null("Headphones") as BoneAttachment3D
	check(phones != null and phones.bone_name == "J_Bip_C_Head" and phones.get_child_count() > 2, "she has no headphones")

	# She blinks.
	avatar.blink_at = 0.0
	await frames(2)
	var close: int = avatar.face.find_blend_shape_by_name("Fcl_EYE_Close")
	check(avatar.face.get_blend_shape_value(close) == 1.0, "she does not blink")

	# The head turns to the player nearby.
	var player: Node3D = scene.get_node("Player")
	player.global_position = ryoko.global_position + ryoko.global_transform.basis.x * 1.6 + Vector3(0, 0, 0.8)
	await frames(60)
	check(absf(avatar.look) > 10.0, "she does not look at the player: %.1f" % avatar.look)

	# She walks when she moves.
	var knee := skeleton.find_bone("J_Bip_L_UpperLeg")
	var standing := skeleton.get_bone_pose_rotation(knee)
	var moved := false
	for i in range(30):
		ryoko.global_position += Vector3(0.05, 0, 0)
		await process_frame
		if not skeleton.get_bone_pose_rotation(knee).is_equal_approx(standing):
			moved = true
	check(moved, "her legs do not move when she walks")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(guide.config_path))
	scene.queue_free()
	current_scene = null
	await frames()
	print("VRM_AVATAR_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
