extends "res://scripts/world/PrologueLocation.gd"
## Six independent interiors; all interaction and population comes from World Core.
const LAYOUT = preload("res://scripts/world/CityLayout.gd")

func _on_snapshot(snapshot: Dictionary) -> void:
	if str(snapshot.get("player",{}).get("location","")) == location_id:
		get_node("HUD/Hint").text = LAYOUT.TITLES.get(location_id,location_id) + "  //  E: HABLAR / SALIR   J: FICHAS"

func _build_world() -> void:
	var wood := Color("716255")
	var paper := Color("b5af99")
	var dark := Color("34343c")
	_solid("Floor",Vector3(0,-0.2,0),Vector3(14,0.4,17),Color("817b70"))
	_solid("WestWall",Vector3(-7.1,1.8,0),Vector3(.24,3.6,17),Color("8e8b7f"))
	_solid("BackWall",Vector3(0,1.8,-8.3),Vector3(14,3.6,.24),Color("9f9a89"))
	for wall in ["WestWall","BackWall"]:
		var surface: MeshInstance3D = get_node(wall).get_child(0)
		var plaster: StandardMaterial3D = surface.material_override.duplicate()
		plaster.albedo_texture = load("res://art/reference09/materials/plaster-albedo.png")
		plaster.uv1_scale = Vector3.ONE*.28
		surface.material_override = plaster
	_solid("EastWall",Vector3(7.1,.3,0),Vector3(.24,.6,17),wood)
	for row in range(26):
		_detail("Floorboard",Vector3(0,.012,-8+row*.63),Vector3(14,.012,.016),wood.darkened(.25))
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("20212b")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color("a6a7b1")
	environment.environment.ambient_light_energy = .7
	environment.environment.ssao_enabled = true
	environment.environment.ssao_intensity = 1.1
	add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-58,-30,0)
	sun.light_color = Color("c8c2b1")
	sun.light_energy = .7
	sun.shadow_enabled = true
	add_child(sun)
	_light(Vector3(1,3.3,-3),Color("d8c598"),1.05)
	_light(Vector3(-3,3.2,3),Color("a0b9b9"),.65)
	_door("BARRIO","APARTMENT_DISTRICT",Vector3(0,1.1,8.1),Color("64747a"))
	for x in [-4.1,4.1]:
		_solid("FrontWall",Vector3(x,.32,8.25),Vector3(5.7,.64,.24),wood)
	for x in [-.86,.86]:
		_detail("DoorFrame",Vector3(x,1.18,8.1),Vector3(.12,2.36,.28),wood)
	_detail("DoorLintel",Vector3(0,2.36,8.1),Vector3(1.84,.12,.28),wood)
	_detail("EntranceMat",Vector3(0,.015,7.5),Vector3(1.7,.018,.85),dark)
	_detail("WallSkirting",Vector3(0,.24,-8.14),Vector3(14,.48,.09),wood)
	_detail("WestSkirting",Vector3(-6.94,.24,0),Vector3(.09,.48,17),wood)
	_sign(LAYOUT.TITLES.get(location_id,location_id).to_upper(),Vector3(0,2.95,-8.03),paper)
	# Counter with drawers and a late-90s cash register.
	_solid("DeskCounter",Vector3(4.3,.53,-6.2),Vector3(3.8,1.06,1.2),wood)
	_detail("CounterTop",Vector3(4.3,1.11,-6.2),Vector3(4.0,.12,1.34),dark)
	for x in [3.1,4.3,5.5]:
		_detail("Drawer",Vector3(x,.6,-5.58),Vector3(1.05,.55,.025),wood.lightened(.08))
		_detail("Handle",Vector3(x,.67,-5.54),Vector3(.3,.025,.035),paper)
	_detail("CashRegister",Vector3(4.9,1.33,-6.1),Vector3(.62,.34,.53),paper)
	_detail("RegisterKeys",Vector3(4.9,1.5,-5.96),Vector3(.49,.025,.22),dark)
	_detail("RegisterDisplay",Vector3(4.9,1.62,-6.22),Vector3(.44,.16,.12),dark)
	_detail("DisplayDigits",Vector3(4.9,1.63,-6.15),Vector3(.34,.09,.014),Color("71a49c"),true)
	# Analogue phone, notices, clock, wall sockets; no modern screens.
	_detail("Telephone",Vector3(3.0,1.25,-6.1),Vector3(.4,.16,.28),dark)
	_detail("Handset",Vector3(3.0,1.36,-6.1),Vector3(.46,.08,.13),dark)
	_detail("NoticeBoard",Vector3(-4.9,2.25,-8.13),Vector3(2.2,1.1,.06),wood)
	for i in range(6):
		_detail("PaperNotice",Vector3(-5.6+float(i%3)*.57,2.02+floorf(float(i)/3)*.43,-8.07),Vector3(.45,.32,.018),paper)
	_clock(Vector3(5.7,2.8,-8.09))
	_detail("Fluorescent",Vector3(0,3.2,-8.03),Vector3(3.2,.09,.2),Color("a6b1a8"),true)
	# Tall posters, cartons, a returns trolley and ledgers break up the empty
	# perimeter while leaving the verified central activity circuits open.
	for i in range(3):
		var z := -4.8+float(i)*3.2
		_detail("PosterFrame",Vector3(-6.94,2.12,z),Vector3(.08,1.48,.99),dark)
		_detail("Poster",Vector3(-6.88,2.12,z),Vector3(.025,1.30,.81),[Color("8f877c"),Color("737e84"),Color("8b747e")][i])
		for band in range(5):
			_detail("PosterPrint",Vector3(-6.855,1.66+band*.16,z),Vector3(.013,.032,.55),paper)
	for i in range(4):
		_detail("Carton",Vector3(5.9,.19+floorf(float(i)/2)*.39,5.2+float(i%2)*.65),Vector3(.65,.38,.57),Color("95856f"))
		_detail("CartonTape",Vector3(5.9,.39+floorf(float(i)/2)*.39,5.2+float(i%2)*.65),Vector3(.10,.013,.57),paper)
	_detail("Ledger",Vector3(3.7,1.195,-5.99),Vector3(.36,.045,.44),paper)
	for z in [-4,0,4]:
		_detail("WallSocket",Vector3(-6.94,.5,z),Vector3(.025,.18,.12),paper)
	if location_id in ["VIDEO_CLUB","BOOKSHOP","GROCERY"]:
		_stocked_shelf(Vector3(-5.5,0,-6.3),6,location_id)
		for z in [-2.6,1.6]:
			_stocked_shelf(Vector3(-4.4,0,z),4,location_id)
		if location_id == "VIDEO_CLUB":
			_solid("TVStand",Vector3(.4,.42,-6.7),Vector3(1.4,.84,.95),wood)
			_crt(Vector3(.4,1.35,-6.7))
			_stocked_shelf(Vector3(-.1,0,-7.55),6,"VIDEO_CLUB")
			_stocked_shelf(Vector3(5.7,0,.0),3,"VIDEO_CLUB")
			_sign("VHS · DEVOLUCIONES  /  REBOBINAR",Vector3(-2,2.5,-7.8),paper)
		elif location_id == "BOOKSHOP":
			_stocked_shelf(Vector3(-.1,0,-7.55),6,"BOOKSHOP")
			_stocked_shelf(Vector3(5.7,0,.0),3,"BOOKSHOP")
			_sign("LIBROS USADOS · REVISTAS · MANGA",Vector3(-2,2.5,-7.8),paper)
		else:
			_sign("PRODUCTOS DEL DÍA · ENCARGOS",Vector3(-2,2.5,-7.8),paper)
			_detail("Fridge",Vector3(6,.95,-2.3),Vector3(1.1,1.9,1.8),paper)
			_detail("FridgeGlass",Vector3(5.43,1.1,-2.3),Vector3(.025,1.35,1.6),Color("546b68"))
	elif location_id == "ARCADE":
		for z in [-5,-2,1,4]:
			_cabinet(Vector3(-5.5,0,z),false)
			_cabinet(Vector3(5.8,0,z),true)
		_sign("GAME CORNER  /  100 YEN",Vector3(-2.5,2.6,-7.8),paper)
	else:
		for z in [-3.0,1.3,4.5]:
			_table(Vector3(-4.3,0,z),wood)
		if location_id == "IZAKAYA":
			_stocked_shelf(Vector3(-4.5,0,-6.5),6,"BOTTLES")
			_sign("AKARI · COMIDAS Y BEBIDAS",Vector3(-2.2,2.5,-7.8),paper)
			for x in [-4,-1,2]:
				_detail("PaperLantern",Vector3(x,2.8,-3),Vector3(.5,.75,.5),Color("aa7860"),true)
		else:
			_detail("CoffeeMachine",Vector3(5.8,1.5,-6.4),Vector3(.6,.7,.5),dark)
			_solid("TVStand",Vector3(-5.5,.52,-6.6),Vector3(1.4,1.04,.95),wood)
			_crt(Vector3(-5.5,1.6,-6.6))
			_sign("KISSA · CAFÉ · DISCOS",Vector3(-2.2,2.5,-7.8),paper)

