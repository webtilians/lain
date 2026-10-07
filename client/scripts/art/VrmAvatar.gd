extends Node3D
## A character made in VRoid Studio (VROID.md), imported from its .vrm as glTF. VRoid
## leaves it in a T-pose with flat (unlit) materials; this gives it the game's anime
## shading (light with a hard edge, shadows that keep the colour, a rim), lowers the
## arms and keeps it alive: breathing, a small sway, blinking, the head turning to whoever
## comes near, and a walk when it moves. Presentation only.
const ARM_DOWN := 72.0  # degrees from the T-pose
const LOOK_RANGE := 4.0
const LOOK_LIMIT := 55.0
const SHADE_KEEP := 0.08  # how much of its colour a surface keeps in full shadow

var skeleton: Skeleton3D
var face: MeshInstance3D
var bones := {}
var clock := 0.0
var blink_at := 2.0
var blink_left := 0.0
var last_position := Vector3.ZERO
var stride := 0.0
var look := 0.0
var materials := {}

func setup(model: PackedScene, extras: Dictionary = {}) -> void:
	var body := model.instantiate()
	body.name = "Model"
	add_child(body)
	skeleton = body.find_children("*", "Skeleton3D", true, false)[0]
	for name in ["J_Bip_C_Hips", "J_Bip_C_Spine", "J_Bip_C_Chest", "J_Bip_C_Neck", "J_Bip_C_Head",
			"J_Bip_L_UpperArm", "J_Bip_R_UpperArm", "J_Bip_L_LowerArm", "J_Bip_R_LowerArm",
			"J_Bip_L_UpperLeg", "J_Bip_R_UpperLeg", "J_Bip_L_LowerLeg", "J_Bip_R_LowerLeg"]:
		bones[name] = skeleton.find_bone(name)
	for mesh in body.find_children("*", "MeshInstance3D", true, false):
		if mesh.mesh != null and mesh.mesh.get_blend_shape_count() > 0 and mesh.find_blend_shape_by_name("Fcl_EYE_Close") >= 0:
			face = mesh
		_shade(mesh)
	if extras.get("headphones", false):
		_headphones(extras.get("accent", Color("e0397a")))
	last_position = global_position if is_inside_tree() else Vector3.ZERO
	_pose(0.0)

func _shade(mesh: MeshInstance3D) -> void:
	## VRoid's flat materials, lit the anime way.
	for index in mesh.mesh.get_surface_count():
		var flat := mesh.get_active_material(index) as BaseMaterial3D
		if flat == null:
			continue
		if not materials.has(flat):
			var anime: BaseMaterial3D = flat.duplicate()
			anime.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
			anime.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON
			anime.specular_mode = BaseMaterial3D.SPECULAR_TOON
			anime.roughness = 0.75
			anime.metallic = 0.0
			anime.rim_enabled = true
			anime.rim = 0.3
			anime.rim_tint = 0.6
			# Shadows keep part of the colour, as anime shading does (never black).
			anime.emission_enabled = true
			anime.emission = Color(SHADE_KEEP, SHADE_KEEP, SHADE_KEEP)
			anime.emission_texture = flat.albedo_texture
			anime.emission_energy_multiplier = 1.0
			anime.set_meta("anime", true)
			materials[flat] = anime
		mesh.set_surface_override_material(index, materials[flat])

func _headphones(accent: Color) -> void:
	## Ryoko's headphones, which VRoid does not have: on her head, over the hair.
	var holder := BoneAttachment3D.new()
	holder.name = "Headphones"
	holder.bone_name = "J_Bip_C_Head"
	skeleton.add_child(holder)
	var top := 0.0
	for mesh in get_node("Model").find_children("*", "MeshInstance3D", true, false):
		if "Hair" in str(mesh.name):
			top = maxf(top, mesh.get_aabb().end.y)
	var head_y := skeleton.get_bone_global_rest(bones.J_Bip_C_Head).origin.y
	var reach := maxf(0.12, top - head_y - 0.06)  # from the ears to just over the hair
	# The band: an arc of short pieces from one ear, over the hair, to the other.
	var dark := _toon(Color("2a1a2e"))
	var pieces := 14
	for step in range(pieces):
		var angle := PI * (float(step) + 0.5) / pieces
		var piece := MeshInstance3D.new()
		var block := BoxMesh.new()
		block.size = Vector3(PI * reach / pieces + 0.004, 0.016, 0.03)
		piece.mesh = block
		piece.material_override = dark
		piece.position = Vector3(cos(angle) * reach, 0.07 + sin(angle) * reach, -0.005)
		piece.rotation.z = angle - PI / 2.0
		holder.add_child(piece)
	for side in [-1.0, 1.0]:
		var cup := MeshInstance3D.new()
		var shell := CylinderMesh.new()
		shell.top_radius = 0.042
		shell.bottom_radius = 0.042
		shell.height = 0.036
		cup.mesh = shell
		cup.material_override = _toon(accent)
		cup.position = Vector3(side * (reach + 0.02), 0.07, -0.005)
		cup.rotation_degrees = Vector3(0, 0, 90)
		holder.add_child(cup)

