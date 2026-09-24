extends "res://tools/build_reference09.gd"
## Building-by-building authored additions to the existing traversable district.
const SHOPS := [
	["CornerBooks","BOOKSHOP","TSUKI  /  LIBROS USADOS",11.0,7.6,9.0,"798889"],
	["Grocer","GROCERY","INOUE  /  ALIMENTACION",21.0,7.1,6.0,"8b9171"],
	["Arcade","VIDEO_CLUB","HOSHI  /  VIDEO CLUB",18.0,-45.4,12.0,"85778c"],
	["Clinic","CAFE","KISSA  /  CAFE Y DISCOS",-10.0,-45.9,7.0,"95816c"],
	["RepairShop","IZAKAYA","AKARI  /  IZAKAYA",-11.0,-80.4,9.0,"976660"],
	["PrintShop","ARCADE","GAME CORNER  /  100 YEN",12.0,-81.4,10.0,"647d85"],
]
func build() -> void:
	if DisplayServer.get_name() == "headless":
		push_error("Author with a real renderer")
		city.free()
		quit(1)
		return
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	city.free()
	city = load("res://art/city08/Neighborhood.tscn").instantiate()
	city.get_node("Residence01").free()
	city.get_node("Residence01Collision").free()
	palette()
	mat("warm","c4b598","",1,.25)
	mat("steel","555963","concrete",1.1)
	mat("paper","d0c5ac")
	mat("bottle","788e80")
	var reference: Node3D = load("res://art/reference09/ReferenceStreet.tscn").instantiate()
	# Flatten it before assigning ownership. Keeping both an instance and all
	# explicit children would replace/leak the original instance's nodes.
	reference.scene_file_path = ""
	city.add_child(reference)
	rng.seed = 90924
	var detailed := 2
	for item in SHOPS:
		holder = city.get_node(str(item[0])+"/Upper")
		if holder.has_node("ShopName"):
			holder.get_node("ShopName").text = ""
		front(item)
	# Residential blocks each get a distinct layer of lived-in details.
	for node in city.get_children():
		if node.get_script() != load("res://scripts/art/CityCutaway.gd"):
			continue
		if str(node.name).begins_with("Skyline"):
			continue
		detailed += 1
		holder = node.get_node("Upper")
		var bounds: AABB = node.bounds
		var c := bounds.get_center()
		var z := bounds.end.z + .20
		var h := bounds.size.y
		# Tinted plaster material on the large wall mass. Retain glazing and trim.
		for mesh in holder.get_children():
			if mesh is MultiMeshInstance3D and mesh.material_override != null and mesh.material_override.resource_name.begins_with("wall_"):
				var plaster: ShaderMaterial = mats.plaster.duplicate()
				plaster.set_shader_parameter("tint",mesh.material_override.albedo_color)
				mesh.material_override = plaster
		# Gutters and downpipes, utility boxes, ceramic pots and doormats.
		for x in [bounds.position.x+.28,bounds.end.x-.28]:
			rod(Vector3(x,.2,z),Vector3(x,h-.05,z),.035,mats.metal)
			box(Vector3(x,1.3,z+.05),Vector3(.22,.36,.16),mats.trim)
			for band in [1.1,2.8,4.2]:
				if band<h:
					box(Vector3(x,band,z+.012),Vector3(.12,.04,.10),mats.metal)
		if str(node.name).begins_with("Outer") or str(node.name) in ["Residence02","SouthHomes","Tenements","Apartments"]:
			var x := c.x - bounds.size.x*.3
			box(Vector3(x,.06,z+.32),Vector3(.8,.05,.6),mats.wood)
			box(Vector3(x+.7,1.55,z+.03),Vector3(.25,.38,.07),mats.metal)
			box(Vector3(x+1.5,.18,z+.32),Vector3(.45,.36,.42),mats.cedar)
			for i in range(5):
				piece("leaf",Vector3(x+1.5,.54,z+.30),Vector3(.40,.48,1),mats.leaves,Vector3(0,float(i)*.65,.1))
			if h>5:
				for i in range(3):
					box(Vector3(c.x-.8+i*.6,4.16,z+.22),Vector3(.43,.66,.055),mat("laundry"+str(i),["999caa","aea895","788591"][i]),Vector3(0,0,.035*i))
			sign_text("HouseNumber",Vector3(x+.68,1.8,z+.12),str(10+node.get_index()),Color("c3c1b4"),15)
	# School facade: many individual panes, notice cases, clock and bicycle stands.
	holder = city.get_node("School/Upper")
	for x in [-23,-20,-17,-14,-11]:
		box(Vector3(x,1.3,-20.91),Vector3(1.7,1.0,.12),mats.wood)
		for i in range(3):
			box(Vector3(x-.5+i*.5,1.3,-20.83),Vector3(.37,.71,.025),mats.paper)
	sign_text("SchoolSub",Vector3(-17,4.0,-20.81),"MUNICIPAL  /  PABELLON B",Color("c0baa6"),30)
	holder = city
	for x in [-24.0,-22.0]:
		bicycle(Vector3(x,0,-19.3))
	# Public park details keep every existing main path clear.
	for at in [Vector3(23,0,-35.5),Vector3(8,0,-35.5)]:
		box(at+Vector3(0,.55,0),Vector3(.45,1.1,.45),mats.metal)
		box(at+Vector3(0,1.11,0),Vector3(.35,.025,.35),mats.ink)
	sign_text("ParkName",Vector3(23.3,1.5,-19.5),"PARQUE DEL ALCANFOR",Color("c3c1aa"),25)
	for x in [22.8,23.8]:
		rod(Vector3(x,0,-19.5),Vector3(x,1.8,-19.5),.028,mats.wood)
	flush_batches()
	await process_frame
	await RenderingServer.frame_post_draw
	assign_owners(city)
	var packed := PackedScene.new()
	if packed.pack(city) != OK or ResourceSaver.save(packed,"res://art/reference09/Neighborhood.tscn") != OK:
		push_error("Failed to save living district")
		quit(1)
		return
	print("LIVING_CITY09_BUILT shops=6 buildings_detailed=",detailed," batches=",batches.size())
	city.free()
	quit()

