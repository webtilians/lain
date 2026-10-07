extends Node3D
## Shows what can be used. Everything interactive nearby gets a soft light floating
## over it; the one that E (A on the controller) would use right now gets a ring on
## the floor and a bobbing arrow with the button to press. The player's own rule
## (IsoController.nearest_interactable) picks it, so the marked object is exactly
## the one that answers. Nothing shows while the player is held by a window, a
## terminal or a cinematic.
const HINT_RADIUS := 7.0
const MAX_HEIGHT := 1.6  # marks float at most this far above the floor (doorways have tall collisions)
const AMBER := Color("e0b45a")
const SOFT := Color(0.88, 0.71, 0.35, 0.7)

var player: Node3D
var ring: MeshInstance3D
var marker: Node3D
var prompt: Label3D
var hints: Array[MeshInstance3D] = []
var focused: Node3D
var heights := {}  # instance id -> how far above its origin an object's top is
var clock := 0.0

func _ready() -> void:
	top_level = true  # markers live in world space, not in the player's
	player = get_parent()
	ring = MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.55
	torus.outer_radius = 0.72
	torus.rings = 40
	ring.mesh = torus
	# Seen through the desk or the counter in front: the iso camera looks down on everything.
	ring.material_override = _glow(AMBER, true)
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(ring)
	marker = Node3D.new()
	add_child(marker)
	var arrow := MeshInstance3D.new()
	var prism := PrismMesh.new()
	prism.size = Vector3(0.5, 0.45, 0.1)
	arrow.mesh = prism
	arrow.rotation_degrees.z = 180.0  # pointing down at the object
	arrow.material_override = _glow(AMBER, true)
	arrow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	marker.add_child(arrow)
	prompt = Label3D.new()
	prompt.text = "[%s]" % Gamepad.label("interact")  # Gamepad swaps [E] and [A] on every Label3D
	prompt.position = Vector3(0, 0.62, 0)
	prompt.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	prompt.no_depth_test = true
	prompt.font_size = 64
	prompt.pixel_size = 0.008
	prompt.outline_size = 14
	prompt.modulate = AMBER
	marker.add_child(prompt)
	_hide_all()

func _glow(color: Color, on_top: bool) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = color
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.no_depth_test = on_top
	material.billboard_mode = BaseMaterial3D.BILLBOARD_DISABLED
	return material

func _process(delta: float) -> void:
	clock += delta
	if not is_instance_valid(player) or not player.is_inside_tree() or not player.is_physics_processing() \
			or not player.has_method("nearest_interactable"):
		_hide_all()
		return
	focused = player.nearest_interactable()
	var ground := floor_under(player)
	var shown := 0
	for node in get_tree().get_nodes_in_group("interactable"):
		if node == focused or not node is Node3D or not node.has_method("interact") or not node.is_visible_in_tree():
			continue
		if node.global_position.distance_to(player.global_position) > HINT_RADIUS:
			continue
		var hint := _hint(shown)
		hint.global_position = _over(node, ground) + Vector3(0, 0.35 + 0.06 * sin(clock * 2.0 + shown), 0)
		hint.visible = true
		shown += 1
	for index in range(shown, hints.size()):
		hints[index].visible = false
	if focused == null:
		ring.visible = false
		marker.visible = false
		return
	var pulse := sin(clock * 4.0)
	var under := floor_under(focused)
	marker.global_position = _over(focused, under) + Vector3(0, 0.55 + 0.1 * pulse, 0)
	ring.global_position = Vector3(focused.global_position.x, under + 0.03, focused.global_position.z)
	ring.scale = Vector3.ONE * (1.0 + 0.07 * pulse)
	ring.material_override.albedo_color.a = 0.65 + 0.25 * pulse
	ring.visible = true
	marker.visible = true

func _hint(index: int) -> MeshInstance3D:
	while hints.size() <= index:
		var hint := MeshInstance3D.new()
		var dot := SphereMesh.new()
		dot.radius = 0.13
		dot.height = 0.26
		hint.mesh = dot
		hint.material_override = _glow(SOFT, true)
		hint.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(hint)
		hints.append(hint)
	return hints[index]

func _hide_all() -> void:
	focused = null
	if ring != null:
		ring.visible = false
		marker.visible = false
	for hint in hints:
		hint.visible = false

func _over(node: Node3D, ground: float) -> Vector3:
	var top := top_of(node)
	return Vector3(top.x, minf(top.y, ground + MAX_HEIGHT), top.z)

func top_of(node: Node3D) -> Vector3:
	var id := node.get_instance_id()
	if not heights.has(id):
		heights[id] = _height(node)
	return node.global_position + Vector3(0, heights[id], 0)

func _height(node: Node3D) -> float:
	## The top of an object's own meshes or collision (visible or not: some are stand-ins for the art).
	var top := -INF
	for mesh in node.find_children("*", "MeshInstance3D", true, false):
		top = maxf(top, (mesh.global_transform * mesh.get_aabb()).end.y)
	for shape_node in node.find_children("*", "CollisionShape3D", true, false):
		if shape_node.shape != null:
			top = maxf(top, (shape_node.global_transform * shape_node.shape.get_debug_mesh().get_aabb()).end.y)
	if top == -INF:
		return 1.2
	return clampf(top - node.global_position.y, 0.3, 2.6)

func floor_under(node: Node3D) -> float:
	## Whatever the object stands on (the floor, a desk), not the object's own collision.
	var from := (top_of(node) if node != player else player.global_position) + Vector3(0, 0.1, 0)
	var query := PhysicsRayQueryParameters3D.create(from, from + Vector3.DOWN * 6.0)
	query.exclude = [player.get_rid()] + ([node.get_rid()] if node is CollisionObject3D else [])
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	return hit.position.y if not hit.is_empty() else player.global_position.y - 0.9