func _toon(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON
	material.specular_mode = BaseMaterial3D.SPECULAR_TOON
	material.roughness = 0.6
	material.rim_enabled = true
	material.rim = 0.8
	material.emission_enabled = true
	material.emission = color * SHADE_KEEP
	material.set_meta("anime", true)
	return material

func _process(delta: float) -> void:
	if skeleton == null:
		return
	clock += delta
	var moved := Vector2(global_position.x - last_position.x, global_position.z - last_position.z).length()
	last_position = global_position
	var speed := moved / maxf(delta, 0.0001)
	stride = stride + delta * speed * 4.2 if speed > 0.15 else 0.0
	_blink(delta)
	_look(delta)
	_pose(clampf(speed / 2.5, 0.0, 1.0))

func _blink(delta: float) -> void:
	if face == null:
		return
	blink_at -= delta
	if blink_at <= 0.0:
		blink_left = 0.13
		blink_at = randf_range(2.5, 6.0)
	blink_left = maxf(0.0, blink_left - delta)
	face.set_blend_shape_value(face.find_blend_shape_by_name("Fcl_EYE_Close"), 1.0 if blink_left > 0.0 else 0.0)

func _look(delta: float) -> void:
	## The head turns, a little, towards the player when they come near.
	var wanted := 0.0
	var player := get_tree().get_first_node_in_group("player") as Node3D
	if player != null and player != owner and player.global_position.distance_to(global_position) < LOOK_RANGE:
		var to_player := global_transform.affine_inverse() * player.global_position
		wanted = clampf(rad_to_deg(atan2(to_player.x, to_player.z)), -LOOK_LIMIT, LOOK_LIMIT)
	look = lerpf(look, wanted, minf(1.0, delta * 3.0))

func _turn(bone: String, axis: Vector3, degrees: float) -> Quaternion:
	## A rotation about a world axis, in the bone's own frame on top of its rest.
	var index: int = bones[bone]
	var local_axis := (skeleton.get_bone_global_rest(index).basis.inverse() * axis).normalized()
	return skeleton.get_bone_rest(index).basis.get_rotation_quaternion() * Quaternion(local_axis, deg_to_rad(degrees))

func _pose(walk: float) -> void:
	var swing := sin(stride) * walk
	var breath := sin(clock * TAU / 4.0)
	var arm_swing := swing * 22.0
	skeleton.set_bone_pose_rotation(bones.J_Bip_L_UpperArm, _turn("J_Bip_L_UpperArm", Vector3.BACK, -ARM_DOWN)
		* Quaternion(Vector3.RIGHT, deg_to_rad(-arm_swing)))
	skeleton.set_bone_pose_rotation(bones.J_Bip_R_UpperArm, _turn("J_Bip_R_UpperArm", Vector3.BACK, ARM_DOWN)
		* Quaternion(Vector3.RIGHT, deg_to_rad(arm_swing)))
	skeleton.set_bone_pose_rotation(bones.J_Bip_L_LowerArm, _turn("J_Bip_L_LowerArm", Vector3.UP, 12.0 + 8.0 * walk))
	skeleton.set_bone_pose_rotation(bones.J_Bip_R_LowerArm, _turn("J_Bip_R_LowerArm", Vector3.UP, -12.0 - 8.0 * walk))
	skeleton.set_bone_pose_rotation(bones.J_Bip_L_UpperLeg, _turn("J_Bip_L_UpperLeg", Vector3.RIGHT, -swing * 28.0))
	skeleton.set_bone_pose_rotation(bones.J_Bip_R_UpperLeg, _turn("J_Bip_R_UpperLeg", Vector3.RIGHT, swing * 28.0))
	skeleton.set_bone_pose_rotation(bones.J_Bip_L_LowerLeg, _turn("J_Bip_L_LowerLeg", Vector3.RIGHT, maxf(0.0, swing) * 40.0))
	skeleton.set_bone_pose_rotation(bones.J_Bip_R_LowerLeg, _turn("J_Bip_R_LowerLeg", Vector3.RIGHT, maxf(0.0, -swing) * 40.0))
	skeleton.set_bone_pose_rotation(bones.J_Bip_C_Chest, _turn("J_Bip_C_Chest", Vector3.RIGHT, breath * 1.6))
	skeleton.set_bone_pose_rotation(bones.J_Bip_C_Spine, _turn("J_Bip_C_Spine", Vector3.BACK, sin(clock * TAU / 7.0) * 1.2))
	skeleton.set_bone_pose_rotation(bones.J_Bip_C_Neck, _turn("J_Bip_C_Neck", Vector3.UP, look * 0.4))
	skeleton.set_bone_pose_rotation(bones.J_Bip_C_Head, _turn("J_Bip_C_Head", Vector3.UP, look * 0.6))
	skeleton.set_bone_pose_position(bones.J_Bip_C_Hips, skeleton.get_bone_rest(bones.J_Bip_C_Hips).origin
		+ Vector3(0, -absf(swing) * 0.025 - (1.0 - walk) * 0.004 * breath, 0))
