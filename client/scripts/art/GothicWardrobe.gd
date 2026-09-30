extends RefCounted
## Visual 0.12 gothic wardrobe for the articulated character rig (LainSlender).
## Recolours rig parts and adds coats, mohawks and spiked collars sized from
## each part's own bounds. Presentation only; never touches collision or state.

const SKIN := ["e7dad5", "dccabf", "cdb6a6", "ebe0da", "c9ab98"]
const CLOTH := ["17161b", "2a2230", "3b1419", "22252a", "2d2924", "3f1b2a", "1d272c"]
const HAIR := ["141013", "1c1416", "6a1220", "3a2250", "cfc7bf", "2a1a14"]
const PUNK := ["b0122a", "6d2bd6", "1fbf8f", "d6d0c4"]

static func paint(rig: Node, path: String, colour: Color, rough: float = 0.7, metal: float = 0.0, glow: float = 0.0) -> void:
	var mesh := rig.get_node_or_null(path) as MeshInstance3D
	if mesh == null or mesh.material_override == null:
		return
	var m := mesh.material_override.duplicate() as StandardMaterial3D
	m.albedo_color = colour
	m.roughness = rough
	m.metallic = metal
	if glow > 0.0:
		m.emission_enabled = true
		m.emission = colour
		m.emission_energy_multiplier = glow
	mesh.material_override = m

static func paint_all(rig: Node, paths: Array, colour: Color, rough: float = 0.7, metal: float = 0.0) -> void:
	for path in paths:
		paint(rig, path, colour, rough, metal)

const SKIN_PARTS := ["Face", "Neck", "Nose", "LeftArm/Hand", "RightArm/Hand"]
const HAIR_PARTS := ["BobHair", "LongSideLock", "FringeLeft", "FringeRight"]
const LEGS := ["LeftLeg/Thigh", "RightLeg/Thigh", "LeftLeg/Knee/Calf", "RightLeg/Knee/Calf"]
const SOCKS := ["LeftLeg/Knee/Sock", "RightLeg/Knee/Sock"]
const SHOES := ["LeftLeg/Knee/Loafer", "RightLeg/Knee/Loafer"]
const SOLES := ["LeftLeg/Knee/Sole", "RightLeg/Knee/Sole"]

static func dress_player(rig: Node) -> void:
	# Lain, gothic: pale, crimson eyes and collar, black blouse, skirt and tights.
	paint_all(rig, SKIN_PARTS, Color("e8dcd8"), 0.55)
	paint_all(rig, HAIR_PARTS, Color("24181a"), 0.45)
	paint(rig, "HairClip", Color("8e1022"), 0.3, 0.8)
	paint(rig, "Iris", Color("a5162a"), 0.3, 0.0, 0.6)
	paint(rig, "Iris2", Color("a5162a"), 0.3, 0.0, 0.6)
	paint_all(rig, ["Brow", "Brow2", "UpperLid", "UpperLid2"], Color("16100f"), 0.6)
	paint(rig, "Mouth", Color("4e0f1a"), 0.35)
	paint_all(rig, ["TailoredBlouse", "LeftArm/Sleeve", "RightArm/Sleeve"], Color("141216"), 0.55)
	paint_all(rig, ["Collar", "Collar2", "Ribbon", "BlouseSeam", "LeftArm/Cuff", "RightArm/Cuff"], Color("7a0f1e"), 0.45)
	paint(rig, "PleatedSkirt", Color("1c1720"), 0.6)
	paint(rig, "Waistband", Color("0e0d10"), 0.4, 0.5)
	paint_all(rig, ["Satchel", "SatchelStrap", "SatchelStrap2"], Color("15110f"), 0.35)
	paint_all(rig, LEGS + SOCKS, Color("111014"), 0.5)
	paint_all(rig, SHOES, Color("0b0a0c"), 0.18, 0.35)
	paint_all(rig, SOLES, Color("050505"), 0.8)
	spiked_collar(rig, Color("0d0c0e"))

