extends SceneTree
## Sculpted cross-section meshes, saved as a playable scene. No server calls.
const OUT := "res://art/characters/LainSlender.tscn"
var rig: Node3D
var materials := {}

func _initialize() -> void:
	call_deferred("build")

func mat(color: String) -> StandardMaterial3D:
	if not materials.has(color):
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(color)
		m.roughness = 0.93
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		materials[color] = m
	return materials[color]

func mesh_node(label: String, mesh: Mesh, color: String, parent: Node3D = null) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = label
	node.mesh = mesh
	node.material_override = mat(color)
	(rig if parent == null else parent).add_child(node, true)
	return node

func loft(label: String, rings: Array, color: String, parent: Node3D = null, exponent: float = 0.75, count: int = 20, pleats: float = 0.0) -> MeshInstance3D:
	# Rings are y, half-width, half-depth, centre-z. Shapes taper at joints.
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for ring in rings:
		for i in range(count):
			var angle := i * TAU / count
			var fold := 1.0 + pleats * (1.0 if i % 2 == 0 else -1.0)
			st.set_uv(Vector2(float(i)/count, ring.x))
			st.add_vertex(Vector3(signf(sin(angle))*pow(absf(sin(angle)),exponent)*ring.y*fold,ring.x,signf(cos(angle))*pow(absf(cos(angle)),exponent)*ring.z*fold+ring.w))
	for row in range(rings.size()-1):
		for i in range(count):
			var a := row*count+i
			var b := row*count+(i+1)%count
			for index in [a,a+count,b,b,a+count,b+count]:
				st.add_index(index)
	# Separate cap normals from the sides: avoids pinched highlights at cuffs.
	st.set_smooth_group(1)
	for end in range(2):
		var ring: Vector4 = rings[0 if end==0 else rings.size()-1]
		var base: int = rings.size()*count + end*count
		for i in range(count):
			var angle := i * TAU / count
			var fold := 1.0 + pleats * (1.0 if i % 2 == 0 else -1.0)
			st.add_vertex(Vector3(signf(sin(angle))*pow(absf(sin(angle)),exponent)*ring.y*fold,ring.x,signf(cos(angle))*pow(absf(cos(angle)),exponent)*ring.z*fold+ring.w))
		for i in range(1,count-1):
			st.add_index(base)
			st.add_index(base+(i if end==0 else i+1))
			st.add_index(base+(i+1 if end==0 else i))
	st.generate_normals()
	return mesh_node(label,st.commit(),color,parent)

func patch(label: String, points: Array, color: String, parent: Node3D = null) -> MeshInstance3D:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in range(1,points.size()-1):
		for p in [points[0],points[i+1],points[i]]:
			st.add_vertex(p)
	st.generate_normals()
	return mesh_node(label,st.commit(),color,parent)

func joint(label: String, at: Vector3, parent: Node3D = null) -> Node3D:
	var node := Node3D.new()
	node.name = label
	node.position = at
	(rig if parent==null else parent).add_child(node)
	return node

