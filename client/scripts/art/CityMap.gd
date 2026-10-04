extends Control
## A plan of the physical streets. Shows public places, never NPC/private knowledge.
const LAYOUT = preload("res://scripts/world/CityLayout.gd")
var player: CharacterBody3D
var footprints: Array[AABB] = []
var panel := StyleBoxFlat.new()

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.bg_color = Color(0.075,0.092,0.12,0.90)
	panel.border_color = Color(0.52,0.56,0.56,0.35)
	panel.set_border_width_all(1)
	panel.set_corner_radius_all(3)

func point(world: Vector3) -> Vector2:
	return Vector2(14,29) + Vector2((world.x+46)/92.0*144,(world.z+114)/132.0*180)

func _process(_delta: float) -> void:
	queue_redraw()

func _draw() -> void:
	draw_style_box(panel,Rect2(Vector2.ZERO,size))
	var font := ThemeDB.fallback_font
	draw_string(font,Vector2(14,19),"DISTRITO  /  03",HORIZONTAL_ALIGNMENT_LEFT,-1,11,Color("c3c9c3"))
	for footprint in footprints:
		var a := point(footprint.position)
		var b := point(footprint.end)
		draw_rect(Rect2(a,b-a),Color("4c555f"))
	for x in LAYOUT.LONG_STREETS:
		draw_line(point(Vector3(x,0,12)),point(Vector3(x,0,-108)),Color("85908c"),2)
	for z in LAYOUT.CROSS_STREETS:
		draw_line(point(Vector3(-43,0,z)),point(Vector3(43,0,z)),Color("85908c"),2)
	for target in LAYOUT.DOORS:
		var at := point(LAYOUT.DOORS[target])
		draw_circle(at,3,Color("c9b993"))
		draw_string(font,at+Vector2(5,-3),{"APARTMENT":"A","SCHOOL":"C","NIGHTCLUB":"D","STATION":"E","BOOKSHOP":"L","GROCERY":"T","VIDEO_CLUB":"V","CAFE":"K","IZAKAYA":"B","ARCADE":"R"}.get(target,""),HORIZONTAL_ALIGNMENT_LEFT,-1,10,Color("e2dccb"))
	if is_instance_valid(player):
		draw_circle(point(player.global_position),4,Color("d9eded"))
		draw_arc(point(player.global_position),7,0,TAU,24,Color("93bbbb"),1,true)
	draw_string(font,Vector2(14,229),"A Casa   C Colegio",HORIZONTAL_ALIGNMENT_LEFT,-1,10,Color("b4b9b3"))
	draw_string(font,Vector2(14,244),"D Disco E Estación · Locales: •",HORIZONTAL_ALIGNMENT_LEFT,-1,10,Color("b4b9b3"))
