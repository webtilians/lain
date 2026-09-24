extends "res://tools/build_city08.gd"
## Offline authoring of the reference-quality street; no gameplay or server writes.
const DEST := "res://art/reference09/ReferenceStreet.tscn"
var house_origin := Vector3.ZERO
var roof_batches := 0

func build() -> void:
	if DisplayServer.get_name() == "headless":
		push_error("Reference authoring requires a real renderer; omit --headless.")
		city.free()
		quit(1)
		return
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	rng.seed = 90231
	city.name = "ReferenceStreet"
	holder = city
	palette()
	house("HouseA",Vector3(-9.8,0,-6.85),5.15,0)
	house("HouseB",Vector3(-9.8,0,0.45),4.8,1)
	holder = city
	street_finish()
	garden()
	utility_detail()
	flush_batches()
	await process_frame
	await RenderingServer.frame_post_draw
	assign_owners(city)
	var packed := PackedScene.new()
	if packed.pack(city) != OK or ResourceSaver.save(packed,DEST) != OK:
		push_error("Cannot save reference street")
		quit(1)
		return
	print("REFERENCE09_BUILT material_batches=",batches.size()+roof_batches," colliders=",solids)
	city.free()
	quit()

func palette() -> void:
	mat("ink","252a2e")
	mat("metal","565b5c","concrete",1.8)
	mat("trim","9b9c95","concrete",0.6)
	mat("wood","625c55","wood",0.7)
	mat("cedar","777269","wood",0.45)
	mat("stone","9d9e98","concrete",0.48)
	mat("mortar","5f635f","concrete",1.3)
	mat("curtain","b5b1a4")
	# Generated albedo plus procedural microsurface, entirely contained in the asset.
	var plaster := ShaderMaterial.new()
	var grain := FastNoiseLite.new()
	grain.seed = 909
	grain.frequency = 0.12
	var normal_texture := NoiseTexture2D.new()
	normal_texture.width = 128
	normal_texture.height = 128
	normal_texture.noise = grain
	normal_texture.seamless = true
	normal_texture.as_normal_map = true
	normal_texture.bump_strength = 0.6
	plaster.resource_name = "ReferencePlaster"
	plaster.shader = load("res://shaders/reference_surface.gdshader")
	plaster.set_shader_parameter("albedo_map",load("res://art/reference09/materials/plaster-albedo.png"))
	plaster.set_shader_parameter("tint",Color("b6b3a8"))
	plaster.set_shader_parameter("repeats",0.28)
	plaster.set_shader_parameter("normal_texture",normal_texture)
	mats["plaster"] = plaster
	var road := ShaderMaterial.new()
	road.resource_name = "ReferenceAsphalt"
	road.shader = load("res://shaders/reference_surface.gdshader")
	road.set_shader_parameter("albedo_map",load("res://art/visual05/textures/asphalt.png"))
	road.set_shader_parameter("tint",Color("818189"))
	road.set_shader_parameter("repeats",0.9)
	road.set_shader_parameter("grit",0.20)
	road.set_shader_parameter("normal_texture",normal_texture)
	mats["road09"] = road
	var glass := mat("glass","a8b5b4")
	glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	glass.albedo_color.a = 0.22
	glass.roughness = 0.19
	glass.metallic = 0.2
	glass.cull_mode = BaseMaterial3D.CULL_DISABLED
	var foliage_mat := mat("leaves","c1c8b8")
	foliage_mat.albedo_texture = load("res://art/visual05/textures/foliage.png")
	foliage_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	foliage_mat.alpha_scissor_threshold = 0.40
	foliage_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	foliage_mat.backlight_enabled = true
	foliage_mat.backlight = Color(0.26,0.30,0.18)
	foliage_mat.roughness = 0.96
	for index in range(4):
		var tile := mat("tile"+str(index),["777882","6b6f7b","81828a","73747f"][index],"concrete",2.0)
		tile.cull_mode = BaseMaterial3D.CULL_DISABLED
		tile.roughness = 0.85

