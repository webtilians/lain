extends Node3D
## Small analogue relay cabinets and covered personnel; collision routes stay open.
const POSITIONS := {
	"STATION":["RELAY_STATION",Vector3(-3.6,0,-.3),Vector3(-1.8,0,-1.8)],
	"SCHOOL_LAB":["RELAY_SCHOOL",Vector3(5.6,0,2.5),Vector3(4.4,0,4.5)],
	"VIDEO_CLUB":["RELAY_VIDEO",Vector3(-5.6,0,5.3),Vector3(-3.6,0,4.6)],
}
var location := ""
var relay := ""
var cabinet: Node3D
var operative: Node3D
var cabinet_label: Label3D
var operative_label: Label3D
var status_lamp: MeshInstance3D
var archivist: Node3D
var archivist_label: Label3D
const RECORDS_POSITIONS := {
	"STATION":Vector3(3.0,0,-1.8),
	"SCHOOL_LAB":Vector3(5.2,0,-3.5),
	"VIDEO_CLUB":Vector3(3.2,0,3.3),
}

func _ready() -> void:
	if not POSITIONS.has(location): return
	var data: Array=POSITIONS[location]
	relay=data[0]
	cabinet=anchor("RelayCabinet",data[1]+Vector3(0,.9,0),false)
	box(cabinet,Vector3.ZERO,Vector3(.72,1.8,.44),Color("4c5359"))
	box(cabinet,Vector3(0,.02,.232),Vector3(.62,1.55,.025),Color("85867b"))
	for row in range(5):
		box(cabinet,Vector3(0,.50-row*.07,.25),Vector3(.46,.023,.025),Color("333b40"))
	box(cabinet,Vector3(.21,-.16,.26),Vector3(.025,.14,.026),Color("b1ab8c"))
	status_lamp=box(cabinet,Vector3(-.2,.17,.26),Vector3(.065,.045,.03),Color("95b399"))
	cabinet_label=caption(cabinet,"Armario de enlace · E",1.4)
	operative=anchor("Maintenance",data[2],true)
	var model: Node3D=load("res://art/characters/LainSlender.tscn").instantiate()
	model.set_script(load("res://scripts/art/CitizenAvatar.gd"))
	model.configure("worker",101+POSITIONS.keys().find(location))
	operative.add_child(model)
	operative_label=caption(operative,"Mantenimiento · E",2.25)
	if WorldApi.snapshot.get("network_conflict",{}).get("multiple_operators",false):
		archivist=anchor("RecordsStaff",RECORDS_POSITIONS[location],true)
		archivist.set("faction","NOEMA")
		var records_model: Node3D=load("res://art/characters/LainSlender.tscn").instantiate()
		records_model.set_script(load("res://scripts/art/CitizenAvatar.gd"))
		records_model.configure("teacher",201+POSITIONS.keys().find(location))
		archivist.add_child(records_model)
		# A folder distinguishes the records staff without revealing allegiance.
		box(archivist,Vector3(.25,1.05,-.12),Vector3(.30,.38,.07),Color("7e666d"))
		archivist_label=caption(archivist,"Personal de registros · E",2.25)
	# The cabinet alone blocks movement; people use the same lightweight
	# nonblocking interaction bodies as the existing civilian population.
	var body:=StaticBody3D.new()
	var collision:=CollisionShape3D.new()
	var shape:=BoxShape3D.new()
	shape.size=Vector3(.72,1.8,.44)
	collision.shape=shape
	body.add_child(collision)
	cabinet.add_child(body)

func anchor(title: String, at: Vector3, person: bool) -> Node3D:
	var node:=Node3D.new()
	node.name=title
	node.position=at
	node.set_script(load("res://scripts/world/ConflictInteractable.gd"))
	node.set("relay",relay)
	node.set("personnel",person)
	add_child(node)
	return node

func box(parent: Node3D, at: Vector3, size: Vector3, color: Color) -> MeshInstance3D:
	var mesh:=MeshInstance3D.new()
	var shape:=BoxMesh.new()
	shape.size=size
	mesh.mesh=shape
	mesh.position=at
	var mat:=StandardMaterial3D.new()
	mat.albedo_color=color
	mat.roughness=.78
	mesh.material_override=mat
	parent.add_child(mesh)
	return mesh

func caption(parent: Node3D, text: String, height: float) -> Label3D:
	var label:=Label3D.new()
	label.text=text
	label.position.y=height
	label.font_size=25
	label.pixel_size=.007
	label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	parent.add_child(label)
	return label

func _process(_delta: float) -> void:
	if cabinet==null: return
	var player:=get_tree().get_first_node_in_group("player") as Node3D
	if player==null: return
	cabinet_label.visible=player.global_position.distance_to(cabinet.global_position)<3.0
	operative_label.visible=player.global_position.distance_to(operative.global_position)<3.4
	if archivist!=null:
		archivist_label.visible=player.global_position.distance_to(archivist.global_position)<3.4
	var network: Dictionary=WorldApi.snapshot.get("network_conflict",{})
	for person in network.get("visible_personnel",[]):
		if str(person.relay)==relay:
			if str(person.get("slot","LINES"))=="RECORDS":
				if archivist_label!=null: archivist_label.text=str(person.name)+"\n"+str(person.role)+" · E"
			else:
				operative_label.text=str(person.name)+"\n"+str(person.role)+" · E"
	var danger:=false
	for op in network.get("pending",[]):
		if str(op.relay)==relay: danger=true
	(status_lamp.material_override as StandardMaterial3D).albedo_color=Color("c27569") if danger else Color("95b399")
