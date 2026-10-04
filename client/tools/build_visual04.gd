extends SceneTree
## Offline authoring tool. Rebuilds saved original meshes, never accesses WorldApi.
var asset: Node3D
var mats: Dictionary = {}

func _initialize() -> void:
	call_deferred("build")

func mat(hex: String, emission: float = 0.0) -> StandardMaterial3D:
	var key := hex + str(emission)
	if mats.has(key):
		return mats[key]
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(hex)
	material.roughness = 0.9
	if emission > 0:
		material.emission_enabled = true
		material.emission = Color(hex)
		material.emission_energy_multiplier = emission
	mats[key] = material
	return material

func box(label: String, at: Vector3, size: Vector3, color: String, solid: bool = false) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	mesh.name = label
	var shape := BoxMesh.new()
	shape.size = size
	mesh.mesh = shape
	mesh.material_override = mat(color)
	mesh.position = at
	asset.add_child(mesh, true)
	if solid:
		var body := StaticBody3D.new()
		mesh.add_child(body)
		var collision := CollisionShape3D.new()
		var bounds := BoxShape3D.new()
		bounds.size = size
		collision.shape = bounds
		body.add_child(collision)
	return mesh

func ellipsoid(label: String, at: Vector3, size: Vector3, color: String) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	mesh.name = label
	var shape := SphereMesh.new()
	shape.radius = 0.5
	shape.height = 1.0
	shape.radial_segments = 20
	shape.rings = 12
	mesh.mesh = shape
	mesh.material_override = mat(color)
	mesh.position = at
	mesh.scale = size
	asset.add_child(mesh, true)
	return mesh

func cylinder(label: String, at: Vector3, radius: float, height: float, color: String, top: float = -1.0) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	mesh.name = label
	var shape := CylinderMesh.new()
	shape.bottom_radius = radius
	shape.top_radius = radius if top < 0 else top
	shape.height = height
	shape.radial_segments = 16
	mesh.mesh = shape
	mesh.material_override = mat(color)
	mesh.position = at
	asset.add_child(mesh, true)
	return mesh

func line(label: String, a: Vector3, b: Vector3, radius: float, color: String) -> void:
	var segment := cylinder(label, (a + b) * 0.5, radius, a.distance_to(b), color)
	segment.quaternion = Quaternion(Vector3.UP, (b - a).normalized())

func sign_text(label: String, text: String, at: Vector3, angle: float, size: int = 48) -> void:
	var sign := Label3D.new()
	sign.name = label
	sign.text = text
	sign.font_size = size
	sign.pixel_size = 0.008
	sign.modulate = Color("c4c4b9")
	sign.outline_size = 0
	sign.position = at
	sign.rotation.y = angle
	asset.add_child(sign)

func own(node: Node) -> void:
	for child in node.get_children():
		child.owner = asset
		own(child)

func save_asset(path: String) -> void:
	own(asset)
	var packed := PackedScene.new()
	if packed.pack(asset) != OK or ResourceSaver.save(packed, path) != OK:
		push_error("Asset save failed: " + path)
		quit(1)
	asset.free()

func begin(label: String) -> void:
	asset = Node3D.new()
	asset.name = label

