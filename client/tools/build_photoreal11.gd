extends SceneTree
## Offline authoring of the Visual 0.11 district: replaces box-built houses with
## the Blender GLBs from tools/blender/jp_houses.py. No gameplay or server writes.
## Needs a real renderer (omit --headless) so existing MultiMesh buffers survive.
const SOURCE := "res://art/reference09/Neighborhood.tscn"
const DEST := "res://art/photoreal11/Neighborhood.tscn"
const INSTANCE := preload("res://scripts/art/PhotorealInstance.gd")
const HOUSES := {
	"ReferenceStreet/HouseA": "res://art/photoreal11/houses/jp_house_a.glb",
	"ReferenceStreet/HouseB": "res://art/photoreal11/houses/jp_house_b.glb",
}
# Ridge plus TV aerial: tall enough for the cutaway's line-of-sight test.
const HOUSE_HEIGHT := 8.8
const SPECS := "res://tools/blender/photoreal11_buildings.json"
const BUILDINGS := "res://art/photoreal11/buildings/"
const POLE := "res://art/photoreal11/props/jp_pole.glb"
const CABLE := "res://art/photoreal11/materials/cable_black.tres"
# Same pole positions as City08 street_life(); their collisions are kept.
const POLE_LINES := {-4.65: [8.5, -10.0, -33.5, -57.0, -69.5, -94.0], 33.2: [8.5, -10.0, -33.5, -57.0, -69.5, -94.0]}
# Attachment points relative to the pole base (see tools/blender/jp_pole.py).
const HIGH_WIRES := [Vector3(-0.75, 10.39, 0), Vector3(0, 10.39, 0), Vector3(0.75, 10.39, 0)]
const LOW_WIRES := [Vector3(-0.75, 9.69, 0), Vector3(0, 9.69, 0), Vector3(0.75, 9.69, 0)]
const TELECOM := Vector3(-0.2, 6.2, 0)
const SERVICE := Vector3(0.36, 8.3, 0)
# Service drops: pole base -> point under the eave of each new house.
const DROPS := [[Vector3(-4.65, 0, -10.0), Vector3(-6.3, 4.95, -8.9)], [Vector3(-4.65, 0, 8.5), Vector3(-6.3, 4.85, -1.4)]]

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	if DisplayServer.get_name() == "headless":
		push_error("Author with a real renderer; omit --headless.")
		quit(1)
		return
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var city: Node3D = load(SOURCE).instantiate()
	root.add_child(city)
	for path in HOUSES:
		replace_house(city, city.get_node(path), HOUSES[path])
	var blocks := replace_blocks(city)
	add_surroundings(city)
	var hidden := hide_old_utilities(city)
	print("PHOTOREAL11_BLOCKS ", blocks)
	add_power_lines(city)
	print("PHOTOREAL11_OLD_UTILITY_PIECES_HIDDEN ", hidden)
	await process_frame
	await RenderingServer.frame_post_draw
	root.remove_child(city)
	var packed := PackedScene.new()
	if packed.pack(city) != OK or ResourceSaver.save(packed, DEST) != OK:
		push_error("Cannot save photoreal district")
		quit(1)
		return
	print("PHOTOREAL11_BUILT houses=", HOUSES.size())
	city.free()
	quit()

func replace_house(city: Node3D, building: Node3D, glb: String) -> void:
	var upper := building.get_node("Upper")
	for child in upper.get_children():
		child.free()
	for child in building.get_children():
		if child != upper:
			child.free()
	var bounds: AABB = building.bounds
	building.bounds = AABB(bounds.position, Vector3(bounds.size.x, HOUSE_HEIGHT, bounds.size.z))
	var centre := Vector3(bounds.get_center().x, 0, bounds.get_center().z)
	for shadow_only in [false, true]:
		var model: Node3D = load(glb).instantiate()
		model.name = "ShadowCaster11" if shadow_only else "House11"
		model.position = centre
		model.set_script(INSTANCE)
		model.shadow_only = shadow_only
		(building if shadow_only else upper).add_child(model)
		model.owner = city

