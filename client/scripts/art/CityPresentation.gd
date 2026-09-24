extends Node3D
const LAYOUT = preload("res://scripts/world/CityLayout.gd")
var player: CharacterBody3D
var location_label: Label
var hint: Label

func _ready() -> void:
	var district := get_parent()
	player = district.get_node("Player")
	location_label = district.get_node("HUD/Location")
	hint = district.get_node("HUD/Hint")
	var grade := ShaderMaterial.new()
	grade.shader = load("res://shaders/city_grade.gdshader")
	district.get_node("RetroOverlay/CRT").material = grade
	for label in [location_label,hint]:
		label.add_theme_color_override("font_color",Color("d2d3ca"))
		label.add_theme_color_override("font_shadow_color",Color("191c28"))
		label.add_theme_constant_override("shadow_offset_x",1)
		label.add_theme_constant_override("shadow_offset_y",2)
	var caption := Label.new()
	caption.text = "L A I N   /   DISTRITO 03"
	caption.position = Vector2(29,12)
	caption.add_theme_font_size_override("font_size",10)
	caption.modulate = Color("bac3bd")
	district.get_node("HUD").add_child(caption)
	var map := Control.new()
	map.set_script(load("res://scripts/art/CityMap.gd"))
	map.name = "NeighborhoodMap"
	map.player = player
	for building in district.get_node("CityArt").get_children():
		if building.get_script() == preload("res://scripts/art/CityCutaway.gd") and not str(building.name).begins_with("Skyline"):
			map.footprints.append(building.bounds)
	district.get_node("HUD").add_child(map)
	map.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	map.offset_left = -192
	map.offset_top = 24
	map.offset_right = -20
	map.offset_bottom = 282

func _process(_delta: float) -> void:
	if not is_instance_valid(player):
		return
	var p := player.position
	if p.z < -98:
		location_label.text = "Estación norte"
	elif p.z < -72:
		location_label.text = "Calle de los talleres"
	elif p.z < -45:
		location_label.text = "Pasaje Azul"
	elif p.z < -12:
		location_label.text = "Colegio municipal" if p.x < 0 else "Plaza del alcanfor"
	else:
		location_label.text = "Residencial"
	var nearby := ""
	for target in LAYOUT.DOORS:
		if player.position.distance_to(LAYOUT.DOORS[target]) < player.interaction_distance:
			nearby = "Entrar: " + LAYOUT.TITLES.get(target, target)
	hint.text = "E  " + nearby + "     ·     J  Diario" if not nearby.is_empty() else "WASD  Caminar     E  Interactuar     J  Diario"