func character() -> void:
	begin("Silhouette")
	asset.set_script(load("res://scripts/art/ApartmentAvatar.gd"))
	# Face is deliberately simple/readable at gameplay scale, facing local +Z.
	ellipsoid("Face", Vector3(0, 0.46, 0.018), Vector3(0.32, 0.39, 0.295), "ceb9ac")
	ellipsoid("HairCrown", Vector3(0, 0.575, -0.047), Vector3(0.37, 0.28, 0.33), "392c29")
	ellipsoid("BobBack", Vector3(0, 0.415, -0.1), Vector3(0.35, 0.32, 0.20), "3f302c")
	ellipsoid("ShortSide", Vector3(-0.146, 0.45, 0.01), Vector3(0.105, 0.24, 0.24), "392c29")
	ellipsoid("LongSideLock", Vector3(0.145, 0.295, 0.03), Vector3(0.09, 0.4, 0.16), "3c2e2b")
	for i in range(5):
		var fringe := ellipsoid("Fringe", Vector3(-0.12 + i * 0.053, 0.595 - (i % 3) * 0.017, 0.109), Vector3(0.09, 0.14, 0.075), "392c29")
		fringe.rotation.z = -0.24
	var clip := box("HairClip", Vector3(0.143, 0.415, 0.133), Vector3(0.025, 0.10, 0.018), "c7b995")
	clip.rotation.z = -0.2
	for x in [-0.072, 0.072]:
		ellipsoid("EyeWhite", Vector3(x, 0.475, 0.153), Vector3(0.056, 0.039, 0.01), "d5c8b6")
		ellipsoid("Iris", Vector3(x, 0.474, 0.16), Vector3(0.025, 0.03, 0.008), "372b32")
		box("UpperLid", Vector3(x, 0.494, 0.16), Vector3(0.055, 0.009, 0.009), "332b2d")
	ellipsoid("Nose", Vector3(0, 0.429, 0.158), Vector3(0.024, 0.032, 0.025), "c5a99a")
	box("Mouth", Vector3(0, 0.376, 0.159), Vector3(0.037, 0.006, 0.008), "9a7772")
	cylinder("Neck", Vector3(0, 0.263, 0), 0.064, 0.1, "ceb9ac")
	var shirt := cylinder("SchoolBlouse", Vector3(0, 0.025, 0), 0.19, 0.42, "7b7e80", 0.18)
	shirt.scale.z = 0.7
	for side in [-1, 1]:
		var collar := box("Collar", Vector3(side * 0.054, 0.21, 0.105), Vector3(0.095, 0.065, 0.025), "c8c9ba")
		collar.rotation.z = side * 0.45
		var sleeve := cylinder("Sleeve", Vector3(side * 0.224, 0.01, 0), 0.068, 0.42, "7b7e80", 0.071)
		sleeve.rotation.z = side * 0.075
		ellipsoid("Hand", Vector3(side * 0.241, -0.24, 0.005), Vector3(0.088, 0.13, 0.075), "ceb9ac")
	box("RedRibbon", Vector3(0, 0.13, 0.146), Vector3(0.048, 0.14, 0.024), "663d43")
	var skirt := cylinder("PleatedSkirt", Vector3(0, -0.31, 0), 0.25, 0.33, "424b45", 0.178)
	skirt.scale.z = 0.8
	for i in range(16):
		var angle := i * TAU / 16.0
		line("SkirtPleat", Vector3(sin(angle)*0.18, -0.15, cos(angle)*0.18*0.8), Vector3(sin(angle)*0.251, -0.47, cos(angle)*0.251*0.8), 0.008, "596055")
	for side in [-1, 1]:
		var leg := Node3D.new()
		leg.name = "LeftLeg" if side == -1 else "RightLeg"
		leg.position = Vector3(side * 0.105, -0.44, 0)
		asset.add_child(leg)
		var shin := cylinder("Shin", Vector3(0, -0.13, 0), 0.047, 0.27, "bca99e")
		shin.reparent(leg, false)
		var sock := cylinder("Sock", Vector3(0, -0.27, 0), 0.049, 0.1, "bbbcb0")
		sock.reparent(leg, false)
		var shoe := ellipsoid("Loafer", Vector3(0, -0.345, 0.045), Vector3(0.13, 0.115, 0.24), "302e30")
		shoe.reparent(leg, false)
	# Small school satchel, a recognizable silhouette even from behind.
	box("Satchel", Vector3(0, 0.035, -0.185), Vector3(0.27, 0.31, 0.12), "766559")
	for x in [-0.11, 0.11]:
		box("SatchelStrap", Vector3(x, 0.12, -0.11), Vector3(0.028, 0.32, 0.035), "ad9c80")
	save_asset("res://art/characters/LainInspired.tscn")

