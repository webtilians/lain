extends Node3D
## The Indara net (ARTE.md): what lies outside the walls while the player is inside a
## building. The room floats in the dark over a net of light, hanging from it by cables at
## its corners. Each of the city's other zones is a jewel on the net, brighter while players
## are there; a pulse runs along the threads and up a cable into the room whenever someone
## arrives in a zone or a line is said aloud there, and one runs out of the room when
## something is said in it. Only counts, from the server through OnlinePresence: never who,
## nor what. Offline the net still breathes with slow pulses of its own. Presentation only.
const SHADER := preload("res://shaders/indara_net.gdshader")
const DRESSER := preload("res://scripts/art/InteriorDresser.gd")
const ISO := preload("res://scripts/player/IsoController.gd")
const CELL := 3.0  # metres between threads
const DEPTH := 7.0  # how far under the floor the net lies
const REACH := 34.0  # where it has faded into the dark
const SPEED := 8.0  # metres a second along the threads
const QUIET := Vector2(4.0, 9.0)  # seconds between the net's own pulses
const MOST := 14  # pulses on the net at once
const PRIVATE := ["APARTMENT"]  # nobody sees who is at home (online.PRIVATE_ROOMS)
# Where the zones' jewels sit, as seen on screen around the room (metres right and up from
# its centre): outside the room's silhouette under the isometric camera.
const SPOTS := [Vector2(-14, 3), Vector2(14, 3), Vector2(-10, -5.5), Vector2(10, -5.5), Vector2(-11, 8.5),
	Vector2(11, 8.5), Vector2(-5, -9.5), Vector2(5, -9.5), Vector2(-17, -2), Vector2(17, -2),
	Vector2(-6, 11), Vector2(6, 11)]
const VOICE := Color(1.9, 0.55, 1.5)  # a line said aloud
const ARRIVAL := Color(0.6, 1.5, 1.9)  # someone arrived
const BREATH := Color(0.35, 0.6, 1.2)  # the net's own pulse
const BEADS := [1.0, 0.75, 0.55, 0.4]  # a pulse's head and its fading trail

var location := ""
var level := 0.0  # the height of the net
var net: ShaderMaterial
var corners: Array[Vector3] = []  # where the cables leave the room
var feet: Array[Vector3] = []  # where they reach the net
var cables: Array[MeshInstance3D] = []
var knots := {}  # zone -> its jewel's knot on the net
var jewels := {}  # zone -> the jewel
var people := {}  # zone -> players there, as last heard
var said := {}  # zone -> lines said aloud there, as last heard
var heard := false
var pulses: Array[Dictionary] = []
var strength := 1.0
var clock := 0.0
var quiet := 2.0

func _ready() -> void:
	var presence := get_node_or_null("/root/OnlinePresence")
	if presence != null and presence.has_signal("indara_heard"):
		presence.indara_heard.connect(hear)

func setup(scene: Node3D, here: String) -> void:
	name = "IndaraNet"
	location = here
	var room: AABB = DRESSER.room_bounds(scene)
	var centre := room.get_center()
	level = room.position.y - DEPTH
	var back: Vector3 = -ISO.CAMERA_OFFSET.normalized()  # where the camera looks
	var right := back.cross(Vector3.UP).normalized()
	var up := right.cross(back).normalized()
	var seen := func(point: Vector3) -> Vector3:
		# The point of the net the camera sees behind this one.
		return point + back * ((level - point.y) / back.y)
	_threads(seen.call(centre))
	# The three bottom corners the camera sees: left, front and right.
	for corner in [Vector3(room.position.x, room.position.y, room.end.z), Vector3(room.end.x, room.position.y, room.end.z),
			Vector3(room.end.x, room.position.y, room.position.z)]:
		var outward := Vector3(signf(corner.x - centre.x), 0, signf(corner.z - centre.z))
		corners.append(corner)
		feet.append(_snap(corner + outward * CELL * 0.5))
		cables.append(_cable(corner, feet[-1]))
	var zones := []
	for zone in load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES:
		if zone != here and not zone in PRIVATE:
			zones.append(zone)
	zones.sort()
	for index in zones.size():
		var spot: Vector2 = SPOTS[index % SPOTS.size()] * (1.0 + 0.35 * floorf(float(index) / SPOTS.size()))
		var knot := _snap(seen.call(centre + right * spot.x + up * spot.y))
		knots[zones[index]] = knot
		jewels[zones[index]] = _jewel(knot)
		people[zones[index]] = 0
	_light_knots()

func set_look(anime: bool) -> void:
	## Fainter in the realistic look (F9).
	strength = 1.0 if anime else 0.6
	net.set_shader_parameter("strength", strength)

func hear(zones: Array) -> void:
	## What the server says of the city: players and lines said aloud in each public zone.
	var first := not heard
	heard = true
	var now := {}
	for item in zones:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var zone := str(item.get("zone", ""))
		var count := int(item.get("people", 0))
		var lines := int(item.get("said", 0))
		var new_lines := 0 if first else lines - int(said.get(zone, lines))
		if zone == location:
			for i in mini(new_lines, 2):
				_pulse(_path_out(), VOICE, i * 0.4)
		elif knots.has(zone):
			for i in mini(new_lines, 2):
				_pulse(_path_in(knots[zone]), VOICE, i * 0.4)
			if not first and count > int(people.get(zone, 0)):
				_pulse(_path_in(knots[zone]), ARRIVAL)
		said[zone] = lines
		now[zone] = count
	for zone in knots:
		people[zone] = int(now.get(zone, 0))
	_light_knots()