func front(item: Array) -> void:
	var kind: String = item[1]
	var x: float = item[3]
	var z: float = item[4]
	var w: float = item[5]
	var accent := mat(kind+"_accent",str(item[6]),"concrete",.8)
	# A deep shopfront with visible shelves behind the side windows; central door is gameplay.
	box(Vector3(x,1.45,z+.14),Vector3(w,2.7,.32),mats.wood)
	box(Vector3(x,3.05,z+.27),Vector3(w,.72,.22),accent)
	sign_text("NewShopName",Vector3(x,3.08,z+.405),str(item[2]),Color("d0c7b0"),29)
	for side in [-1.0,1.0]:
		var wx: float = x+side*w*.30
		box(Vector3(wx,1.45,z+.34),Vector3(w*.29,1.78,.10),mats.ink)
		box(Vector3(wx,1.42,z+.43),Vector3(w*.275,1.63,.04),mat("shopglass","526266"))
		for row in range(3):
			for col in range(5):
				var px: float = wx-w*.11+col*w*.053
				var py := .9+row*.46
				var product_color: String = ["8c8f85","a8967c","747889","92777a"][(row+col)%4]
				box(Vector3(px,py,z+.467),Vector3(.20,.28,.025),mat(product_color,product_color))
				box(Vector3(px,py-.035,z+.487),Vector3(.14,.04,.012),mats.paper)
		for frame_x in [wx-w*.15,wx+w*.15,wx]:
			box(Vector3(frame_x,1.45,z+.50),Vector3(.055,1.95,.12),mats.metal)
		box(Vector3(wx,.46,z+.55),Vector3(w*.32,.12,.36),mats.trim)
	# Canvas awning with muted alternating panels.
	for panel in range(16):
		box(Vector3(x-w/2+(panel+.5)*w/16,2.6,z+.79),Vector3(w/16,.075,1.15),accent if panel%2==0 else mats.curtain,Vector3(.15,0,0))
	# Wall menu / price card, outside the interactive centre.
	box(Vector3(x-w*.44,1.55,z+.5),Vector3(.48,.85,.08),mats.ink)
	sign_text("Menu",Vector3(x-w*.44,1.57,z+.555),"100\n300\n500",Color("c5c0ab"),19)
	point_light(Vector3(x,2.45,z+1.1),Color("c7b391"),.6,5)
	if kind=="IZAKAYA":
		for lx in [x-2,x+2]:
			piece("rod",Vector3(lx,2.2,z+.8),Vector3(.32,.8,.32),accent)
			box(Vector3(lx,2.62,z+.8),Vector3(.52,.08,.52),mats.ink)
			sign_text("Lantern",Vector3(lx,2.2,z+1.14),"SAKE",Color("ded0b5"),18)
		for i in range(5):
			box(Vector3(x-.64+i*.32,2.13,z+.44),Vector3(.29,.42,.025),accent)
	if kind=="VIDEO_CLUB":
		sign_text("VideoPoster",Vector3(x+3.8,2,z+.55),"VHS\nRENTAL\n1998",Color("c4b2b5"),22)
	if kind=="GROCERY":
		for dx in [-2,2]:
			box(Vector3(x+dx,.23,z+.8),Vector3(.8,.46,.65),mats.cedar)
			for col in range(4):
				box(Vector3(x+dx-.24+col*.16,.53,z+.8),Vector3(.12,.13,.12),mats.bottle)
	if kind=="CAFE":
		sign_text("CafeWindow",Vector3(x-1.8,1.45,z+.54),"COFFEE\n350",Color("d2c5a8"),23)

func bicycle(at: Vector3) -> void:
	# Open wire wheels and triangular frame, distinct from street furniture.
	for z in [-.60,.60]:
		var c := at+Vector3(0,.36,z)
		for n in range(16):
			var a := n*TAU/16
			var b := (n+1)*TAU/16
			rod(c+Vector3(0,sin(a)*.32,cos(a)*.32),c+Vector3(0,sin(b)*.32,cos(b)*.32),.016,mats.ink)
	var crank := at+Vector3(0,.35,0)
	var saddle := at+Vector3(0,.87,-.28)
	var handle := at+Vector3(0,.95,.5)
	for line in [[crank,saddle],[crank,handle],[saddle,handle],[saddle,at+Vector3(0,.36,-.6)],[handle,at+Vector3(0,.36,.6)]]:
		rod(line[0],line[1],.025,mats.metal)
	box(saddle,Vector3(.22,.07,.27),mats.ink)
	rod(handle+Vector3(-.25,0,0),handle+Vector3(.25,0,0),.02,mats.metal)