func district() -> void:
	begin("ResidentialStreet")
	for side in [-1, 1]:
		box("Sidewalk", Vector3(side * 2.05, 0.022, -10), Vector3(1.5, 0.035, 35.7), "9a9992")
		box("Kerb", Vector3(side * 1.32, 0.065, -10), Vector3(0.11, 0.09, 35.7), "bab9af")
		for z in range(-26, 8, 2):
			box("PavingJoint", Vector3(side * 2.05, 0.043, z), Vector3(1.45, 0.007, 0.022), "74757b")
			for slot in range(4):
				box("Drain", Vector3(side * 1.54, 0.05, z + slot*0.06), Vector3(0.24, 0.014, 0.027), "35353c")
	for z in range(-25, 7, 7):
		# Left houses lie behind the original collision boundary at x=-3.
		box("HouseFacade", Vector3(-3.05, 1.65, z), Vector3(0.08, 3.25, 6.1), "b4b4ae")
		box("HouseSill", Vector3(-2.97, 1.12, z), Vector3(0.12, 0.11, 2.25), "7a777b")
		box("WindowFrame", Vector3(-2.98, 1.9, z), Vector3(0.08, 1.5, 2.15), "55515d")
		box("WindowGlass", Vector3(-2.93, 1.9, z), Vector3(0.025, 1.35, 2.0), "858797")
		for offset in [-0.65, 0, 0.65]:
			box("WindowMullion", Vector3(-2.90, 1.9, z+offset), Vector3(0.02, 1.36, 0.036), "43434d")
		box("HouseDoor", Vector3(-2.94, 1.05, z+2.2), Vector3(0.08, 2.05, 0.98), "63616a")
		box("Mailbox", Vector3(-2.78, 1.18, z+1.42), Vector3(0.22, 0.26, 0.27), "6b6266")
		box("MailboxSlot", Vector3(-2.66, 1.21, z+1.42), Vector3(0.013, 0.018, 0.2), "242733")
		box("RoofEave", Vector3(-4.45, 3.31, z), Vector3(3.6, 0.12, 6.3), "48444d")
		for tile in range(13):
			box("RoofSeam", Vector3(-4.4, 3.38, z-2.85+tile*0.47), Vector3(3.3, 0.014, 0.025), "63606a")
		box("GardenWall", Vector3(3.0, 0.56, z), Vector3(0.18, 1.1, 5.7), "aeada7")
		box("GardenCoping", Vector3(3.0, 1.14, z), Vector3(0.3, 0.09, 5.85), "d0ccc0")
		for i in range(8):
			ellipsoid("Shrub", Vector3(3.62, 0.88, z-2.4+i*0.64), Vector3(0.95, 1.05+(i%3)*0.16, 0.9), "424947")
		for i in range(3):
			box("ConcreteJoint", Vector3(2.899, 0.24+i*0.29, z), Vector3(0.013, 0.015, 5.65), "777883")
	for z in [-22.0, -12.0, -2.0, 6.0]:
		for side in [-1, 1]:
			var x: float = side * 2.62
			cylinder("UtilityPole", Vector3(x, 2.5, z), 0.09, 5.0, "46434a")
			box("Crossarm", Vector3(x, 4.6, z), Vector3(1.0, 0.065, 0.09), "3c3c46")
			cylinder("Transformer", Vector3(x+0.16, 3.85, z), 0.16, 0.46, "72767d")
			for wire in [-0.38, 0.0, 0.38]:
				cylinder("Insulator", Vector3(x+wire, 4.73, z), 0.045, 0.19, "aaa9ac")
				if z < 6:
					var end := minf(z + 10, 6)
					var last := Vector3(x+wire, 4.82, z)
					for step in range(1, 9):
						var t := step/8.0
						var next := Vector3(x+wire, 4.82-sin(t*PI)*0.6, lerpf(z,end,t))
						line("OverheadWire", last, next, 0.011, "272832")
						last = next
		line("CrossStreetWire", Vector3(-2.62,4.35,z), Vector3(2.62,4.35,z-0.8), 0.012, "272832")
	# The portals preserve their gameplay position, now framed as actual entrances.
	box("StationGateway", Vector3(0, 2.9, -26.9), Vector3(4.8, 0.18, 0.8), "545b61")
	for x in [-2.0, 2.0]:
		box("StationGatewayPost", Vector3(x, 1.4, -26.9), Vector3(0.15, 2.8, 0.2), "737778")
	box("ApartmentEntryFrame", Vector3(0,2.42,7.8), Vector3(2.4,0.13,0.25), "77717a")
	save_asset("res://art/visual04/ResidentialStreet.tscn")