func head() -> void:
	loft("Face",[
		Vector4(.472,.024,.036,.021),Vector4(.486,.061,.056,.02),
		Vector4(.527,.093,.072,.011),Vector4(.60,.107,.084,0),
		Vector4(.674,.10,.083,-.008),Vector4(.718,.065,.059,-.011),
		Vector4(.734,.009,.012,-.014)],"c5b2a4",null,1.0,28)
	loft("Neck",[Vector4(.386,.042,.037,0),Vector4(.448,.038,.032,0),Vector4(.487,.043,.037,0)],"c5b2a4")
	# A continuous bob shell: high over the forehead, longer at the nape.
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n := 32
	for row in range(12):
		for i in range(n):
			var theta := i*TAU/n
			var end := lerpf(1.21,2.27,(1.0-cos(theta))*0.5)
			var phi := 0.015 + end*row/11.0
			st.add_vertex(Vector3(.121*sin(phi)*sin(theta),.620+.142*cos(phi),-.014+.103*sin(phi)*cos(theta)))
	for row in range(11):
		for i in range(n):
			var a := row*n+i
			var b := row*n+(i+1)%n
			for index in [a,b,a+n,b,b+n,a+n]:
				st.add_index(index)
	st.generate_normals()
	mesh_node("BobHair",st.commit(),"382c2b")
	var lock := loft("LongSideLock",[Vector4(.347,.008,.012,.08),Vector4(.38,.018,.023,.071),Vector4(.45,.025,.03,.047),Vector4(.56,.026,.042,.023),Vector4(.667,.025,.051,-.004)],"3d2e2b")
	lock.position.x = .105
	patch("FringeLeft",[Vector3(-.105,.68,.062),Vector3(-.068,.717,.072),Vector3(.018,.713,.075),Vector3(-.015,.65,.09),Vector3(-.040,.658,.092),Vector3(-.057,.634,.089),Vector3(-.084,.656,.079)],"382c2b")
	patch("FringeRight",[Vector3(.012,.713,.074),Vector3(.076,.702,.069),Vector3(.112,.65,.047),Vector3(.082,.636,.076),Vector3(.052,.654,.089),Vector3(.029,.644,.094)],"3d2e2b")
	patch("HairClip",[Vector3(.112,.581,.066),Vector3(.122,.583,.065),Vector3(.112,.637,.069),Vector3(.102,.635,.073)],"c1b08c")
	for side in [-1,1]:
		var x: float = side*.043
		patch("Eye",[Vector3(x-.025,.611,.081),Vector3(x-.013,.619,.083),Vector3(x+.016,.617,.083),Vector3(x+.026,.609,.08),Vector3(x+.013,.598,.084),Vector3(x-.014,.599,.084)],"d6cdc1")
		patch("Iris",[Vector3(x-.008,.615,.085),Vector3(x+.008,.615,.085),Vector3(x+.008,.601,.087),Vector3(x,.598,.087),Vector3(x-.008,.602,.087)],"433638")
		patch("UpperLid",[Vector3(x-.026,.613,.085),Vector3(x-.013,.622,.085),Vector3(x+.016,.620,.085),Vector3(x+.027,.611,.083),Vector3(x+.015,.615,.086),Vector3(x-.012,.617,.086)],"423333")
		patch("Brow",[Vector3(x-.02,.635,.083),Vector3(x+.019,.634,.083),Vector3(x+.019,.638,.083),Vector3(x-.02,.639,.083)],"64504a")
	patch("Nose",[Vector3(-.011,.574,.087),Vector3(0,.557,.109),Vector3(.009,.574,.087),Vector3(0,.592,.086)],"bea698")
	patch("Mouth",[Vector3(-.012,.530,.085),Vector3(.013,.530,.085),Vector3(.008,.527,.086),Vector3(-.009,.527,.086)],"956f6c")