func house(label: String, at: Vector3, height: float, variant: int) -> void:
	house_origin = at
	var building_node := Node3D.new()
	building_node.name = label
	building_node.set_script(load("res://scripts/art/CityCutaway.gd"))
	building_node.set("bounds",AABB(at+Vector3(-3.4,0,-3.15),Vector3(6.8,height+1.2,6.3)))
	city.add_child(building_node)
	var upper := Node3D.new()
	upper.name = "Upper"
	building_node.add_child(upper)
	holder = building_node
	box(at+Vector3(0,0.17,0),Vector3(6.85,0.34,6.35),mats.mortar)
	solid(label+"Collision",at+Vector3(0,height/2,0),Vector3(6.8,height,6.3))
	holder = upper
	var face := at.x+3.4
	# Solid rear volume ends 30cm behind the facade, leaving real window reveals.
	box(at+Vector3(-0.18,height/2,0),Vector3(6.44,height,6.3),mats.plaster)
	for column in range(3):
		var z := at.z-2.1+column*2.1
		var is_door := column==1
		var low := 0.0 if is_door else 0.91
		var high := 2.18 if is_door else 2.20
		facade_panel(face,z,0.25,low,1.95,mats.plaster)
		facade_panel(face,z,high,2.82,1.95,mats.plaster)
		facade_panel(face,z,2.82,3.18,1.95,mats.plaster)
		facade_panel(face,z,4.43,height,1.95,mats.plaster)
		for y_range in [Vector2(low,high),Vector2(3.18,4.43)]:
			for side in [-1.0,1.0]:
				box(Vector3(face,(y_range.x+y_range.y)/2,z+side*0.82),Vector3(0.28,y_range.y-y_range.x,0.33),mats.plaster)
		if is_door:
			house_door(face,z,variant)
		else:
			recessed_window(face,z,1.555,1.29,variant+column,false)
		recessed_window(face,z,3.805,1.25,variant+column,true)
	for z in [at.z-3.11,at.z-1.05,at.z+1.05,at.z+3.11]:
		box(Vector3(face, height/2,z),Vector3(0.30,height,0.15),mats.plaster)
	# Timber weatherboards below the ground-floor windows.
	for row in range(7):
		box(Vector3(face+0.16,0.32+row*0.079,at.z-2.1),Vector3(0.04,0.071,1.75),mats.cedar)
		box(Vector3(face+0.16,0.32+row*0.079,at.z+2.1),Vector3(0.04,0.071,1.75),mats.cedar)
	box(Vector3(face+0.2,2.85,at.z),Vector3(0.32,0.12,6.65),mats.wood)
	for z in [at.z-3.08,at.z+3.08]:
		box(Vector3(face+0.16,height/2,z),Vector3(0.10,height,0.12),mats.cedar)
	# Side-wall windows have deep projecting surrounds and small frosted panes.
	for side in [-1.0,1.0]:
		for floor_index in range(2):
			var y := 1.6+floor_index*2.15
			box(at+Vector3(-0.4,y,side*3.17),Vector3(1.55,1.30,0.14),mats.wood)
			box(at+Vector3(-0.4,y,side*3.25),Vector3(1.37,1.11,0.025),mats.metal)
			box(at+Vector3(-0.4,y,side*3.28),Vector3(0.045,1.12,0.035),mats.trim)
	# A small service box, exposed conduit and exterior AC unit.
	service_details(face,at.z-2.3,height)
	if variant==1:
		balcony(face,at.z)
	roof(at,height,variant)
	# Gutter and downpipe use elbows, collars and wall clips.
	rod(Vector3(face+0.45,height-0.04,at.z-3.40),Vector3(face+0.45,height-0.04,at.z+3.40),0.065,mats.metal)
	var pipe_z := at.z+2.95
	rod(Vector3(face+0.43,height-0.06,pipe_z),Vector3(face+0.27,height-0.40,pipe_z),0.041,mats.metal)
	rod(Vector3(face+0.27,height-0.40,pipe_z),Vector3(face+0.27,0.28,pipe_z),0.041,mats.metal)
	rod(Vector3(face+0.27,0.28,pipe_z),Vector3(face+0.51,0.09,pipe_z),0.041,mats.metal)
	for y in [0.6,2.25,3.9]:
		box(Vector3(face+0.24,y,pipe_z),Vector3(0.13,0.035,0.14),mats.metal)
	holder = city
	for z in [at.z-2.8,at.z+2.8]:
		planter(Vector3(face+0.48,0,z),0.28)

