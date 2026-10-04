extends SceneTree
## Offline art authoring. Only saves visual05 resources; never loads gameplay.
const OUT := "res://art/visual05/models/"
var asset: Node3D
var cache: Dictionary = {}
var rng := RandomNumberGenerator.new()

func _initialize() -> void:
	call_deferred("build")

func material(kind: String, tint: String = "b9b4ad", scale_value: float = 0.6) -> StandardMaterial3D:
	var key := kind + tint + str(scale_value)
	if cache.has(key):
		return cache[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(tint)
	m.roughness = 0.94
	if kind != "flat":
		m.albedo_texture = load("res://art/visual05/textures/" + kind + ".png")
		m.uv1_triplanar = true
		m.uv1_world_triplanar = true
		m.uv1_scale = Vector3.ONE * scale_value
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	cache[key] = m
	return m

func box(label: String, at: Vector3, size: Vector3, m: Material) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = label
	var shape := BoxMesh.new()
	shape.size = size
	node.mesh = shape
	node.material_override = m
	node.position = at
	asset.add_child(node, true)
	return node

func rod(label: String, a: Vector3, b: Vector3, radius: float, m: Material) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = label
	var shape := CylinderMesh.new()
	shape.bottom_radius = radius
	shape.top_radius = radius
	shape.height = a.distance_to(b)
	shape.radial_segments = 10
	node.mesh = shape
	node.material_override = m
	node.position = (a+b)*0.5
	node.quaternion = Quaternion(Vector3.UP,(b-a).normalized())
	asset.add_child(node, true)
	return node

func foliage(at: Vector3, size: float) -> void:
	var m := StandardMaterial3D.new()
	m.albedo_texture = load("res://art/visual05/textures/foliage.png")
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.4
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.roughness = 1.0
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.backlight_enabled = true
	m.backlight = Color(0.16,0.16,0.13)
	for i in range(3):
		var leaf := MeshInstance3D.new()
		leaf.name = "FoliageCard"
		var plane := QuadMesh.new()
		plane.size = Vector2(size,size)
		leaf.mesh = plane
		leaf.material_override = m
		leaf.position = at + Vector3(0, i*0.05, 0)
		leaf.rotation = Vector3(-0.12, i*PI/3.0, rng.randf_range(-0.14,0.14))
		asset.add_child(leaf, true)

func own(node: Node) -> void:
	for child in node.get_children():
		child.owner = asset
		if child is Node3D:
			child.scene_file_path = ""
		own(child)

func save_asset(name: String) -> void:
	own(asset)
	asset.scene_file_path = ""
	var scene := PackedScene.new()
	if scene.pack(asset) != OK or ResourceSaver.save(scene, OUT+name+".tscn") != OK:
		push_error("Cannot save " + name)
		quit(1)
	asset.free()

func begin(name: String, source: String = "") -> void:
	asset = Node3D.new() if source.is_empty() else load(source).instantiate()
	asset.name = name

func weather_existing() -> void:
	for node in asset.find_children("*", "MeshInstance3D", true, false):
		var old = node.material_override
		var label := str(node.name)
		if old is StandardMaterial3D and not old.emission_enabled:
			var c: Color = old.albedo_color
			var tint := Color(minf(c.r*1.5+0.15,1),minf(c.g*1.5+0.15,1),minf(c.b*1.5+0.15,1)).to_html(false)
			if label.contains("Slab") or label.contains("Sidewalk") or label.contains("Wall") or label.contains("Facade") or label.contains("Kerb") or label.contains("Coping"):
				node.material_override = material("concrete", "c4c1ba", 0.9)
			elif not (label.contains("Wire") or label.contains("Line") or label.contains("Text")):
				node.material_override = material("concrete", tint, 1.8)
			if label.begins_with("WindowGlass"):
				node.material_override = material("flat","5c5866")
			elif label.begins_with("HouseDoor"):
				node.material_override = material("wood","74717a",0.6)
			elif label.begins_with("WindowFrame") or label.begins_with("WindowMullion"):
				node.material_override = material("flat","48434e")
			elif label.begins_with("Tactile"):
				node.material_override = material("flat","b9a16b" if label.contains("Ridge") else "93825f")
			elif label.begins_with("RailSleeper"):
				node.material_override = material("wood","8b8785",1.5)

func district() -> void:
	begin("ResidentialStreet", "res://art/visual04/ResidentialStreet.tscn")
	weather_existing()
	for node in asset.get_children():
		if str(node.name).begins_with("Shrub") or str(node.name).begins_with("RoofSeam"):
			node.free()
	var dark := material("flat", "343039")
	var metal := material("concrete", "72716c", 1.8)
	for z in [-25.0,-18.0,-11.0,-4.0,3.0]:
		# Pitched tile roofs: their edges stay behind the original wall collision.
		for side in [-1.0,1.0]:
			var roof := box("PitchedRoof",Vector3(-4.5+side*0.83,3.56,z),Vector3(1.83,0.075,6.5),material("concrete","686870",2.5))
			roof.rotation.z = -side*0.30
			for row in range(10):
				var x: float = -4.5+side*(0.12+row*0.17)
				rod("RoofTileLip",Vector3(x,3.85-absf(x+4.5)*0.30,z-3.2),Vector3(x,3.85-absf(x+4.5)*0.30,z+3.2),0.022,metal)
		for i in range(18):
			var zz: float = z-3.13+i*0.365
			rod("RoofTileJoint",Vector3(-6.15,3.36,zz),Vector3(-4.5,3.86,zz),0.009,dark)
			rod("RoofTileJoint",Vector3(-4.5,3.86,zz),Vector3(-2.85,3.36,zz),0.009,dark)
		rod("RainGutter",Vector3(-2.87,3.21,z-3.18),Vector3(-2.87,3.21,z+3.18),0.055,metal)
		rod("DrainPipe",Vector3(-2.86,0.15,z+2.88),Vector3(-2.86,3.23,z+2.88),0.045,metal)
		box("AirConditioner",Vector3(-2.69,1.05,z-2.1),Vector3(0.48,0.56,0.83),material("concrete","b7b6ad",2))
		for i in range(7):
			box("VentLouvre",Vector3(-2.435,0.86+i*0.058,z-2.1),Vector3(0.013,0.012,0.72),dark)
		# Yard wall, gate and layered leaf silhouettes rather than round shrubs.
		for dz in [-2.3,0.0,2.3]:
			box("GardenPier",Vector3(2.95,0.8,z+dz),Vector3(0.32,1.6,0.31),material("concrete","b3b2ab"))
		for i in range(7):
			rod("GateBar",Vector3(2.85,0.16,z-0.75+i*0.20),Vector3(2.85,1.57,z-0.75+i*0.20),0.015,dark)
		for y in [0.35,1.4]:
			rod("GateRail",Vector3(2.85,y,z-0.78),Vector3(2.85,y,z+0.65),0.025,dark)
		for i in range(4):
			foliage(Vector3(3.6+rng.randf()*0.45,1.2+rng.randf()*0.45,z-2.0+i*1.1),1.8+rng.randf()*0.55)
		rod("TreeTrunk",Vector3(4.3,0.3,z-1.6),Vector3(4.3,2.55,z-1.6),0.075,material("wood","7e797a"))
		foliage(Vector3(4.3,2.65,z-1.6),2.6)
		# Meter covers and worn narrow nameplates beside each entrance.
		box("ElectricMeter",Vector3(-2.86,1.8,z+1.25),Vector3(0.11,0.34,0.23),metal)
		box("DoorPlate",Vector3(-2.87,1.58,z+0.45),Vector3(0.03,0.25,0.17),material("flat","b4aa9b"))
	# Circular iron utility covers laid flush with road.
	for z in [-7.0,-19.0,3.0]:
		rod("Manhole",Vector3(0,0.011,z),Vector3(0,0.027,z),0.29,metal)
		for i in range(5):
			box("ManholeSlot",Vector3(-0.16+i*0.08,0.031,z),Vector3(0.023,0.007,0.35),dark)
	save_asset("ResidentialStreet")

func station() -> void:
	begin("StationDressing", "res://art/visual04/StationDressing.tscn")
	weather_existing()
	var dark := material("flat","292e31")
	var steel := material("concrete","888d87",2)
	for node in asset.find_children("Fluorescent*","MeshInstance3D",true,false):
		node.position.z += 0.14
		node.position.y += 0.04
	# Ballast uses one instanced draw, preserving the existing track geometry.
	var ballast := MultiMeshInstance3D.new()
	ballast.name = "RailBallast"
	var stones := MultiMesh.new()
	stones.transform_format = MultiMesh.TRANSFORM_3D
	var pebble := SphereMesh.new()
	pebble.radius = 0.05
	pebble.height = 0.085
	pebble.radial_segments = 6
	pebble.rings = 3
	pebble.material = material("flat","494749")
	stones.mesh = pebble
	stones.instance_count = 3200
	for i in range(stones.instance_count):
		var basis := Basis.from_euler(Vector3(rng.randf(),rng.randf()*TAU,rng.randf()))
		stones.set_instance_transform(i,Transform3D(basis,Vector3(rng.randf_range(1.78,4.22),0.062,rng.randf_range(-9.4,8.4))))
	ballast.multimesh = stones
	asset.add_child(ballast)
	# Tile wall courses, grime-heavy lower panels and noticeboard frames.
	for z in range(-10,11):
		for row in range(7):
			box("WallTile",Vector3(-4.823,0.19+row*0.28,z*1.0),Vector3(0.045,0.265,0.975),material("concrete","afa99a" if row>1 else "787c70",2))
	for z in [-8.0,-1.0,6.0]:
		rod("CanopyBrace",Vector3(-4.31,2.5,z),Vector3(-3.5,3.23,z),0.04,steel)
		rod("Conduit",Vector3(-4.72,2.6,z-3.4),Vector3(-4.72,2.6,z+3.4),0.025,steel)
		for i in range(23):
			box("CorrugatedRib",Vector3(-4.15,3.44,z-3.3+i*0.3),Vector3(1.6,0.045,0.055),steel)
		box("FluorescentEnd",Vector3(-2.33,3.08,z),Vector3(0.12,0.14,0.23),steel)
	for z in [-9.6,-2.3,5.3]:
		for side in [-1,1]:
			rod("PosterFrame",Vector3(-4.69,1.32,z+side*.50),Vector3(-4.69,2.65,z+side*.50),0.026,dark)
	# A second ticket machine and recycling bin, both outside central walking route.
	box("TicketMachine",Vector3(-3.87,0.9,9.25),Vector3(0.7,1.8,0.67),steel)
	box("TicketDisplay",Vector3(-3.507,1.38,9.25),Vector3(0.012,0.4,0.45),material("flat","485d55"))
	for i in range(5):
		box("TicketButtons",Vector3(-3.49,1.01,9.05+i*.085),Vector3(.016,.065,.053),material("flat","a59e81"))
	box("Bin",Vector3(-4.0,0.48,1.65),Vector3(0.63,0.96,0.56),steel)
	box("BinOpening",Vector3(-3.68,0.72,1.65),Vector3(0.012,0.21,0.38),dark)
	# Cable service fence on the far end; does not cover signal approach.
	for x in [1.6,3.0,4.4]:
		rod("FencePost",Vector3(x,0.1,-9.6),Vector3(x,2.8,-9.6),0.038,steel)
	for i in range(17):
		rod("FenceWire",Vector3(1.6+i*.175,0.4,-9.6),Vector3(1.6+i*.175,2.6,-9.6),0.007,dark)
	for i in range(13):
		rod("FenceWire",Vector3(1.6,0.4+i*.175,-9.6),Vector3(4.4,0.4+i*.175,-9.6),0.007,dark)
	box("SignalMast",Vector3(3.9,1.72,-9.7),Vector3(.09,3.4,.09),steel)
	box("SignalHousing",Vector3(3.9,2.62,-9.7),Vector3(.32,.67,.3),dark)
	var red := material("flat","a5343d").duplicate() as StandardMaterial3D
	red.emission_enabled = true
	red.emission = Color("be3948")
	red.emission_energy_multiplier = 2.0
	box("RedSignal",Vector3(3.9,2.77,-9.53),Vector3(.15,.15,.02),red)
	var lamp := OmniLight3D.new()
	lamp.name = "SignalRedGlow"
	lamp.position = Vector3(3.9,2.77,-9.15)
	lamp.light_color = Color("b92e40")
	lamp.light_energy = 0.9
	lamp.omni_range = 2.4
	asset.add_child(lamp)
	save_asset("StationDressing")

func fabric() -> void:
	# A triangulated wrinkled blanket with a deterministic height field.
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for z in range(24):
		for x in range(20):
			for corner in [Vector2(0,0),Vector2(0,1),Vector2(1,1),Vector2(0,0),Vector2(1,1),Vector2(1,0)]:
				var u: float = (x+corner.x)/20.0
				var v: float = (z+corner.y)/24.0
				var h: float = 0.47 + 0.020*sin(u*19+v*4)*sin(v*7) + 0.013*sin(v*25-u*8)
				st.set_uv(Vector2(u,v))
				st.add_vertex(Vector3(-3.2+u*1.62,h,0.94+v*1.87))
	st.generate_normals()
	var mesh := MeshInstance3D.new()
	mesh.name = "WrinkledDuvet"
	mesh.mesh = st.commit()
	var cloth := material("flat","7b7485").duplicate() as StandardMaterial3D
	cloth.cull_mode = BaseMaterial3D.CULL_DISABLED
	mesh.material_override = cloth
	asset.add_child(mesh)

func apartment() -> void:
	for part in ["Floor","Architecture","Workstation","SleepingArea","Shelves","Kitchen"]:
		begin(part,"res://art/apartment/models/"+part+".tscn")
		weather_existing()
		for node in asset.find_children("*","MeshInstance3D",true,false):
			var label := str(node.name)
			# Older baked assets have automatic names. Match their geometry too.
			if part == "Floor" and node.position.y < 0.03 and node.position.y > 0:
				node.visible = false
			if part == "SleepingArea" and node.mesh is BoxMesh and node.mesh.size.y < 0.02:
				node.visible = false
			if label.begins_with("Floorboard") or label.contains("Shelf") or label.contains("DeskTop") or label.contains("LowTable") or label.contains("DoorSurround"):
				node.material_override = material("wood","c3bdc0",0.35 if part=="Floor" else 0.8)
			if label.contains("Rug") or label.contains("Pillow") or label.contains("Futon") or label.contains("Curtain"):
				node.material_override = material("flat","88808d")
			if label.begins_with("FabricFold") or label.begins_with("Duvet"):
				node.visible = false
		if part == "SleepingArea":
			fabric()
		if part == "Floor":
			box("WoodFloor",Vector3(0,0.017,0),Vector3(7.99,0.027,7.99),material("wood","c3bdc0",0.24))
		save_asset(part)
	begin("ApartmentDetails")
	var dark := material("flat","34333b")
	var ivory := material("concrete","c4c3b7",2)
	# Extra computer gear and storage occupy edges, leaving tested routes clear.
	for i in range(3):
		var z: float = -1.0+i*.6
		box("EquipmentCase",Vector3(-3.45,0.36,z),Vector3(.54,.72,.48),ivory)
		for row in range(5):
			box("EquipmentVent",Vector3(-3.17,.23+row*.065,z),Vector3(.009,.016,.33),dark)
		box("EquipmentHandle",Vector3(-3.45,.745,z),Vector3(.23,.025,.06),dark)
	for i in range(7):
		var x: float = -0.35+i*.09
		box("CassetteStack",Vector3(x,1.075,-3.38),Vector3(.065,.16,.16),material("concrete","8d8a85",3))
	box("Fridge",Vector3(1.53,.66,-3.30),Vector3(.64,1.32,.66),ivory)
	box("FridgeSeal",Vector3(1.53,.91,-2.96),Vector3(.6,.014,.012),dark)
	box("FridgeHandle",Vector3(1.77,.7,-2.925),Vector3(.025,.26,.035),dark)
	box("KitchenShelf",Vector3(.65,2.1,-3.53),Vector3(1.7,.06,.55),material("wood","b5ada6"))
	for i in range(5):
		rod("KitchenJar",Vector3(.04+i*.23,2.14,-3.48),Vector3(.04+i*.23,2.34+(i%2)*.07,-3.48),.073,ivory)
	for z in [-1.0,-.45,.10]:
		box("WallPoster",Vector3(-3.855,1.8,z),Vector3(.018,.65,.40),material("concrete","c3bfb5",2))
		for j in range(4):
			box("PosterInk",Vector3(-3.841,1.95-j*.10,z),Vector3(.009,.023,.25-j*.025),dark)
	# Surface conduits, socket and paperwork add silhouette detail.
	rod("WallConduit",Vector3(-3.82,.5,-3.5),Vector3(-3.82,.5,1.0),.015,dark)
	box("WallSocket",Vector3(-3.8,.5,-1.0),Vector3(.06,.14,.10),ivory)
	for y in [1.64,2.32]:
		box("WindowCrossbar",Vector3(-1.65,y,-3.62),Vector3(2.63,.025,.035),dark)
	# Desk speaker pair, stereo receiver and a second dormant CRT.
	for x in [-2.5,-.7]:
		box("Speaker",Vector3(x,1.17,-3.03),Vector3(.23,.48,.25),dark)
		rod("SpeakerCone",Vector3(x,1.18,-2.889),Vector3(x,1.18,-2.872),.074,material("flat","74746d"))
	box("SecondCRT",Vector3(-3.4,1.08,-1.1),Vector3(.51,.43,.47),ivory)
	box("SecondScreen",Vector3(-3.131,1.09,-1.1),Vector3(.02,.3,.32),material("flat","263535"))
	box("StorageCrate",Vector3(-2.48,.23,3.53),Vector3(.73,.45,.58),material("wood","8b8384"))
	for i in range(6):
		box("PaperBundle",Vector3(-2.46,.477+i*.018,3.53),Vector3(.50,.014,.35),ivory)
	for i in range(6):
		var paper := box("LoosePaper",Vector3(.1+i*.042,.493+i*.002,1.45+i*.014),Vector3(.25,.002,.18),ivory)
		paper.rotation.y = i*.13
	rod("PlantPot",Vector3(-3.36,0,3.48),Vector3(-3.36,.32,3.48),.19,material("concrete","766b66"))
	foliage(Vector3(-3.36,.81,3.48),1.1)
	save_asset("ApartmentDetails")

func build() -> void:
	rng.seed = 5001
	district()
	station()
	apartment()
	ResourceSaver.save(material("asphalt","c7c2c6",0.8),"res://art/visual05/road.tres")
	ResourceSaver.save(material("concrete","bcb9b4",0.6),"res://art/visual05/wall.tres")
	ResourceSaver.save(material("concrete","85867e",1.8),"res://art/visual05/platform.tres")
	ResourceSaver.save(material("asphalt","777377",2.0),"res://art/visual05/ballast.tres")
	var rail := material("flat","777b7f").duplicate() as StandardMaterial3D
	rail.metallic = 0.55
	rail.roughness = 0.45
	ResourceSaver.save(rail,"res://art/visual05/rail.tres")
	print("VISUAL05_ASSETS_SAVED")
	quit()
