extends SceneTree
## Deterministic offline authoring. Saves actual assets; never loads game autoloads/scenes.
const OUT := "res://art/city08/Neighborhood.tscn"
const LAYOUT = preload("res://scripts/world/CityLayout.gd")
var city := Node3D.new()
var holder: Node3D
var mats: Dictionary = {}
var batches: Dictionary = {}
var rng := RandomNumberGenerator.new()
var solids := 0

func _initialize() -> void:
	call_deferred("build")

func mat(key: String, tint: String, texture: String = "", scale_value: float = 0.35, emission: float = 0.0) -> StandardMaterial3D:
	if mats.has(key):
		return mats[key]
	var m := StandardMaterial3D.new()
	m.resource_name = key
	m.albedo_color = Color(tint)
	m.roughness = 0.91
	if not texture.is_empty():
		m.albedo_texture = load("res://art/visual05/textures/" + texture + ".png")
		m.uv1_triplanar = true
		m.uv1_world_triplanar = true
		m.uv1_scale = Vector3.ONE * scale_value
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	if emission > 0.0:
		m.emission_enabled = true
		m.emission = Color(tint)
		m.emission_energy_multiplier = emission
	mats[key] = m
	return m

func piece(kind: String, at: Vector3, size: Vector3, m: Material, rotation: Vector3 = Vector3.ZERO) -> void:
	# Batches remain local to a building or a 24m street chunk for culling/cutaway.
	var chunk := Vector2i(floori(at.x / 24), floori(at.z / 24))
	var key := str(holder.get_instance_id()) + kind + str(m.get_instance_id()) + str(chunk)
	if not batches.has(key):
		batches[key] = {"parent": holder, "kind": kind, "material": m, "transforms": []}
	batches[key]["transforms"].append(Transform3D(Basis.from_euler(rotation) * Basis.from_scale(size), at))

func box(at: Vector3, size: Vector3, m: Material, rotation: Vector3 = Vector3.ZERO) -> void:
	piece("box", at, size, m, rotation)

func rod(a: Vector3, b: Vector3, radius: float, m: Material) -> void:
	piece("rod", (a+b)*0.5, Vector3(radius, a.distance_to(b), radius), m,
		Basis(Quaternion(Vector3.UP, (b-a).normalized())).get_euler())