func _clock(at: Vector3) -> void:
	_detail("ClockFrame",at,Vector3(.6,.6,.05),Color("45464a"))
	_detail("ClockFace",at+Vector3(0,0,.033),Vector3(.5,.5,.02),Color("c4beaa"))
	_detail("ClockHand",at+Vector3(0,.09,.05),Vector3(.025,.2,.012),Color("39383d"))
	_detail("ClockMinute",at+Vector3(.09,0,.052),Vector3(.20,.02,.012),Color("39383d"))

func _stocked_shelf(at: Vector3, columns: int, kind: String) -> void:
	var w := columns*.53
	_solid("Shelf",at+Vector3(0,.9,0),Vector3(w+.2,1.8,.64),Color("4e4b47"))
	for level in range(3):
		var y := .38+level*.52
		_detail("ShelfLip",at+Vector3(0,y-.17,.37),Vector3(w+.26,.045,.08),Color("aaa48e"))
		for col in range(columns*2):
			var x := -w/2+.14+col*.255
			var tint: Color = [Color("78868b"),Color("a7987d"),Color("776878"),Color("78806a")][(level+col)%4]
			var size := Vector3(.21,.32,.12)
			if kind in ["GROCERY","BOTTLES"]:
				size = Vector3(.16,.27,.16)
			_detail("Stock",at+Vector3(x,y,.39),size,tint)
			_detail("SpineLabel",at+Vector3(x,y-.035,.46),Vector3(.14,.055,.012),Color("c5bca6"))

