extends Node3D
## Shows what can be used, quietly. The one that E (A on the controller) would use
## right now gets a soft glow along its own silhouette when it has a visible shape
## (a person, an object), or a faint glow on the floor when it is only a place (a
## doorway), and a small key to press above it. Everything else usable nearby gets
## a tiny dim light. The player's own rule (IsoController.nearest_interactable) picks
## it, so the marked object is exactly the one that answers. Nothing shows while the
## player is held by a window, a terminal or a cinematic.
const HINT_RADIUS := 6.0
const MAX_HEIGHT := 1.6  # marks float at most this far above the floor (doorways have tall collisions)
const AMBER := Color("e0b45a")
const SOFT := Color(0.88, 0.71, 0.35, 0.35)
# A light along the edges of the shape (fresnel), added over its own materials.
const RIM_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back;
uniform vec3 rim_color : source_color = vec3(0.88, 0.71, 0.35);
uniform float strength = 0.5;
void fragment() {
	float rim = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 2.5);
	ALBEDO = rim_color * rim * strength;
}
"""
# A faint round glow on the floor, fading out to nothing at its edge.
const GLOW_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled;
uniform vec3 glow_color : source_color = vec3(0.88, 0.71, 0.35);
uniform float strength = 0.3;
void fragment() {
	float d = distance(UV, vec2(0.5)) * 2.0;
	ALBEDO = glow_color * smoothstep(1.0, 0.0, d) * strength;
}
"""

var player: Node3D
var ring: MeshInstance3D  # the floor glow, for places without a visible shape
var marker: Node3D
var prompt: Label3D
var hints: Array[MeshInstance3D] = []
var focused: Node3D
var rim: ShaderMaterial
var outlined := {}  # MeshInstance3D -> the overlay it had before
var heights := {}  # instance id -> how far above its origin an object's top is
var clock := 0.0

func _ready() -> void:
	top_level = true  # markers live in world space, not in the player's
	player = get_parent()
	rim = ShaderMaterial.new()
	rim.shader = Shader.new()
	rim.shader.code = RIM_SHADER
	ring = MeshInstance3D.new()
	var disc := PlaneMesh.new()
	disc.size = Vector2(1.3, 1.3)
	ring.mesh = disc
	var glow := ShaderMaterial.new()
	glow.shader = Shader.new()
	glow.shader.code = GLOW_SHADER
	ring.material_override = glow
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(ring)
	marker = Node3D.new()
	add_child(marker)
	prompt = Label3D.new()
	prompt.text = "[%s]" % Gamepad.label("interact")  # Gamepad swaps [E] and [A] on every Label3D
	prompt.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	prompt.no_depth_test = true
	prompt.font_size = 40
	prompt.pixel_size = 0.007
	prompt.outline_size = 10
	prompt.modulate = Color(AMBER, 0.85)
	marker.add_child(prompt)
	_hide_all()

func _glow(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = color
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.no_depth_test = true
	return material

func _process(delta: float) -> void:
	clock += delta
	if not is_instance_valid(player) or not player.is_inside_tree() or not player.is_physics_processing() \
			or not player.has_method("nearest_interactable"):
		_hide_all()
		return
	var now: Node3D = player.nearest_interactable()
	if now != focused:
		_outline(now)
	focused = now
	var ground := floor_under(player)
	var shown := 0
	for node in get_tree().get_nodes_in_group("interactable"):
		if node == focused or not node is Node3D or not node.has_method("interact") or not node.is_visible_in_tree():
			continue
		if node.global_position.distance_to(player.global_position) > HINT_RADIUS:
			continue
		var hint := _hint(shown)
		hint.global_position = _over(node, ground) + Vector3(0, 0.3 + 0.04 * sin(clock * 2.0 + shown), 0)
		hint.visible = true
		shown += 1
	for index in range(shown, hints.size()):
		hints[index].visible = false
	if focused == null:
		ring.visible = false
		marker.visible = false
		return
	var pulse := sin(clock * 2.5)
	rim.set_shader_parameter("strength", 0.45 + 0.15 * pulse)
	var under := floor_under(focused)
	marker.global_position = _over(focused, under) + Vector3(0, 0.4 + 0.05 * pulse, 0)
	marker.visible = true
	# A place with no visible shape of its own (a doorway) gets the faint floor glow instead.
	ring.visible = outlined.is_empty()
	if ring.visible:
		ring.global_position = Vector3(focused.global_position.x, under + 0.03, focused.global_position.z)
		ring.material_override.set_shader_parameter("strength", 0.25 + 0.08 * pulse)

func _outline(node: Node3D) -> void:
	## Move the silhouette glow to another object (or to none).
	for mesh in outlined:
		if is_instance_valid(mesh):
			mesh.material_overlay = outlined[mesh]
	outlined.clear()
	if node == null:
		return
	for mesh in node.find_children("*", "MeshInstance3D", true, false):
		if mesh.is_visible_in_tree():
			outlined[mesh] = mesh.material_overlay
			mesh.material_overlay = rim

func _hint(index: int) -> MeshInstance3D:
	while hints.size() <= index:
		var hint := MeshInstance3D.new()
		var dot := SphereMesh.new()
		dot.radius = 0.06
		dot.height = 0.12
		hint.mesh = dot
		hint.material_override = _glow(SOFT)
		hint.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(hint)
		hints.append(hint)
	return hints[index]

func _hide_all() -> void:
	_outline(null)
	focused = null
	if ring != null:
		ring.visible = false
		marker.visible = false
	for hint in hints:
		hint.visible = false

func _exit_tree() -> void:
	_outline(null)

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
