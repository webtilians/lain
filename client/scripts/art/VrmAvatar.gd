extends Node3D
## A character made in VRoid Studio (VROID.md), imported from its .vrm as glTF. VRoid
## leaves it in a T-pose with flat (unlit) materials; this gives it the game's anime
## shading (light with a hard edge, shadows that keep the colour, a rim), lowers the
## arms and keeps it alive: breathing, a small sway, blinking, the head turning to whoever
## comes near, and a walk when it moves. What VRoid could not do is retouched here (the
## extras): Ryoko's headphones; the teacher's grey hair, moustache, older look and a
## man's build (VRoid started him from its female base). Presentation only.
const ARM_DOWN := 72.0  # degrees from the T-pose
const LOOK_RANGE := 4.0
const LOOK_LIMIT := 55.0
const SHADE_KEEP := 0.08  # how much of its colour a surface keeps in full shadow
const GREY_HAIR := preload("res://shaders/vrm_grey_hair.gdshader")
const TONE := 0.85  # VRoid's textures are made to be shown unlit: lit, they come out too bright

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
	for part in extras.get("tint", {}):
		_tint(body, part, extras.tint[part])
	if extras.get("grey_hair", false):
		_grey_hair(body)
	for part in extras.get("hide", []):
		_hide(body, part)
	if face != null:
		for shape in extras.get("face", {}):
			var index: int = face.find_blend_shape_by_name(shape)
			if index >= 0:
				face.set_blend_shape_value(index, extras.face[shape])
	if extras.get("moustache", false):
		_moustache()
	if extras.get("masculine", false):
		_masculine()
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
			# Toon light is full light on everything facing the lamp: no extra shine on top.
			anime.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
			anime.roughness = 1.0
			anime.metallic = 0.0
			anime.albedo_color = Color(flat.albedo_color.r * TONE, flat.albedo_color.g * TONE, flat.albedo_color.b * TONE,
				flat.albedo_color.a)
			anime.rim_enabled = true
			anime.rim = 0.3
			anime.rim_tint = 0.6
			# No glow of its own: on VRoid's textures it turned everything white.
			anime.emission_enabled = false
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

func _surfaces(body: Node, part: String) -> Array:
	## [mesh, surface] for every surface whose material is named after this part of VRoid's model.
	var found := []
	for mesh in body.find_children("*", "MeshInstance3D", true, false):
		for index in mesh.mesh.get_surface_count():
			if part in str(mesh.mesh.surface_get_material(index).resource_name):
				found.append([mesh, index])
	return found

func _tint(body: Node, part: String, color: Color) -> void:
	## Recolour a garment (a white one takes the colour as it is), keeping its folds and seams.
	for found in _surfaces(body, part):
		var dressed: BaseMaterial3D = found[0].get_active_material(found[1]).duplicate()
		dressed.albedo_color = Color(color.r * TONE, color.g * TONE, color.b * TONE, dressed.albedo_color.a)
		found[0].set_surface_override_material(found[1], dressed)

func _grey_hair(body: Node) -> void:
	for found in _surfaces(body, "_HAIR"):
		var original: BaseMaterial3D = found[0].mesh.surface_get_material(found[1])
		var grey := ShaderMaterial.new()
		grey.shader = GREY_HAIR
		grey.set_shader_parameter("hair", original.albedo_texture)
		found[0].set_surface_override_material(found[1], grey)

func _hide(body: Node, part: String) -> void:
	## A part VRoid would not leave out (the teacher's long eyelashes).
	var gone := StandardMaterial3D.new()
	gone.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	gone.albedo_color = Color(0, 0, 0, 0)
	gone.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	for found in _surfaces(body, part):
		found[0].set_surface_override_material(found[1], gone)

func _moustache() -> void:
	## Grey, under the nose: placed from the face's own size, on the head bone.
	var holder := BoneAttachment3D.new()
	holder.name = "Moustache"
	holder.bone_name = "J_Bip_C_Head"
	skeleton.add_child(holder)
	var bounds: AABB = face.get_aabb()
	var head := skeleton.get_bone_global_rest(bones.J_Bip_C_Head).origin
	var at := Vector3(0, bounds.position.y + bounds.size.y * 0.205, bounds.end.z - 0.009) - head
	var grey := _toon(Color("b4aea6"))
	grey.emission = Color("b4aea6") * 0.45  # reads as drawn grey whatever the light
	# One piece across the lip, its ends drooping a little.
	for part in [[0.0, 0.0, 0.05, 0.001], [-1.0, -16.0, 0.03, -0.004], [1.0, 16.0, 0.03, -0.004]]:
		var tuft := MeshInstance3D.new()
		var shape := SphereMesh.new()
		shape.radius = 0.5
		shape.height = 1.0
		tuft.mesh = shape
		tuft.material_override = grey
		tuft.scale = Vector3(part[2], 0.0085, 0.011)
		tuft.position = at + Vector3(part[0] * 0.016, part[3], -absf(part[0]) * 0.004)
		tuft.rotation_degrees = Vector3(0, 0, part[1])
		holder.add_child(tuft)

func _masculine() -> void:
	## VRoid's female base made a man: a flat chest, broader shoulders, narrower hips.
	for name in ["J_Sec_L_Bust1", "J_Sec_R_Bust1"]:
		var bust := skeleton.find_bone(name)
		if bust >= 0:
			skeleton.set_bone_pose_scale(bust, Vector3(0.25, 0.25, 0.25))
	var chest := skeleton.find_bone("J_Bip_C_UpperChest")
	if chest >= 0:
		skeleton.set_bone_pose_scale(chest, Vector3(1.12, 1.0, 1.05))
	skeleton.set_bone_pose_scale(bones.J_Bip_C_Hips, Vector3(0.93, 1.0, 1.0))

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