func _table(at: Vector3, wood: Color) -> void:
	_solid("DeskTable",at+Vector3(0,.73,0),Vector3(1.65,.10,1.05),wood)
	for x in [-.65,.65]:
		for z in [-.35,.35]:
			_detail("TableLeg",at+Vector3(x,.37,z),Vector3(.07,.74,.07),wood.darkened(.2))
	for z in [-.85,.85]:
		_solid("Chair",at+Vector3(0,.25,z),Vector3(.52,.5,.5),wood.darkened(.18))
		_detail("ChairBack",at+Vector3(0,.72,z+signf(z)*.23),Vector3(.52,.42,.07),wood)
	_detail("Menu",at+Vector3(.35,.80,0),Vector3(.2,.02,.28),Color("c7bfa7"))
	_detail("Cup",at+Vector3(-.3,.85,0),Vector3(.12,.15,.12),Color("afa897"))

func _crt(at: Vector3) -> void:
	_detail("CRT",at,Vector3(1.0,.78,.68),Color("535454"))
	_detail("CRTScreen",at+Vector3(-.05,.035,.353),Vector3(.75,.55,.018),Color("66837b"),true)
	_detail("VCR",at+Vector3(0,-.48,0),Vector3(.92,.17,.52),Color("34363c"))
	_detail("TapeSlot",at+Vector3(-.12,-.48,.267),Vector3(.42,.04,.018),Color("171c22"))

func _cabinet(at: Vector3, flipped: bool) -> void:
	_solid("ArcadeCabinet",at+Vector3(0,.94,0),Vector3(1.0,1.88,1.0),Color("484b55"))
	_detail("ArcadeScreen",at+Vector3(0,1.35,.511),Vector3(.75,.58,.025),Color("667d87") if flipped else Color("887485"),true)
	_detail("ControlPanel",at+Vector3(0,.9,.63),Vector3(.94,.10,.36),Color("928b7a"))
	for x in [-.22,.22]:
		_detail("Joystick",at+Vector3(x,1.03,.63),Vector3(.06,.2,.06),Color("333a40"))
	_detail("CoinSlot",at+Vector3(.22,.55,.514),Vector3(.04,.12,.025),Color("bab0a0"))