func _process(delta: float) -> void:
	clock += delta
	quiet -= delta
	if quiet <= 0.0:
		# Slower once the real city is heard, so its pulses stand out.
		quiet = randf_range(QUIET.x, QUIET.y) * (2.0 if heard else 1.0)
		if not knots.is_empty():
			_pulse(_path_in(knots[knots.keys().pick_random()]), BREATH)
	for jewel in jewels.values():
		jewel.rotate_y(delta * 0.6)
	for pulse in pulses.duplicate():
		var travelled: float = (clock - pulse.born) * SPEED
		var done := true
		for index in pulse.beads.size():
			var bead: MeshInstance3D = pulse.beads[index]
			var at: float = travelled - index * 0.35
			bead.visible = at > 0.0 and at < pulse.length
			done = done and at >= pulse.length
			if bead.visible:
				bead.position = _along(pulse.path, at)
		if done:
			for bead in pulse.beads:
				bead.queue_free()
			pulses.erase(pulse)

func _pulse(path: PackedVector3Array, colour: Color, delay: float = 0.0) -> void:
	if pulses.size() >= MOST or path.size() < 2:
		return
	var length := 0.0
	for index in range(1, path.size()):
		length += path[index - 1].distance_to(path[index])
	var beads: Array[MeshInstance3D] = []
	for size in BEADS:
		var bead := MeshInstance3D.new()
		var shape := SphereMesh.new()
		shape.radius = 0.13 * size
		shape.height = 0.26 * size
		shape.radial_segments = 8
		shape.rings = 4
		bead.mesh = shape
		bead.material_override = _glow(colour * size)
		bead.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		bead.visible = false
		add_child(bead)
		beads.append(bead)
	pulses.append({"path": path, "length": length, "born": clock + delay, "beads": beads, "colour": colour})

func _path_in(knot: Vector3) -> PackedVector3Array:
	## From a jewel along the threads to the nearest cable, and up it into the room.
	var nearest := 0
	for index in feet.size():
		if knot.distance_to(feet[index]) < knot.distance_to(feet[nearest]):
			nearest = index
	var foot := feet[nearest]
	return PackedVector3Array([knot, Vector3(foot.x, level, knot.z), foot, corners[nearest]])

func _path_out() -> PackedVector3Array:
	## Out of the room, down a cable and along the threads to one of the jewels.
	var path := _path_in(knots[knots.keys().pick_random()]) if not knots.is_empty() else PackedVector3Array()
	path.reverse()
	return path

func _along(path: PackedVector3Array, distance: float) -> Vector3:
	for index in range(1, path.size()):
		var step := path[index - 1].distance_to(path[index])
		if distance <= step:
			return path[index - 1].lerp(path[index], distance / maxf(step, 0.001))
		distance -= step
	return path[-1]

func _snap(point: Vector3) -> Vector3:
	return Vector3(roundf(point.x / CELL) * CELL, level, roundf(point.z / CELL) * CELL)

func _threads(centre: Vector3) -> void:
	var plane := MeshInstance3D.new()
	plane.name = "Threads"
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(REACH * 2.4, REACH * 2.4)
	plane.mesh = mesh
	plane.position = Vector3(centre.x, level, centre.z)
	plane.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	net = ShaderMaterial.new()
	net.shader = SHADER
	net.set_shader_parameter("cell", CELL)
	net.set_shader_parameter("centre", Vector2(centre.x, centre.z))
	net.set_shader_parameter("reach", REACH)
	plane.material_override = net
	add_child(plane)

func _cable(from: Vector3, to: Vector3) -> MeshInstance3D:
	var cable := MeshInstance3D.new()
	cable.name = "Cable"
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.04, 0.04, from.distance_to(to))
	cable.mesh = mesh
	cable.material_override = _glow(BREATH * 0.5)
	cable.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	cable.transform = Transform3D(Basis.looking_at(to - from, Vector3.RIGHT), (from + to) * 0.5)
	add_child(cable, true)
	return cable

func _jewel(knot: Vector3) -> MeshInstance3D:
	var jewel := MeshInstance3D.new()
	var shape := SphereMesh.new()
	shape.radius = 0.2
	shape.height = 0.5
	shape.radial_segments = 4
	shape.rings = 2
	jewel.mesh = shape
	jewel.material_override = _glow(ARRIVAL * 0.3)
	jewel.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	jewel.position = knot + Vector3(0, 0.45, 0)
	add_child(jewel)
	return jewel

func _light_knots() -> void:
	## Zones with players glow brighter; the cables' feet always a little.
	var lit := PackedVector4Array()
	for zone in knots:
		var count: int = people.get(zone, 0)
		var brightness := 0.05 if count == 0 else (0.55 if count == 1 else 0.85)
		lit.append(Vector4(knots[zone].x, knots[zone].z, brightness, 0))
		jewels[zone].material_override.albedo_color = ARRIVAL * (0.15 + brightness)
	for foot in feet:
		lit.append(Vector4(foot.x, foot.z, 0.2, 0))
	net.set_shader_parameter("knots", lit)
	net.set_shader_parameter("knot_count", lit.size())

func _glow(colour: Color) -> StandardMaterial3D:
	var glow := StandardMaterial3D.new()
	glow.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	glow.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	glow.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	glow.disable_fog = true
	glow.albedo_color = colour
	glow.set_meta("anime", true)  # AnimeLook leaves it as it is
	return glow