func resident(is_k: bool) -> void:
	begin("Resident")
	var cloth := "414b59" if is_k else "806e79"
	var hair := "292a30" if is_k else "544038"
	ellipsoid("Face", Vector3(0,1.53,0.02), Vector3(0.31,0.39,0.29), "bca99a")
	ellipsoid("Hair", Vector3(0,1.67,-0.035), Vector3(0.35,0.22,0.32), hair)
	if not is_k:
		ellipsoid("Bob", Vector3(0,1.48,-0.095), Vector3(0.37,0.38,0.21), hair)
	for side in [-1,1]:
		box("Eye", Vector3(side*0.063,1.55,0.16), Vector3(0.038,0.014,0.008), "302c33")
		cylinder("Sleeve", Vector3(side*0.247,1.10,0), 0.074,0.52,cloth)
		ellipsoid("Hand", Vector3(side*0.247,0.795,0.01), Vector3(0.095,0.14,0.08), "bca99a")
		cylinder("Trouser", Vector3(side*0.107,0.385,0), 0.08,0.65,"383d48")
		ellipsoid("Shoe", Vector3(side*0.107,0.075,0.045), Vector3(0.17,0.14,0.28), "292b32")
	cylinder("Neck", Vector3(0,1.33,0),0.06,0.15,"bca99a")
	var coat := cylinder("Coat",Vector3(0,1.005,0),0.225,0.66,cloth,0.205)
	coat.scale.z = 0.72
	box("Shirt",Vector3(0,1.26,0.149),Vector3(0.1,0.17,0.018),"b4b1a8")
	for side in [-1,1]:
		var lapel := box("Lapel",Vector3(side*0.082,1.23,0.158),Vector3(0.07,0.22,0.03),"62626b" if is_k else "a39196")
		lapel.rotation.z=side*0.28
	if is_k:
		box("Tie",Vector3(0,1.20,0.168),Vector3(0.035,0.17,0.015),"473642")
	else:
		box("Bag",Vector3(0.28,0.72,0.06),Vector3(0.15,0.28,0.3),"67574f")
		line("BagStrap",Vector3(-0.15,1.3,0.19),Vector3(0.26,0.79,0.17),0.014,"aa9586")
	save_asset("res://art/characters/AgentK.tscn" if is_k else "res://art/characters/Nora.tscn")

