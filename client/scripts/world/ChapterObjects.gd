extends Node3D
## Physical, inspectable surfaces. No quest beacons or autonomous progression.
var location := ""
var anchors: Array[Node3D] = []
var captions: Array[Label3D] = []
var envelope: MeshInstance3D
var professor_pose: Node3D
var ryoko_pose: Node3D

func _ready() -> void:
	if location=="SCHOOL":
		paper("CLOSURE_SHEET","Parte de cierre",Vector3(-6.78,1.8,.75),Vector3(.025,.52,.38),Color("d2c8a5"))
		paper("SCHOOL_CLOCK","Reloj del pabellón",Vector3(0,2.6,-8.06),Vector3(.62,.62,.05),Color("c2c5b8"))
		var face := get_node("SCHOOL_CLOCK")
		var hour := detail(face,Vector3(-.074,.052,.045),Vector3(.025,.18,.025),Color("373c42"))
		hour.rotation.z=deg_to_rad(55)
		var minute := detail(face,Vector3(.104,.06,.047),Vector3(.02,.24,.025),Color("373c42"))
		minute.rotation.z=deg_to_rad(-60)
	elif location=="SCHOOL_LAB":
		# The existing third CRT is already reachable and has its own collision.
		anchor("SCHOOL_PC","Archivo local",Vector3(-4.15,1.2,-.92))
		envelope=detail(self,Vector3(-3.6,1.08,-.92),Vector3(.45,.025,.32),Color("d0bc91"))
		envelope.name="CaseEnvelope"
		professor_pose=get_parent().get_node_or_null("PROFESSOR")
	elif location=="NIGHTCLUB":
		ryoko_pose=get_parent().get_node_or_null("RYOKO")

func anchor(id: String, title: String, position_value: Vector3) -> Node3D:
	var item := Node3D.new()
	item.name=id
	item.set_script(load("res://scripts/world/ChapterInteractable.gd"))
	item.set("target",id)
	item.position=position_value
	add_child(item)
	anchors.append(item)
	var caption := Label3D.new()
	caption.text=title+"  [E]"
	caption.position=Vector3(0,.38,0)
	caption.font_size=24
	caption.pixel_size=.007
	caption.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	caption.modulate=Color("c7d1be")
	item.add_child(caption)
	captions.append(caption)
	return item

func paper(id: String, title: String, at: Vector3, size: Vector3, color: Color) -> void:
	var item := anchor(id,title,at)
	detail(item,Vector3.ZERO,size,color)
	if id=="CLOSURE_SHEET":
		for row in range(5):
			detail(item,Vector3(.018,.15-row*.07,0),Vector3(.012,.012,.25),Color("626a61"))

func detail(parent: Node3D, at: Vector3, size: Vector3, color: Color) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size=size
	mesh.mesh=box
	mesh.position=at
	var material := StandardMaterial3D.new()
	material.albedo_color=color
	material.roughness=.9
	mesh.material_override=material
	parent.add_child(mesh)
	return mesh

func _process(_delta: float) -> void:
	var player := get_tree().get_first_node_in_group("player") as Node3D
	for i in range(anchors.size()):
		captions[i].visible=player!=null and player.global_position.distance_to(anchors[i].global_position)<2.3
	var decision: String = str(WorldApi.snapshot.get("chapter_one",{}).get("decision",""))
	if envelope!=null:
		envelope.visible=decision=="DISCLOSE"
	if professor_pose!=null:
		professor_pose.rotation.y=.7 if decision=="SEAL" else 0.0
	if ryoko_pose!=null:
		ryoko_pose.rotation.y=-.7 if decision=="DISCLOSE" else 0.0