## Parametric blocks from tools/blender/jp_block.py, one GLB per plot. Specs are
## written by tools/photoreal11_specs.py; each GLB is modelled facing local +Z.
func replace_blocks(city: Node3D) -> int:
	var specs: Array = JSON.parse_string(FileAccess.get_file_as_string(SPECS))
	for spec in specs:
		var building := city.get_node(str(spec.node)) as Node3D
		var upper := building.get_node("Upper")
		var labels: Array[Label3D] = []
		for child in upper.get_children():
			if child is Label3D:
				upper.remove_child(child)
				labels.append(child)
			else:
				child.free()
		for child in building.get_children():
			if child != upper:
				child.free()
		var turn := Basis(Vector3.UP, deg_to_rad(float(spec.rotation_deg)))
		var centre := Vector3(float(spec.centre[0]), 0, float(spec.centre[1]))
		var top := 0.0
		for shadow_only in [false, true]:
			var model: Node3D = load(BUILDINGS + str(spec.name) + ".glb").instantiate()
			model.name = "ShadowCaster11" if shadow_only else "Block11"
			model.position = centre
			model.basis = turn
			model.set_script(INSTANCE)
			model.shadow_only = shadow_only
			(building if shadow_only else upper).add_child(model)
			model.owner = city
			for mesh in model.find_children("*", "MeshInstance3D"):
				top = maxf(top, (mesh as MeshInstance3D).get_aabb().end.y)
		var bounds: AABB = building.bounds
		building.bounds = AABB(bounds.position, Vector3(bounds.size.x, maxf(bounds.size.y, top), bounds.size.z))
		place_labels(city, upper, labels, spec, centre, turn)
	return specs.size()

func place_labels(city: Node3D, upper: Node, labels: Array[Label3D], spec: Dictionary, centre: Vector3, turn: Basis) -> void:
	var front := float(spec.depth) / 2.0
	var door := float(spec.door_a)
	var dark_sign := str(spec.get("sign", "sign_cream")) == "sign_dark" or str(spec.kind) == "club"
	var glass_slots := [door - 1.45, door + 1.45]
	var lanterns := [door - 1.3, door + 1.3]
	for label in labels:
		var local := Vector3.INF
		match str(label.name):
			"NewShopName", "ClubTitle", "StationTitle":
				# Centre of the sign band authored by jp_block.py build_shop().
				local = Vector3(0, 3.77, front + 0.21)
				label.modulate = Color("ece2c8") if dark_sign else Color("2b2824")
			"ClubSubtitle":
				local = Vector3(0, 3.52, front + 0.21)
				label.modulate = Color("62d3ff")
			"Menu", "VideoPoster", "CafeWindow":
				if not glass_slots.is_empty():
					local = Vector3(glass_slots.pop_front(), 1.55, front - 0.42)
			"Lantern", "Lantern2":
				if not lanterns.is_empty():
					local = Vector3(lanterns.pop_front(), 2.3, front + 1.02)
			"SchoolTitle":
				local = Vector3(door, 3.55, front + 1.95)
			"SchoolSub":
				local = Vector3(door, 3.2, front + 2.03)
		if local == Vector3.INF:
			label.free()  # house numbers would float in front of the new facades
			continue
		label.transform = Transform3D(turn, centre + turn * local)
		upper.add_child(label)
		label.owner = city

## Ground and a ring of non-playable buildings beyond the district bounds, so
## the camera never looks past the edge of the world at the sky.
func add_surroundings(city: Node3D) -> void:
	var holder := Node3D.new()
	holder.name = "Surroundings11"
	city.add_child(holder)
	holder.owner = city
	var ground := MeshInstance3D.new()
	ground.name = "OuterGround"
	var plane := PlaneMesh.new()
	plane.size = Vector2(420, 420)
	ground.mesh = plane
	ground.position = Vector3(0, -0.03, -48)
	ground.material_override = load("res://art/photoreal11/materials/sidewalk.tres")
	holder.add_child(ground)
	ground.owner = city
	var rng := RandomNumberGenerator.new()
	rng.seed = 1111
	# Houses face +X in their GLB; blocks face +Z. Angle turns each toward the district.
	var houses := ["res://art/photoreal11/houses/jp_house_a.glb", "res://art/photoreal11/houses/jp_house_b.glb", BUILDINGS + "blk_outerm1_0_0.glb"]
	var blocks := [BUILDINGS + "blk_outerm1_0_1.glb", BUILDINGS + "blk_outerm1_0_2.glb", BUILDINGS + "blk_skyline3.glb", BUILDINGS + "blk_outer1_0_4.glb"]
	var rows := [
		# [start, step, count, fixed axis value, along x?, house angle, block angle]
		[-42.0, 10.5, 9, 26.0, true, PI / 2, PI],
		[-106.0, 11.0, 12, -55.0, false, 0.0, PI / 2],
		[-106.0, 11.0, 12, 55.0, false, PI, -PI / 2],
		[-44.0, 11.0, 9, -137.0, true, -PI / 2, 0.0],
	]
	for row in rows:
		for i in range(int(row[2])):
			var along: float = row[0] + i * row[1] + rng.randf_range(-1.0, 1.0)
			var at: Vector3 = Vector3(along, 0, row[3]) if row[4] else Vector3(row[3], 0, along)
			var is_house: bool = rng.randf() < 0.5 and float(row[3]) != -137.0
			var path: String = houses[rng.randi() % houses.size()] if is_house else blocks[rng.randi() % blocks.size()]
			var model: Node3D = load(path).instantiate()
			model.name = "Filler11_" + str(holder.get_child_count())
			model.position = at
			model.rotation.y = float(row[5] if is_house else row[6])
			holder.add_child(model)
			model.owner = city