func station() -> void:
	begin("StationDressing")
	for z in range(-10, 11):
		for x in range(-4, 2):
			box("PlatformSlab", Vector3(x-0.2,0.015,z), Vector3(0.985,0.02,0.985), "777b79" if (x+z)%3 else "707674")
		box("TactileStrip", Vector3(1.43,0.047,z), Vector3(0.31,0.06,0.98), "a9a58a")
		for i in range(4):
			box("TactileRidge", Vector3(1.32+i*0.075,0.083,z), Vector3(0.026,0.018,0.91), "c5bca0")
	for i in range(34):
		box("RailSleeper", Vector3(3,0.073,-9+i*0.52), Vector3(2.4,0.07,0.18), "514b4c")
	for z in [-8.0, -1.0, 6.0]:
		box("CanopyPost", Vector3(-4.32,1.63,z), Vector3(0.13,3.25,0.13), "5b6367", true)
		box("CanopyBeam", Vector3(-2.0,3.24,z), Vector3(4.8,0.13,0.1), "666e71")
		box("FixtureHousing", Vector3(-1.45,3.11,z), Vector3(1.8,0.08,0.2), "363f46")
		var tube := box("Fluorescent", Vector3(-1.45,3.05,z), Vector3(1.64,0.04,0.075), "b4c7b9")
		tube.material_override = mat("b4c7b9", 0.7)
		var light := OmniLight3D.new()
		light.position = Vector3(-1.45,2.85,z)
		light.light_color = Color("a9bdba")
		light.light_energy = 0.8
		light.omni_range = 5.3
		asset.add_child(light)
		box("CanopyEdge", Vector3(-4.15,3.36,z), Vector3(1.5,0.11,6.9), "444c53")
	for z in [-2.0, 3.5]:
		for seat in range(3):
			var dz: float = z+seat*0.64
			box("BenchSeat", Vector3(-3.8,0.52,dz), Vector3(0.58,0.09,0.57), "6d8081", true)
			box("BenchBack", Vector3(-4.09,0.82,dz), Vector3(0.075,0.57,0.57), "6d8081")
			for dx in [-4.0,-3.6]:
				box("BenchLeg", Vector3(dx,0.25,dz), Vector3(0.045,0.5,0.045), "434951")
	for z in [-7.8,0.2,5.2]:
		box("PosterFrame", Vector3(-4.79,1.98,z), Vector3(0.09,1.3,0.94), "464a52")
		box("PosterPaper", Vector3(-4.73,1.98,z), Vector3(0.012,1.16,0.81), "aaa998")
		for stripe in range(4):
			box("PosterTypography", Vector3(-4.718,2.33-stripe*0.13,z), Vector3(0.012,0.04,0.55-stripe*0.08), "676c6d")
		box("PosterRedMark", Vector3(-4.715,1.65,z+0.2), Vector3(0.012,0.2,0.2), "69464b")
	# Ticket dispenser against the back wall, outside the walkable corridor.
	box("TicketMachine", Vector3(-3.9,0.98,8.0), Vector3(0.85,1.95,0.78), "6f7e7b", true)
	box("TicketScreenBezel", Vector3(-3.46,1.37,8), Vector3(0.035,0.46,0.52), "222d37")
	var ticket_screen := box("TicketScreen", Vector3(-3.437,1.37,8), Vector3(0.012,0.33,0.39), "7aaf9b")
	ticket_screen.material_override = mat("7aaf9b",0.4)
	for i in range(3):
		box("TicketButton", Vector3(-3.43,0.95,7.85+i*0.15), Vector3(0.023,0.07,0.065), "c2bba4")
	box("TicketSlot", Vector3(-3.43,0.55,8), Vector3(0.022,0.08,0.38), "283037")
	# NODE_07 keeps its original collision and interaction script, inside this cabinet.
	box("SignalCabinet", Vector3(-1.8,0.95,-6), Vector3(0.86,1.85,0.7), "515b61")
	box("SignalPanel", Vector3(-1.8,1.0,-5.637), Vector3(0.72,1.57,0.022), "647077")
	for i in range(6):
		box("SignalVent", Vector3(-1.8,0.65+i*0.068,-5.62), Vector3(0.51,0.022,0.015), "303740")
	var red := ellipsoid("AnomalyLED", Vector3(-1.57,1.54,-5.59), Vector3(0.06,0.06,0.024), "b45965")
	red.material_override = mat("b45965",1.4)
	sign_text("PlatformSign", "01  /  ESTACIÓN", Vector3(-1.55,2.55,-9.9), 0, 38)
	save_asset("res://art/visual04/StationDressing.tscn")

func build() -> void:
	character()
	resident(true)
	resident(false)
	district()
	station()
	print("VISUAL04_ASSETS_SAVED")
	quit()