func facade_panel(x: float,z: float,bottom: float,top: float,width: float,m: Material) -> void:
	if top>bottom:
		box(Vector3(x,(top+bottom)/2,z),Vector3(0.28,top-bottom,width),m)

func recessed_window(x: float,z: float,y: float,h: float,variation: int,upstairs: bool) -> void:
	var inner := x-0.17
	box(Vector3(inner-0.08,y,z),Vector3(0.02,h,1.32),mats.ink)
	# Curtain pleats are real geometry behind a translucent pane.
	for i in range(12):
		var zz := z-0.59+i*0.105
		if variation%2==0 and i in [5,6,7]:
			continue
		box(Vector3(inner-0.02+sin(i*2.4)*0.018,y,zz),Vector3(0.02,h-0.08,0.092),mats.curtain)
	box(Vector3(inner+0.07,y,z),Vector3(0.015,h-0.06,1.28),mats.glass)
	for side in [-1.0,1.0]:
		box(Vector3(x+0.10,y,z+side*0.675),Vector3(0.14,h+0.10,0.07),mats.wood)
		box(Vector3(x+0.1,y+side*(h/2+0.015),z),Vector3(0.14,0.07,1.42),mats.wood)
	box(Vector3(x+0.11,y,z),Vector3(0.09,h,0.042),mats.metal)
	box(Vector3(x+0.11,y+0.08,z),Vector3(0.09,0.036,1.31),mats.metal)
	box(Vector3(x+0.19,y-h/2-0.09,z),Vector3(0.43,0.09,1.56),mats.stone)
	box(Vector3(x+0.1,y+h/2+0.13,z),Vector3(0.27,0.11,1.60),mats.trim)
	if variation%2==0:
		for side in [-1.0,1.0]:
			var sz: float = z+side*0.86
			box(Vector3(x+0.14,y,sz),Vector3(0.08,h+0.05,0.28),mats.wood)
			for louvre in range(12):
				box(Vector3(x+0.195,y-h/2+0.07+louvre*(h-0.12)/12,sz),Vector3(0.045,0.042,0.25),mats.cedar,Vector3(0,0,0.12))
	if not upstairs:
		for i in range(7):
			rod(Vector3(x+0.32,y-h/2-0.015,z-0.58+i*0.195),Vector3(x+0.32,y-0.01,z-0.58+i*0.195),0.012,mats.metal)
		rod(Vector3(x+0.32,y,z-0.64),Vector3(x+0.32,y,z+0.64),0.018,mats.metal)
	weather_streak(Vector3(x+0.148,y-h/2-0.40,z),Vector2(1.4,0.65))

func house_door(x: float,z: float,variant: int) -> void:
	box(Vector3(x-0.08,1.055,z),Vector3(0.08,2.11,1.27),mats.wood)
	for i in range(9):
		box(Vector3(x-0.02,0.8,z-0.54+i*0.135),Vector3(0.035,1.45,0.013),mats.ink)
	box(Vector3(x+0.025,1.65,z),Vector3(0.02,0.5,0.94),mats.glass)
	box(Vector3(x+0.07,0.99,z+0.43),Vector3(0.07,0.26,0.03),mats.trim)
	box(Vector3(x+0.18,0.07,z),Vector3(0.52,0.14,1.6),mats.stone)
	box(Vector3(x+0.52,2.31,z),Vector3(1.32,0.10,1.85),mats.metal,Vector3(0,0,-0.12))
	rod(Vector3(x+0.13,1.94,z-0.77),Vector3(x+1.05,2.27,z-0.77),0.017,mats.metal)
	rod(Vector3(x+0.13,1.94,z+0.77),Vector3(x+1.05,2.27,z+0.77),0.017,mats.metal)
	box(Vector3(x+0.2,1.48,z+0.93),Vector3(0.12,0.31,0.22),mats.trim)
	box(Vector3(x+0.27,1.52,z+0.93),Vector3(0.026,0.14,0.14),mats.ink)
	sign_text("Nameplate",Vector3(x+0.29,1.86,z+0.91),"03 / "+str(6+variant),Color("c7c4b7"),14,PI/2)

