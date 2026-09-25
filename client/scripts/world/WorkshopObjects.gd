extends Node3D
## Physical café workstation using the city's CRT furniture and materials.
var terminal: Node3D
var caption: Label3D
func _ready() -> void:
	var shop := get_parent()
	shop._solid("WorkshopDesk", Vector3(3.1,.55,-2.1), Vector3(1.9,1.1,1.0), Color("625c50"))
	shop._crt(Vector3(3.1,1.63,-2.25))
	shop._detail("WorkshopKeyboard", Vector3(3.1,1.14,-1.76), Vector3(.7,.06,.21), Color("a3a18d"))
	terminal = Node3D.new()
	terminal.name = "CafeTerminal"
	terminal.position = Vector3(3.1,1.2,-1.8)
	terminal.set_script(load("res://scripts/world/WorkshopInteractable.gd"))
	add_child(terminal)
	caption = Label3D.new()
	caption.text = "Terminal del café / técnico · E"
	caption.position.y = .8
	caption.font_size = 25
	caption.pixel_size = .007
	caption.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	terminal.add_child(caption)
func _process(_delta: float) -> void:
	var player := get_tree().get_first_node_in_group("player") as Node3D
	caption.visible = player != null and player.global_position.distance_to(terminal.global_position) < 2.3