## Old poles and cables are baked into shared per-material MultiMeshes; collapse
## just the instances that belong to them. Their StaticBody collisions remain.
func hide_old_utilities(node: Node) -> int:
	var count := 0
	if node is MultiMeshInstance3D and node.multimesh != null:
		var mm: MultiMesh = node.multimesh
		for i in range(mm.instance_count):
			var world: Transform3D = node.global_transform * mm.get_instance_transform(i)
			if is_old_utility(world.origin):
				mm.set_instance_transform(i, Transform3D(Basis().scaled(Vector3.ZERO), node.global_transform.affine_inverse() * Vector3(0, -50, 0)))
				count += 1
	for child in node.get_children():
		count += hide_old_utilities(child)
	return count

func is_old_utility(p: Vector3) -> bool:
	for x in POLE_LINES:
		var line: Array = POLE_LINES[x]
		for z in line:
			if p.y > .25 and Vector2(p.x - x, p.z - z).length() < 1.35:
				return true
		# Old 6.7 m wires between poles.
		if absf(p.x - x) < 1.1 and p.y > 5.3 and p.y < 7.1 and p.z < line.max() + 1 and p.z > line.min() - 1:
			return true
	# Old service drop from the pole to the reference houses.
	return p.x > -6.4 and p.x < -4.2 and p.y > 4.4 and p.y < 5.6 and p.z > -10.2 and p.z < -5.6

func add_power_lines(city: Node3D) -> void:
	var holder := Node3D.new()
	holder.name = "PowerLines11"
	city.add_child(holder)
	holder.owner = city
	var tool := SurfaceTool.new()
	tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	for x in POLE_LINES:
		var zs: Array = POLE_LINES[x]
		# The street light arm faces the carriageway.
		var facing := 0.0 if x < 0 else PI
		var previous := Vector3.INF
		for z in zs:
			var base := Vector3(x, 0, z)
			var pole: Node3D = load(POLE).instantiate()
			pole.name = "Pole11_" + str(holder.get_child_count())
			pole.position = base
			pole.rotation.y = facing
			holder.add_child(pole)
			pole.owner = city
			if previous != Vector3.INF:
				# Radii are ~1.5x real so the wires survive TAA at the isometric zoom.
				var span := base.distance_to(previous)
				for offset in HIGH_WIRES + LOW_WIRES:
					var o: Vector3 = Basis(Vector3.UP, facing) * offset
					wire(tool, previous + o, base + o, span * .018, .015)
				var t: Vector3 = Basis(Vector3.UP, facing) * TELECOM
				wire(tool, previous + t, base + t, span * .03, .026)
			previous = base
	for drop in DROPS:
		for k in [-0.12, 0.12]:
			wire(tool, drop[0] + SERVICE + Vector3(0, 0, k), drop[1] + Vector3(0, 0, k), .35, .012)
	tool.generate_normals()
	var lines := MeshInstance3D.new()
	lines.name = "Wires"
	lines.mesh = tool.commit()
	lines.material_override = load(CABLE)
	holder.add_child(lines)
	lines.owner = city

## Catenary-like sagging tube between two attachment points.
func wire(tool: SurfaceTool, a: Vector3, b: Vector3, sag: float, radius: float) -> void:
	var steps := 24
	var sides := 6
	var rings: Array[PackedVector3Array] = []
	for i in range(steps + 1):
		var t := float(i) / steps
		var centre := a.lerp(b, t) - Vector3.UP * (4.0 * sag * t * (1.0 - t))
		var ahead := a.lerp(b, minf(t + .01, 1.0)) - Vector3.UP * (4.0 * sag * minf(t + .01, 1.0) * (1.0 - minf(t + .01, 1.0)))
		var behind := a.lerp(b, maxf(t - .01, 0.0)) - Vector3.UP * (4.0 * sag * maxf(t - .01, 0.0) * (1.0 - maxf(t - .01, 0.0)))
		var tangent := (ahead - behind).normalized()
		var side := tangent.cross(Vector3.UP).normalized()
		var up := side.cross(tangent).normalized()
		var ring := PackedVector3Array()
		for s in range(sides):
			var angle := TAU * s / sides
			ring.append(centre + (side * cos(angle) + up * sin(angle)) * radius)
		rings.append(ring)
	for i in range(steps):
		for s in range(sides):
			var n := (s + 1) % sides
			# Clockwise seen from outside: Godot's front-face winding.
			for v in [rings[i][s], rings[i + 1][n], rings[i + 1][s], rings[i][s], rings[i][n], rings[i + 1][n]]:
				tool.add_vertex(v)