func balcony(x: float,z: float) -> void:
	box(Vector3(x+0.40,2.95,z),Vector3(0.92,0.12,2.9),mats.metal)
	for i in range(16):
		rod(Vector3(x+0.83,3.02,z-1.35+i*0.18),Vector3(x+0.83,3.91,z-1.35+i*0.18),0.013,mats.metal)
	rod(Vector3(x+0.83,3.95,z-1.42),Vector3(x+0.83,3.95,z+1.42),0.025,mats.metal)
	for side in [-1.0,1.0]:
		rod(Vector3(x+0.14,3.95,z+side*1.42),Vector3(x+0.83,3.95,z+side*1.42),0.022,mats.metal)
		box(Vector3(x+0.45,2.84,z+side*1.15),Vector3(0.66,0.10,0.09),mats.metal,Vector3(0,0,-0.4))

func service_details(x: float,z: float,height: float) -> void:
	box(Vector3(x+0.4,0.54,z),Vector3(0.56,0.62,0.88),mats.trim)
	rod(Vector3(x+0.70,0.56,z),Vector3(x+0.72,0.56,z),0.22,mats.ink)
	for i in range(10):
		box(Vector3(x+0.736,0.31+i*0.05,z),Vector3(0.018,0.014,0.72),mats.metal)
	for side in [-1.0,1.0]:
		box(Vector3(x+0.35,0.17,z+side*0.34),Vector3(0.53,0.08,0.12),mats.metal)
	rod(Vector3(x+0.28,0.8,z+0.53),Vector3(x+0.28,2.1,z+0.53),0.032,mats.trim)
	box(Vector3(x+0.25,2.14,z+0.50),Vector3(0.17,0.35,0.25),mats.metal)
	rod(Vector3(x+0.15,2.3,z+0.70),Vector3(x+0.15,height-0.17,z+0.70),0.013,mats.ink)
	rod(Vector3(x+0.15,height-0.17,z-0.70),Vector3(x+0.15,height-0.17,z+0.70),0.014,mats.ink)

func roof(at: Vector3,height: float,variant: int) -> void:
	var slope := 0.29
	var half_width := 3.4
	var peak := height+half_width*tan(slope)
	piece("gable",at+Vector3(0,height+0.48,0),Vector3(6.8,0.96,6.3),mats.plaster)
	for side in [-1.0,1.0]:
		box(at+Vector3(side*1.79,height+0.5,0),Vector3(3.87,0.075,6.96),mats.wood,Vector3(0,0,-side*slope))
		for row in range(12):
			for col in range(23):
				var xx: float = side*(0.05+row*0.305)
				var zz := -3.40+col*0.30
				var yy := peak-absf(xx)*tan(slope)+0.075
				piece("tile",at+Vector3(xx,yy,zz),Vector3.ONE,mats["tile"+str((col*3+row+variant)%4)],Vector3(0,PI if side<0 else 0,-side*slope))
		rod(at+Vector3(side*3.72,height-0.055,-3.48),at+Vector3(side*3.72,height-0.055,3.48),0.050,mats.metal)
	for n in range(24):
		rod(at+Vector3(0,peak+0.12,-3.5+n*0.295),at+Vector3(0,peak+0.12,-3.19+n*0.295),0.13,mats["tile"+str(n%4)])
	# Aerial and small roof access hatch with flashing around its base.
	var aerial := at+Vector3(-1.5,peak-0.2,1.65)
	rod(aerial,aerial+Vector3(0,1.45,0),0.018,mats.metal)
	rod(aerial+Vector3(-0.75,1.1,0),aerial+Vector3(0.75,1.1,0),0.019,mats.metal)
	for i in range(5):
		rod(aerial+Vector3(-0.5+i*0.25,1.1,-0.35),aerial+Vector3(-0.5+i*0.25,1.1,0.35),0.012,mats.metal)

func weather_streak(at: Vector3,size_value: Vector2) -> void:
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/reference_weather.gdshader")
	var mesh := MeshInstance3D.new()
	mesh.name = "SillWeathering"
	var quad := QuadMesh.new()
	quad.size = size_value
	mesh.mesh = quad
	mesh.material_override = m
	mesh.position = at
	mesh.rotation.y = PI/2
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	holder.add_child(mesh,true)