static func dress_citizen(rig: Node, kind: String, variant: int) -> void:
	var seed := variant * 7 + kind.length()
	var cloth := Color(CLOTH[posmod(seed, CLOTH.size())])
	paint_all(rig, SKIN_PARTS, Color(SKIN[posmod(seed * 3, SKIN.size())]), 0.6)
	var hair := Color(HAIR[posmod(seed * 5, HAIR.size())])
	if kind == "elder":
		hair = Color("b9b3ad")
	paint_all(rig, HAIR_PARTS, hair, 0.5)
	paint_all(rig, ["TailoredBlouse", "LeftArm/Sleeve", "RightArm/Sleeve"], cloth, 0.6)
	paint_all(rig, ["Collar", "Collar2", "BlouseSeam", "LeftArm/Cuff", "RightArm/Cuff"], cloth.darkened(0.35), 0.5)
	paint(rig, "PleatedSkirt", cloth.darkened(0.2), 0.6)
	paint_all(rig, LEGS + SOCKS, Color("121115"), 0.55)
	paint_all(rig, SHOES, Color("0c0b0d"), 0.25, 0.3)
	if kind in ["worker", "teacher", "suit", "elder"] or variant % 4 == 1:
		long_coat(rig, Color(["0e0d10", "1c1416", "241c1a", "171c20"][posmod(seed, 4)]))
	if kind == "student" and variant % 3 == 0 or kind == "worker" and variant % 5 == 2:
		mohawk(rig, Color(PUNK[posmod(seed, PUNK.size())]))
		spiked_collar(rig, Color("101012"))
	elif variant % 6 == 3:
		spiked_collar(rig, Color("101012"))

static func bounds(rig: Node, path: String) -> AABB:
	var mesh := rig.get_node_or_null(path) as MeshInstance3D
	return mesh.get_aabb() if mesh != null and mesh.mesh != null else AABB()

static func accessory(rig: Node, label: String, mesh: PrimitiveMesh, at: Vector3, colour: Color, rough: float, metal: float = 0.0) -> MeshInstance3D:
	var part := MeshInstance3D.new()
	part.name = label
	# Baked to ArrayMesh like the sculpted rig parts (check_character06 expects no primitives).
	var baked := ArrayMesh.new()
	baked.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, mesh.get_mesh_arrays())
	part.mesh = baked
	part.position = at
	var m := StandardMaterial3D.new()
	m.albedo_color = colour
	m.roughness = rough
	m.metallic = metal
	part.material_override = m
	rig.add_child(part)
	return part

static func long_coat(rig: Node, colour: Color) -> void:
	var torso := bounds(rig, "TailoredBlouse")
	if torso.size == Vector3.ZERO or rig.has_node("GothicCoat"):
		return
	var coat := CylinderMesh.new()
	var width := maxf(torso.size.x, torso.size.z) * 0.56
	coat.top_radius = width
	coat.bottom_radius = width * 1.35
	coat.height = torso.size.y + 0.55
	coat.radial_segments = 12
	var top := torso.end.y - 0.01
	accessory(rig, "GothicCoat", coat, Vector3(torso.get_center().x, top - coat.height / 2, torso.get_center().z), colour, 0.42)
	var lapel := BoxMesh.new()
	lapel.size = Vector3(width * 1.9, 0.05, width * 1.9)
	accessory(rig, "GothicCoatCollar", lapel, Vector3(torso.get_center().x, top + 0.02, torso.get_center().z), colour.lightened(0.05), 0.4)

static func mohawk(rig: Node, colour: Color) -> void:
	var hair := bounds(rig, "BobHair")
	if hair.size == Vector3.ZERO or rig.has_node("Mohawk"):
		return
	var holder := Node3D.new()
	holder.name = "Mohawk"
	rig.add_child(holder)
	for i in range(6):
		var spike := CylinderMesh.new()
		spike.top_radius = 0.0
		spike.bottom_radius = 0.028
		spike.height = 0.1 + 0.05 * sin(float(i) / 5.0 * PI)
		spike.radial_segments = 6
		var z := lerpf(hair.position.z + 0.03, hair.end.z - 0.03, float(i) / 5.0)
		var part := accessory(holder, "Spike" + str(i), spike, Vector3(hair.get_center().x, hair.end.y + spike.height / 2 - 0.02, z), colour, 0.4)
		part.rotation.x = lerpf(-0.35, 0.35, float(i) / 5.0)

static func spiked_collar(rig: Node, colour: Color) -> void:
	var neck := bounds(rig, "Neck")
	if neck.size == Vector3.ZERO or rig.has_node("SpikedCollar"):
		return
	var ring := TorusMesh.new()
	var radius := maxf(neck.size.x, neck.size.z) * 0.55
	ring.inner_radius = radius
	ring.outer_radius = radius + 0.018
	var centre := Vector3(neck.get_center().x, neck.position.y + neck.size.y * 0.35, neck.get_center().z)
	var collar := accessory(rig, "SpikedCollar", ring, centre, colour, 0.35, 0.6)
	for i in range(8):
		var angle := TAU * i / 8.0
		var spike := CylinderMesh.new()
		spike.top_radius = 0.0
		spike.bottom_radius = 0.008
		spike.height = 0.03
		spike.radial_segments = 5
		var part := accessory(collar, "Stud" + str(i), spike, Vector3(cos(angle), 0, sin(angle)) * (radius + 0.02), Color("9a9aa2"), 0.3, 0.9)
		part.rotation = Vector3(0, -angle, -PI / 2)