func solid(label: String, at: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.name = label
	body.position = at
	var shape := BoxShape3D.new()
	shape.size = size
	var collision := CollisionShape3D.new()
	collision.name = "Collision"
	collision.shape = shape
	body.add_child(collision)
	city.add_child(body, true)
	solids += 1

func sign_text(label: String, at: Vector3, text_value: String, color: Color, size_value: int = 42, rotation_y: float = 0.0) -> void:
	var sign := Label3D.new()
	sign.name = label
	sign.position = at
	sign.text = text_value
	sign.font_size = size_value
	sign.pixel_size = 0.006
	sign.outline_size = 1
	sign.modulate = color
	sign.rotation.y = rotation_y
	sign.no_depth_test = false
	holder.add_child(sign, true)

func point_light(at: Vector3, color: Color, energy: float, radius: float) -> void:
	var light := OmniLight3D.new()
	light.position = at
	light.light_color = color
	light.light_energy = energy
	light.omni_range = radius
	light.distance_fade_enabled = true
	light.distance_fade_begin = 23.0
	light.distance_fade_length = 10.0
	holder.add_child(light, true)

func build() -> void:
	# MultiMesh transform buffers cannot be authored with the dummy renderer.
	if DisplayServer.get_name() == "headless":
		push_error("Build city art with a real renderer; omit --headless.")
		city.free()
		quit(1)
		return
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	rng.seed = 80923
	city.name = "CityArt"
	holder = city
	mat("ink", "282b34")
	mat("steel", "555963", "concrete", 1.1)
	mat("stone", "aaa8a0", "concrete", 0.32)
	mat("road", "66646a", "asphalt", 0.23)
	mat("pavement", "a09d99", "concrete", 0.44)
	mat("paint", "c0b9a1", "concrete", 0.8)
	mat("wood", "77716a", "wood", 0.45)
	mat("glass", "404853")
	mat("warm", "b0a082", "", 1, 0.20)
	mat("cool", "8ca69e", "", 1, 0.20)
	mat("soil", "56554e", "asphalt", 0.4)
	streets()
	buildings()
	landmarks()
	street_life()
	flush_batches()
	await process_frame
	await RenderingServer.frame_post_draw
	assign_owners(city)
	DirAccess.make_dir_recursive_absolute("res://art/city08")
	var scene := PackedScene.new()
	if scene.pack(city) != OK or ResourceSaver.save(scene, OUT) != OK:
		push_error("Failed to save city asset")
		quit(1)
		return
	print("CITY08_BUILT batches=", batches.size(), " solids=", solids)
	city.free()
	quit()

func streets() -> void:
	box(Vector3(0,-0.12,-48), Vector3(92,0.22,132), mats.pavement)
	solid("Ground", Vector3(0,-0.15,-48), Vector3(92,0.28,132))
	for x in LAYOUT.LONG_STREETS:
		box(Vector3(x,0.001,-45), Vector3(5.8,0.02,120), mats.road)
		for side in [-1.0, 1.0]:
			for z in range(-105,15):
				if near_cross(float(z), 3.8):
					continue
				box(Vector3(x+side*3.05,0.04,z), Vector3(0.22,0.08,0.96), mats.stone)
				if z % 4 == 0:
					box(Vector3(x+side*2.7,0.025,z), Vector3(0.08,0.012,2.5), mats.paint)
		for z in range(-99,10,5):
			if not near_cross(float(z), 5):
				box(Vector3(x,0.023,z),Vector3(0.09,0.012,1.5),mats.paint)
		for z in LAYOUT.CROSS_STREETS:
			for side in [-1.0,1.0]:
				for stripe in range(7):
					box(Vector3(x-2.35+stripe*0.78,0.046,z+side*4.45),Vector3(0.40,0.015,1.65),mats.paint)
	for z in LAYOUT.CROSS_STREETS:
		box(Vector3(0,0.024,z),Vector3(86,0.025,5.8),mats.road)
		for x in range(-43,44):
			if absf(float(x)) < 3.8 or absf(absf(float(x))-29) < 3.8:
				continue
			for side in [-1.0,1.0]:
				box(Vector3(x,0.041,z+side*3.05),Vector3(0.96,0.08,0.22),mats.stone)
	# Long paving joints and drains are flush so walking has no invisible steps.
	for x in [-4.2,4.2,-24.8,24.8,-33.2,33.2]:
		for z in range(-107,14,2):
			if not near_cross(float(z), 3.5):
				box(Vector3(x,0.009,z),Vector3(2.2,0.01,0.022),mats.steel)
	for z in [-6.0,-30.0,-58.0,-89.0]:
		rod(Vector3(0.6,0.025,z),Vector3(0.6,0.04,z),0.43,mats.steel)
		for i in range(7):
			box(Vector3(0.33+i*0.09,0.047,z),Vector3(0.025,0.014,0.47),mats.ink)
	for z in [-9.0,-33.0,-62.0,-92.0]:
		box(Vector3(2.65,0.035,z),Vector3(0.32,0.02,0.76),mats.ink)
		for i in range(7):
			box(Vector3(2.65,0.05,z-0.3+i*0.1),Vector3(0.30,0.014,0.023),mats.steel)
	# World bounds are enclosed by back walls, not holes in the playable floor.
	for x in [-45.5,45.5]:
		box(Vector3(x,1.0,-48),Vector3(1,2,132),mats.stone)
		solid("CityBoundary",Vector3(x,1,-48),Vector3(1,2,132))
	for z in [-113.5,17.5]:
		box(Vector3(0,1,z),Vector3(92,2,1),mats.stone)
		solid("CityBoundary",Vector3(0,1,z),Vector3(92,2,1))

func near_cross(z: float, distance: float) -> bool:
	for crossing in LAYOUT.CROSS_STREETS:
		if absf(z-crossing) < distance:
			return true
	return false

func building(label: String, center: Vector3, size: Vector3, tint: String, pitched: bool = false, shop: String = "") -> void:
	var group := Node3D.new()
	group.name = label
	group.set_script(load("res://scripts/art/CityCutaway.gd"))
	group.set("bounds", AABB(Vector3(center.x-size.x/2,0,center.z-size.z/2),size))
	city.add_child(group)
	var upper := Node3D.new()
	upper.name = "Upper"
	group.add_child(upper)
	holder = group
	box(center+Vector3(0,0.26,0),Vector3(size.x+0.12,0.52,size.z+0.12),mats.steel)
	solid(label+"Collision",center+Vector3(0,size.y/2,0),size)
	holder = upper
	var wall := mat("wall_"+tint,tint,"concrete",0.24)
	box(center+Vector3(0,size.y/2,0),size,wall)
	# Cornices, stained base course and horizontal floor divisions.
	for y in [0.65,3.1,size.y-0.18]:
		box(center+Vector3(0,y,0),Vector3(size.x+0.17,0.13,size.z+0.17),mats.stone)
	var floors := maxi(1,int((size.y-0.5)/2.65))
	for floor_index in range(floors):
		var y := 1.7+floor_index*2.7
		for side in [-1.0,1.0]:
			for n in range(maxi(1,int(size.x/2.5))):
				var x := center.x-size.x/2+1.3+n*2.5
				window(Vector3(x,y,center.z+side*(size.z/2+0.036)),false,side, floor_index+n)
			for n in range(maxi(1,int(size.z/2.6))):
				var z := center.z-size.z/2+1.3+n*2.6
				window(Vector3(center.x+side*(size.x/2+0.036),y,z),true,side,floor_index+n+1)
	# Small building details are sized to people rather than giant repeated boxes.
	var front_z := center.z+size.z/2+0.06
	box(Vector3(center.x,1.03,front_z),Vector3(1.05,2.06,0.06),mats.wood)
	box(Vector3(center.x+0.36,1.0,front_z+0.06),Vector3(0.03,0.23,0.045),mats.warm)
	rod(Vector3(center.x+size.x/2+0.08,0.15,front_z-0.2),Vector3(center.x+size.x/2+0.08,size.y-0.05,front_z-0.2),0.045,mats.steel)
	box(Vector3(center.x+size.x/2+0.30,2.0,center.z),Vector3(0.52,0.65,1.0),mats.stone)
	for vent in range(8):
		box(Vector3(center.x+size.x/2+0.568,1.73+vent*0.075,center.z),Vector3(0.018,0.018,0.83),mats.ink)
	box(Vector3(center.x+size.x/2+0.07,1.5,front_z-1),Vector3(0.12,0.43,0.30),mats.steel)
	if pitched:
		var roof := mat("roof","565661","concrete",0.75)
		var slope := 0.27
		var quarter_rise := size.x/4*tan(slope)
		var gable_height := quarter_rise*2+0.04
		piece("gable",center+Vector3(0,size.y+gable_height/2,0),Vector3(size.x,gable_height,size.z),wall)
		for side in [-1.0,1.0]:
			box(center+Vector3(side*size.x/4,size.y+quarter_rise+0.10,0),Vector3(size.x/2+0.45,0.12,size.z+0.65),roof,Vector3(0,0,-side*slope))
			for tile in range(int(size.z/0.3)+2):
				var z := center.z-size.z/2-0.20+tile*0.30
				rod(Vector3(center.x,size.y+0.19+quarter_rise*2,z),Vector3(center.x+side*(size.x/2+0.22),size.y+0.19-0.22*tan(slope),z),0.022,mats.steel)
		rod(center+Vector3(0,size.y+0.19+quarter_rise*2,-size.z/2-0.30),center+Vector3(0,size.y+0.19+quarter_rise*2,size.z/2+0.30),0.10,mats.steel)
	else:
		box(center+Vector3(0,size.y+0.02,0),Vector3(size.x+0.3,0.18,size.z+0.3),mats.steel)
		for side in [-1.0,1.0]:
			box(center+Vector3(side*size.x/2,size.y+0.30,0),Vector3(0.14,0.5,size.z),wall)
			box(center+Vector3(0,size.y+0.30,side*size.z/2),Vector3(size.x,0.5,0.14),wall)
		box(center+Vector3(-size.x/4,size.y+0.47,0),Vector3(1.5,0.8,1.4),mats.stone)
		rod(center+Vector3(1,size.y,1),center+Vector3(1,size.y+2.5,1),0.024,mats.steel)
		for antenna in range(4):
			rod(center+Vector3(0.4,size.y+1.7+antenna*0.2,1),center+Vector3(1.6,size.y+1.7+antenna*0.2,1),0.016,mats.steel)
	# Thin projecting balconies break up the silhouettes of lived-in blocks.
	if size.y > 5.5 and label not in ["School","Nightclub","StationHall"] and not label.begins_with("Skyline"):
		var balcony_z := center.z+size.z/2+0.52
		box(Vector3(center.x,3.75,balcony_z),Vector3(3.8,0.16,1.2),mats.stone)
		rod(Vector3(center.x-1.85,4.72,balcony_z+0.55),Vector3(center.x+1.85,4.72,balcony_z+0.55),0.028,mats.steel)
		for bar in range(14):
			var bx := center.x-1.80+bar*0.277
			rod(Vector3(bx,3.85,balcony_z+0.55),Vector3(bx,4.72,balcony_z+0.55),0.014,mats.steel)
		for bx in [center.x-1.85,center.x+1.85]:
			rod(Vector3(bx,4.72,balcony_z-0.55),Vector3(bx,4.72,balcony_z+0.55),0.028,mats.steel)
	if not shop.is_empty():
		shopfront(center, size, shop)
	holder = city

func window(at: Vector3, side_wall: bool, sign_side: float, seed_value: int) -> void:
	var frame_size := Vector3(1.40,1.24,0.065) if not side_wall else Vector3(0.065,1.24,1.40)
	var glass_size := Vector3(1.22,1.06,0.076) if not side_wall else Vector3(0.076,1.06,1.22)
	box(at,frame_size,mats.steel)
	box(at,glass_size,mats.warm if seed_value % 5 == 0 else mats.glass)
	var sill := Vector3(1.55,0.07,0.16) if not side_wall else Vector3(0.16,0.07,1.55)
	box(at+Vector3(0,-0.65,0),sill,mats.stone)
	var bar := Vector3(0.043,1.14,0.088) if not side_wall else Vector3(0.088,1.14,0.043)
	box(at,bar,mats.steel)
	if seed_value % 3 == 0:
		var curtain := Vector3(0.37,1.03,0.078) if not side_wall else Vector3(0.078,1.03,0.37)
		var offset := Vector3(-0.4,0,sign_side*0.007) if not side_wall else Vector3(sign_side*0.007,0,-0.4)
		box(at+offset,curtain,mats.wood)

func shopfront(center: Vector3, size: Vector3, title: String) -> void:
	var z := center.z+size.z/2+0.16
	box(Vector3(center.x,1.2,z),Vector3(size.x-0.7,2.25,0.17),mats.steel)
	for i in range(3):
		box(Vector3(center.x-size.x*0.28+i*size.x*0.28,1.3,z+0.09),Vector3(size.x*0.24,1.90,0.07),mats.glass if i != 1 else mats.warm)
	var awning := mat("awning","687577","concrete",0.6)
	box(Vector3(center.x,2.65,z+0.52),Vector3(size.x+0.18,0.16,1.32),awning,Vector3(0.12,0,0))
	box(Vector3(center.x,3.05,z+0.1),Vector3(size.x-0.5,0.65,0.18),mats.ink)
	sign_text("ShopName",Vector3(center.x,3.08,z+0.21),title,Color("c0c2b5"),32)

func buildings() -> void:
	# Two inhabited inner blocks and outer rows form a real street grid.
	building("Apartments",Vector3(-14,0,11.8),Vector3(14,7.1,7.8),"a6a398")
	building("CornerBooks",Vector3(11,0,3),Vector3(10,6.1,9),"9e9898",false,"LIBROS / 02")
	building("Residence01",Vector3(-10,0,-3.5),Vector3(8,5.1,12),"b4aea2",true)
	building("Residence02",Vector3(-20,0,-4),Vector3(7,4.0,11),"939b9a",true)
	building("Grocer",Vector3(21,0,0),Vector3(7,4.4,14),"a5a49a",false,"MORI  /  ALIMENTACION")
	building("School",Vector3(-17,0,-28.5),Vector3(17,7.4,15),"b8b4a6")
	building("Arcade",Vector3(18,0,-50.5),Vector3(13,6.3,10),"8f9296",false,"VIDEO  /  24")
	building("Clinic",Vector3(-10,0,-52),Vector3(8,7.8,12),"b0b2a9",false,"CONSULTORIO")
	building("Tenements",Vector3(-20.5,0,-58),Vector3(7,8.1,24),"98949b")
	building("Nightclub",Vector3(18.5,0,-65),Vector3(13,5.3,12),"676972")
	building("RepairShop",Vector3(-11,0,-88.5),Vector3(10,5.6,16),"909993",false,"RADIO / REPARACIONES")
	building("PrintShop",Vector3(12,0,-89),Vector3(11,4.5,15),"a39d95",false,"COPIAS / IMPRENTA")
	building("SouthHomes",Vector3(22,0,-87),Vector3(7,7.0,18),"868e98")
	for side in [-1.0,1.0]:
		for i in range(8):
			var z: float = [5,-6,-27,-51,-64,-88,-109,12][i]
			var height := 4.0+float(i%3)*1.7
			building("Outer"+str(side)+"_"+str(i),Vector3(side*39,0,z),Vector3(9,height,8.4),["999a92","9496a0","aaa397"][i%3],i%2==0)
	# Distant rooftop silhouettes are beyond the playable boundary.
	for i in range(11):
		var h := 7.0+float((i*7)%5)*2.1
		building("Skyline"+str(i),Vector3(-48+i*9.5,0,-124),Vector3(8,h,10),"747c8a")

func landmarks() -> void:
	# Campus entrance faces a cross street; the functional door is added by gameplay.
	var school := city.get_node("School/Upper") as Node3D
	holder = school
	box(Vector3(-18,2.9,-20.25),Vector3(5.0,0.20,2.1),mats.steel)
	for x in [-20.2,-15.8]:
		box(Vector3(x,1.40,-19.8),Vector3(0.18,2.8,0.18),mats.steel)
	box(Vector3(-18,3.7,-20.86),Vector3(8.2,0.80,0.14),mats.steel)
	sign_text("SchoolTitle",Vector3(-18,3.73,-20.75),"ESCUELA MUNICIPAL",Color("d3ccb9"),44)
	# Clock on the upper facade.
	rod(Vector3(-18,6,-20.98),Vector3(-18,6,-20.85),0.57,mats.stone)
	rod(Vector3(-18,6,-20.76),Vector3(-18,6.35,-20.76),0.027,mats.ink)
	rod(Vector3(-18,6,-20.76),Vector3(-17.7,5.91,-20.76),0.027,mats.ink)
	point_light(Vector3(-18,2.55,-19.7),Color("c5d0c2"),0.8,5)
	holder = city.get_node("Nightclub/Upper")
	box(Vector3(25.60,2.55,-65),Vector3(1.6,0.16,5.4),mats.ink)
	var neon := mat("neon","a29cb8","",1,0.75)
	box(Vector3(26.4,2.50,-65),Vector3(0.045,0.07,5.1),neon)
	box(Vector3(25.06,3.50,-65),Vector3(0.12,1.20,5.0),mats.ink)
	sign_text("ClubTitle",Vector3(25.15,3.52,-65),"A Z U L",Color("b2a4ce"),68,PI/2)
	sign_text("ClubSubtitle",Vector3(25.18,2.95,-65),"B A J O  N I V E L",Color("c2bbc7"),22,PI/2)
	point_light(Vector3(26.1,2.1,-65),Color("a994ca"),1.3,6)
	holder = city
	# Plaza occupies an entire block, with open paths along all four sides.
	box(Vector3(16,0.015,-28),Vector3(17,0.03,17),mats.stone)
	for x in range(8,25,2):
		box(Vector3(x,0.035,-28),Vector3(0.028,0.01,17),mats.steel)
	for z in range(-36,-19,2):
		box(Vector3(16,0.036,z),Vector3(17,0.01,0.028),mats.steel)
	box(Vector3(17,0.26,-28),Vector3(5.4,0.52,5.4),mats.steel)
	box(Vector3(17,0.53,-28),Vector3(5.0,0.07,5.0),mats.soil)
	solid("PlazaPlanter",Vector3(17,0.28,-28),Vector3(5.4,0.56,5.4))
	tree(Vector3(17,0.6,-28),1.2)
	for z in [-22.0,-34.0]:
		bench(Vector3(13,0,z))
		bench(Vector3(21,0,z))
	# Apartment intercom/door are on the near face, with an actual facade behind them.
	box(Vector3(-12,2.6,7.2),Vector3(3.2,0.16,1.6),mats.steel)
	point_light(Vector3(-12,2.4,6.9),Color("d6b18d"),0.7,5)
	# Station terminates the long avenue with a canopy, clock and entrance hall.
	building("StationHall",Vector3(0,0,-110),Vector3(18,4.2,6.5),"8c9898")
	holder = city.get_node("StationHall/Upper")
	box(Vector3(0,3.0,-105.6),Vector3(15,0.25,3.0),mats.steel)
	for x in [-6.8,6.8]:
		box(Vector3(x,1.45,-104.5),Vector3(0.18,2.9,0.18),mats.steel)
	box(Vector3(0,3.65,-106.6),Vector3(11,0.65,0.18),mats.ink)
	sign_text("StationTitle",Vector3(0,3.65,-106.46),"ESTACION  /  ACCESO NORTE",Color("c4c9ba"),38)
	holder = city
	for x in [-5.0,5.0]:
		point_light(Vector3(x,2.8,-105),Color("b1c7b8"),0.75,7)

func tree(at: Vector3, factor: float = 1.0) -> void:
	var wood: Material = mats.wood
	rod(at,at+Vector3(0,3.1,0)*factor,0.13*factor,wood)
	for i in range(5):
		var angle := i*TAU/5
		var tip := at+Vector3(cos(angle)*0.95,3.1+float(i%2)*0.45,sin(angle)*0.95)*factor
		rod(at+Vector3(0,1.8,0)*factor,tip,0.055*factor,wood)
		var leaf := mat("leaf","c1c8b8")
		leaf.albedo_texture = load("res://art/visual05/textures/foliage.png")
		leaf.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		leaf.alpha_scissor_threshold = 0.45
		leaf.cull_mode = BaseMaterial3D.CULL_DISABLED
		leaf.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		leaf.backlight_enabled = true
		leaf.backlight = Color(0.18,0.18,0.12)
		for card in range(3):
			piece("leaf",tip,Vector3(2.0,1.9,1)*factor,leaf,Vector3(-0.18,angle+card*PI/3,0.14))
	solid("TreeTrunk",at+Vector3(0,1,0),Vector3(0.30,2,0.30))

func bench(at: Vector3) -> void:
	for i in range(5):
		box(at+Vector3(0,0.51,-0.26+i*0.13),Vector3(2.1,0.085,0.10),mats.wood)
	for i in range(3):
		box(at+Vector3(0,0.8+i*0.14,0.35),Vector3(2.1,0.11,0.08),mats.wood)
	for x in [-0.82,0.82]:
		box(at+Vector3(x,0.28,0),Vector3(0.08,0.5,0.63),mats.steel)
		box(at+Vector3(x,0.73,0.33),Vector3(0.07,0.91,0.07),mats.steel)
	solid("Bench",at+Vector3(0,0.46,0),Vector3(2.1,0.92,0.72))

func pole(at: Vector3) -> void:
	rod(at,at+Vector3(0,6.8,0),0.105,mats.stone)
	for y in [5.8,6.5]:
		rod(at+Vector3(-1.05,y,0),at+Vector3(1.05,y,0),0.055,mats.steel)
		for x in [-0.85,0.0,0.85]:
			rod(at+Vector3(x,y,0),at+Vector3(x,y+0.22,0),0.07,mats.stone)
	box(at+Vector3(0.22,4.8,0),Vector3(0.46,0.65,0.43),mats.steel)
	rod(at+Vector3(0,4.1,0),at+Vector3(1.3,4.1,0),0.055,mats.steel)
	box(at+Vector3(1.2,4.04,0),Vector3(0.57,0.07,0.22),mats.warm)
	solid("UtilityPole",at+Vector3(0,3,0),Vector3(0.24,6,0.24))

func cable(a: Vector3, b: Vector3) -> void:
	for n in range(12):
		var t := float(n)/12
		var tt := float(n+1)/12
		rod(a.lerp(b,t)-Vector3(0,sin(t*PI)*0.60,0),a.lerp(b,tt)-Vector3(0,sin(tt*PI)*0.60,0),0.015,mats.ink)

func vending(at: Vector3) -> void:
	var red := mat("vending","8b5a5b","concrete",0.8)
	box(at+Vector3(0,0.98,0),Vector3(1.16,1.96,0.79),red)
	box(at+Vector3(-0.1,1.26,0.405),Vector3(0.83,0.95,0.04),mats.cool)
	for row in range(3):
		for col in range(5):
			rod(at+Vector3(-0.40+col*0.15,0.95+row*0.27,0.438),at+Vector3(-0.40+col*0.15,1.1+row*0.27,0.438),0.045,mats.warm if col%2==0 else mats.steel)
	box(at+Vector3(0,0.32,0.413),Vector3(0.75,0.18,0.03),mats.ink)
	box(at+Vector3(0.48,0.99,0.413),Vector3(0.13,0.31,0.035),mats.ink)
	solid("VendingMachine",at+Vector3(0,0.98,0),Vector3(1.16,1.96,0.79))
	point_light(at+Vector3(0,1.2,0.9),Color("b1c0ac"),0.40,3)

func car(at: Vector3, tint: String) -> void:
	var paint := mat("car"+tint,tint,"concrete",0.6)
	box(at+Vector3(0,0.54,0),Vector3(1.55,0.62,3.3),paint)
	box(at+Vector3(0,1.08,0.12),Vector3(1.38,0.60,1.95),mats.glass)
	box(at+Vector3(0,1.42,0.18),Vector3(1.45,0.08,1.88),paint)
	for x in [-0.73,0.73]:
		box(at+Vector3(x,1.05,0.2),Vector3(0.06,0.65,0.09),paint)
		for z in [-1.0,1.08]:
			rod(at+Vector3(x-0.11,0.31,z),at+Vector3(x+0.11,0.31,z),0.30,mats.ink)
		box(at+Vector3(x*0.72,0.68,1.68),Vector3(0.35,0.20,0.035),mats.warm)
	box(at+Vector3(0,0.38,1.69),Vector3(1.42,0.11,0.045),mats.steel)
	box(at+Vector3(0,0.62,1.69),Vector3(0.38,0.15,0.045),mats.stone)
	solid("ParkedCar",at+Vector3(0,0.69,0),Vector3(1.6,1.4,3.4))

func street_life() -> void:
	for x in [-4.65,33.2]:
		var last := Vector3.ZERO
		for z in [8.5,-10.0,-33.5,-57.0,-69.5,-94.0]:
			var at := Vector3(x,0,z)
			pole(at)
			if last != Vector3.ZERO:
				for wire in [-0.85,0.0,0.85]:
					cable(last+Vector3(wire,6.72,0),at+Vector3(wire,6.72,0))
			last = at
	for at in [Vector3(-33.5,0,-3),Vector3(-33.5,0,-30),Vector3(8,0,-24),Vector3(23,0,-33),Vector3(-24,0,-88),Vector3(7,0,11),Vector3(33.5,0,-53)]:
		tree(at)
	for at in [Vector3(-6.7,0,2.5),Vector3(20,0,-19.7),Vector3(24,0,-57.5)]:
		vending(at)
	car(Vector3(-22,0,-10),"8b9194")
	car(Vector3(23,0,-48),"929489")
	car(Vector3(-36,0,-81),"747c87")
	# Bus stop, translucent-looking solid glass panels and timetable.
	box(Vector3(-4.8,2.55,-46),Vector3(1.65,0.12,4.5),mats.steel)
	for z in [-44.0,-48.0]:
		box(Vector3(-5.45,1.25,z),Vector3(0.09,2.5,0.09),mats.steel)
	box(Vector3(-5.5,1.6,-46),Vector3(0.04,1.5,3.9),mats.glass)
	box(Vector3(-4.0,1.6,-43.7),Vector3(0.18,1.1,0.65),mats.stone)
	rod(Vector3(-4,0,-43.7),Vector3(-4,2.9,-43.7),0.05,mats.steel)
	sign_text("BusRoute",Vector3(-3.86,2.7,-43.7),"04",Color("b8c9bd"),35,PI/2)
	# Phone booth: separate frame and inset panels, not a featureless cuboid.
	var phone := Vector3(8,0,-35)
	for x in [-0.55,0.55]:
		for z in [-0.55,0.55]:
			box(phone+Vector3(x,1.2,z),Vector3(0.07,2.4,0.07),mats.steel)
	box(phone+Vector3(0,2.43,0),Vector3(1.25,0.18,1.25),mats.cool)
	box(phone+Vector3(0,1.55,-0.52),Vector3(1.03,1.50,0.04),mats.glass)
	box(phone+Vector3(0,1.22,-0.36),Vector3(0.40,0.57,0.23),mats.steel)
	box(phone+Vector3(-0.22,1.26,-0.2),Vector3(0.10,0.35,0.10),mats.ink)
	solid("PhoneBooth",phone+Vector3(0,1.25,0),Vector3(1.18,2.5,1.18))
	# Bicycle silhouettes outside the campus; wheels remain actual rings.
	for i in range(3):
		var at := Vector3(-23+i*0.75,0,-19.7)
		for z in [-0.58,0.58]:
			for n in range(16):
				var a := n*TAU/16
				var b := (n+1)*TAU/16
				rod(at+Vector3(0,0.38+sin(a)*0.32,z+cos(a)*0.32),at+Vector3(0,0.38+sin(b)*0.32,z+cos(b)*0.32),0.026,mats.ink)
		rod(at+Vector3(0,0.38,-0.58),at+Vector3(0,0.95,0.38),0.03,mats.steel)
		rod(at+Vector3(0,0.38,0.58),at+Vector3(0,0.88,-0.22),0.03,mats.steel)
		rod(at+Vector3(0,0.88,-0.22),at+Vector3(0,0.38,-0.58),0.03,mats.steel)
		rod(at+Vector3(-0.24,1.04,0.40),at+Vector3(0.24,1.04,0.40),0.026,mats.steel)
		box(at+Vector3(0,0.90,-0.22),Vector3(0.21,0.06,0.30),mats.ink)
	# Public noticeboards and map supports: urban detail without quest spoilers.
	for at in [Vector3(5,0,-37),Vector3(-22,0,-104)]:
		box(at+Vector3(0,1.55,0),Vector3(1.5,1.25,0.17),mats.steel)
		for x in [-0.60,0.60]:
			box(at+Vector3(x,0.65,0),Vector3(0.07,1.3,0.07),mats.steel)
		for i in range(4):
			box(at+Vector3(-0.51+i*0.33,1.60,0.09),Vector3(0.27,0.78-float(i%2)*0.2,0.014),mats.paint if i%2==0 else mats.wood)

func flush_batches() -> void:
	for key in batches:
		var data: Dictionary = batches[key]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		var mesh: Mesh
		if data.kind == "rod":
			var cylinder := CylinderMesh.new()
			cylinder.top_radius = 1.0
			cylinder.bottom_radius = 1.0
			cylinder.height = 1.0
			cylinder.radial_segments = 8
			mesh = cylinder
		elif data.kind == "leaf":
			var quad := QuadMesh.new()
			quad.size = Vector2.ONE
			mesh = quad
		elif data.kind == "gable":
			var prism := PrismMesh.new()
			prism.size = Vector3.ONE
			mesh = prism
		else:
			var cube := BoxMesh.new()
			cube.size = Vector3.ONE
			mesh = cube
		mesh.material = data.material
		mm.mesh = mesh
		mm.instance_count = data.transforms.size()
		for index in range(mm.instance_count):
			mm.set_instance_transform(index,data.transforms[index])
		var batch := MultiMeshInstance3D.new()
		batch.name = "Geometry_" + str(data.material.resource_name) + "_" + data.kind
		batch.multimesh = mm
		data.parent.add_child(batch,true)

func assign_owners(node: Node) -> void:
	for child in node.get_children():
		child.owner = city
		assign_owners(child)