func street_finish() -> void:
	box(Vector3(0,0.054,-2.8),Vector3(5.8,0.018,17.6),mats.road09)
	# Individual paving slabs, with small variation rather than one stretched map.
	for side in [-1.0,1.0]:
		for row in range(29):
			var z := -11.35+row*0.6
			for col in range(3):
				var x: float = side*(3.47+col*0.71)
				box(Vector3(x,0.038,z),Vector3(0.697,0.028,0.584),mats.stone)
			box(Vector3(side*3.02,0.055,z),Vector3(0.21,0.11,0.586),mats.trim)
		for z in [-9.3,-3.7,3.0]:
			box(Vector3(side*2.87,0.070,z),Vector3(0.24,0.025,0.80),mats.ink)
			for slot in range(9):
				box(Vector3(side*2.87,0.087,z-0.35+slot*0.085),Vector3(0.23,0.025,0.025),mats.metal)
	# Utility cover with ring and radial pattern.
	var cover := Vector3(0.72,0.074,-2.7)
	rod(cover,cover+Vector3(0,0.023,0),0.44,mats.metal)
	for i in range(32):
		var a := i*TAU/32
		var b := (i+1)*TAU/32
		rod(cover+Vector3(cos(a)*0.39,0.03,sin(a)*0.39),cover+Vector3(cos(b)*0.39,0.03,sin(b)*0.39),0.012,mats.ink)
	for i in range(7):
		box(cover+Vector3(-0.24+i*0.08,0.028,0),Vector3(0.020,0.014,0.46),mats.ink)
	# Fine irregular cracks and patched edges are geometry, not a repeated stain.
	for start in [Vector3(-1.8,0.070,1.7),Vector3(1.9,0.071,-7.5)]:
		var point: Vector3 = start
		for n in range(18):
			var next: Vector3 = point+Vector3(rng.randf_range(-0.14,0.18),0,rng.randf_range(0.05,0.20))
			rod(point,next,0.006,mats.mortar)
			point = next
	for i in range(140):
		var side := -1.0 if i%2==0 else 1.0
		var at := Vector3(side*rng.randf_range(2.5,2.82),0.075,rng.randf_range(-10.5,5.6))
		box(at,Vector3(0.032,0.008,0.10),mat("leaf_litter"+str(i%3),["79705a","665e59","817765"][i%3]),Vector3(0,rng.randf()*TAU,0))

func garden() -> void:
	# Walls and planting occupy the setback on the opposite pavement.
	for extent in [Vector2(-11.0,0.9),Vector2(2.8,6.5)]:
		var length: float = extent.y-extent.x
		box(Vector3(5.48,0.61,(extent.x+extent.y)/2),Vector3(0.27,1.22,length),mats.mortar)
		solid("GardenBoundary",Vector3(5.48,0.61,(extent.x+extent.y)/2),Vector3(0.27,1.22,length))
		for row in range(5):
			for n in range(int(length/0.47)):
				var z: float = extent.x+0.25+n*0.47+(0.20 if row%2==1 else 0.0)
				if z>extent.y-0.20: continue
				box(Vector3(5.325,0.13+row*0.235,z),Vector3(0.045,0.221,0.451),mats.stone)
		box(Vector3(5.45,1.27,(extent.x+extent.y)/2),Vector3(0.40,0.12,length+0.05),mats.trim)
	for z in [-11.0,0.9,2.8,6.5]:
		box(Vector3(5.44,0.84,z),Vector3(0.45,1.68,0.46),mats.stone)
		box(Vector3(5.44,1.74,z),Vector3(0.53,0.15,0.54),mats.trim)
	for i in range(13):
		rod(Vector3(5.44,0.10,1.04+i*0.13),Vector3(5.44,1.52,1.04+i*0.13),0.015,mats.metal)
	for y in [0.25,1.39]:
		rod(Vector3(5.44,y,0.99),Vector3(5.44,y,2.69),0.025,mats.metal)
	solid("GardenGate",Vector3(5.44,0.8,1.85),Vector3(0.12,1.6,1.9))
	for z in [-9.6,-7.8,-3.7,4.8]:
		shrub(Vector3(5.92,0.65,z),0.9)
	branching_tree(Vector3(7.5,0,-7.0),4.8)
	branching_tree(Vector3(-5.7,0,-11.5),3.1)