func body() -> void:
	loft("TailoredBlouse",[Vector4(-.127,.133,.073,0),Vector4(-.06,.121,.074,0),Vector4(.10,.108,.072,0),Vector4(.25,.132,.077,0),Vector4(.337,.148,.066,0),Vector4(.376,.135,.055,-.006),Vector4(.407,.045,.036,0)],"73787a",null,.64,24)
	for side in [-1,1]:
		patch("Collar",[Vector3(side*.02,.404,.041),Vector3(side*.083,.377,.062),Vector3(side*.058,.317,.079),Vector3(side*.009,.369,.062)],"c7c6b9")
	patch("Ribbon",[Vector3(-.018,.360,.078),Vector3(.018,.360,.078),Vector3(.014,.225,.083),Vector3(0,.208,.085),Vector3(-.014,.225,.083)],"673b45")
	patch("BlouseSeam",[Vector3(-.003,.207,.082),Vector3(.003,.207,.082),Vector3(.003,-.101,.077),Vector3(-.003,-.101,.077)],"636c70")
	loft("PleatedSkirt",[Vector4(-.368,.195,.112,.002),Vector4(-.25,.172,.103,0),Vector4(-.135,.137,.081,0),Vector4(-.102,.13,.078,0)],"424e48",null,.8,48,.038)
	loft("Waistband",[Vector4(-.133,.138,.082,0),Vector4(-.101,.132,.079,0)],"3c4641",null,.8,24)
	var bag := loft("Satchel",[Vector4(.045,.101,.022,-.105),Vector4(.068,.116,.047,-.105),Vector4(.276,.11,.047,-.105),Vector4(.30,.08,.03,-.105)],"695c54",null,.48,16)
	bag.position.z=-.008
	for side in [-1,1]:
		patch("SatchelStrap",[Vector3(side*.10,.354,-.048),Vector3(side*.121,.347,-.058),Vector3(side*.092,.16,-.090),Vector3(side*.076,.17,-.096)],"9b8b72")

func limbs() -> void:
	for side in [-1,1]:
		var prefix := "Left" if side==-1 else "Right"
		var arm := joint(prefix+"Arm",Vector3(side*.145,.339,0))
		arm.rotation.z = side*.055
		loft("Sleeve",[Vector4(-.439,.026,.026,.031),Vector4(-.32,.031,.031,.019),Vector4(-.23,.034,.033,-.002),Vector4(-.11,.038,.035,-.002),Vector4(-.025,.045,.04,0),Vector4(.025,.019,.025,0)],"73787a",arm,.7,16)
		loft("Cuff",[Vector4(-.448,.029,.028,.032),Vector4(-.421,.030,.028,.028)],"a9aaa2",arm,.64,16)
		loft("Hand",[Vector4(-.553,.012,.017,.043),Vector4(-.534,.023,.02,.042),Vector4(-.476,.025,.022,.036),Vector4(-.441,.020,.018,.032)],"c5b2a4",arm,.74,16)
		var leg := joint(prefix+"Leg",Vector3(side*.069,-.126,0))
		loft("Thigh",[Vector4(-.328,.033,.034,.003),Vector4(-.245,.039,.042,0),Vector4(-.08,.052,.05,0),Vector4(.012,.05,.047,0)],"bca99d",leg,.93,20)
		var knee := joint("Knee",Vector3(0,-.315,0),leg)
		loft("Calf",[Vector4(-.302,.022,.025,-.002),Vector4(-.25,.026,.029,-.004),Vector4(-.13,.036,.034,-.01),Vector4(-.03,.032,.032,0),Vector4(.013,.034,.034,.002)],"bca99d",knee,.92,20)
		loft("Sock",[Vector4(-.327,.024,.028,.002),Vector4(-.23,.027,.03,-.003)],"aead9f",knee,.88,20)
		loft("Loafer",[Vector4(-.418,.042,.09,.036),Vector4(-.402,.047,.096,.036),Vector4(-.370,.041,.086,.035),Vector4(-.327,.026,.043,.010)],"302f31",knee,.65,20)
		loft("Sole",[Vector4(-.422,.043,.091,.036),Vector4(-.407,.046,.095,.036)],"25252a",knee,.64,20)

func own(node: Node) -> void:
	for child in node.get_children():
		child.owner=rig
		own(child)

func build() -> void:
	rig=Node3D.new()
	rig.name="Silhouette"
	rig.set_script(load("res://scripts/art/SlenderAvatar.gd"))
	head()
	body()
	limbs()
	own(rig)
	var packed := PackedScene.new()
	if packed.pack(rig)!=OK or ResourceSaver.save(packed,OUT)!=OK:
		push_error("Cannot save slender avatar")
		quit(1)
		return
	rig.free()
	print("SLENDER_AVATAR_SAVED")
	quit()