func planter(at: Vector3,radius: float) -> void:
	rod(at+Vector3(0,0.05,0),at+Vector3(0,0.39,0),radius,mat("clay","806e60","concrete",1.3))
	rod(at+Vector3(0,0.40,0),at+Vector3(0,0.43,0),radius*1.08,mats.mortar)
	shrub(at+Vector3(0,0.60,0),radius*1.5)

func shrub(at: Vector3,radius: float) -> void:
	for n in range(7):
		var theta := n*2.399
		var pos := at+Vector3(cos(theta)*radius*0.40,float(n%3)*0.11,sin(theta)*radius*0.4)
		piece("leaf",pos,Vector3(radius*1.7,radius*1.5,1),mats.leaves,Vector3(-0.30,theta,0.15))

func branching_tree(at: Vector3,height: float) -> void:
	var trunk: Material = mat("bark","776f64","wood",2.3)
	var top := at+Vector3(0.10,height*0.64,0.1)
	rod(at,top,0.14,trunk)
	for i in range(8):
		var angle := i*2.399
		var end := at+Vector3(cos(angle)*height*0.31,height*(0.72+float(i%3)*0.09),sin(angle)*height*0.31)
		var joint := top.lerp(end,0.6)-Vector3(0,0.25,0)
		rod(top-Vector3(0,height*0.22,0),joint,0.055,trunk)
		rod(joint,end,0.025,trunk)
		for sub in range(3):
			var tip := end+Vector3(cos(angle+sub)*0.40,0.13,sin(angle+sub)*0.4)
			rod(joint,tip,0.012,trunk)
			piece("leaf",tip,Vector3(height*0.52,height*0.39,1),mats.leaves,Vector3(-0.15,angle+sub*0.8,-0.12))
	solid("ReferenceTreeTrunk",at+Vector3(0,1.2,0),Vector3(0.3,2.4,0.3))

func utility_detail() -> void:
	# Refine existing poles in place; their original collision remains unchanged.
	for z in [-10.0,8.5]:
		var at := Vector3(-4.65,0,z)
		for y in [2.1,3.6,4.3]:
			rod(at+Vector3(-0.12,y,0),at+Vector3(0.12,y,0),0.14,mats.metal)
		for i in range(8):
			box(at+Vector3(0.23,4.52+i*0.073,0.235),Vector3(0.36,0.021,0.025),mats.ink)
		for x in [-0.85,0.0,0.85]:
			for ring in range(4):
				rod(at+Vector3(x,6.53+ring*0.06,0),at+Vector3(x,6.557+ring*0.06,0),0.09,mats.trim)
		box(at+Vector3(0.105,1.65,0),Vector3(0.025,0.5,0.15),mats.trim)
		for y in [1.55,1.62,1.69]:
			box(at+Vector3(0.122,y,0),Vector3(0.014,0.020,0.12),mats.ink)
	for offset in [Vector3(-0.3,5.4,0),Vector3(0.27,5.1,0)]:
		cable(Vector3(-4.65,0,-10)+offset,Vector3(-6.23,4.55,-5.8))

func tile_mesh() -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for segment in range(8):
		var a := float(segment)*PI/8
		var b := float(segment+1)*PI/8
		var vertices := [Vector3(0,sin(a)*0.045,cos(a)*0.151),Vector3(0.365,sin(a)*0.045,cos(a)*0.151),Vector3(0,sin(b)*0.045,cos(b)*0.151),Vector3(0.365,sin(b)*0.045,cos(b)*0.151)]
		for index in [0,1,2,2,1,3]:
			var v: Vector3 = vertices[index]
			var angle := a if index<2 else b
			surface.set_normal(Vector3(0,sin(angle)/0.045,cos(angle)/0.151).normalized())
			surface.set_uv(Vector2(v.x/0.365,angle/PI))
			surface.add_vertex(v)
	return surface.commit()

func flush_batches() -> void:
	var roof_mesh := tile_mesh()
	for key in batches.keys():
		var data: Dictionary = batches[key]
		if data.kind!="tile": continue
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = roof_mesh
		mm.instance_count = data.transforms.size()
		for index in range(mm.instance_count):
			mm.set_instance_transform(index,data.transforms[index])
		var node := MultiMeshInstance3D.new()
		node.name = "CeramicTiles"
		node.multimesh = mm
		node.material_override = data.material
		data.parent.add_child(node,true)
		batches.erase(key)
		roof_batches += 1
	super.flush_batches()
