extends Node3D
## Applies HUD styling only. All geometry is supplied by saved model scenes.
var room: Node3D

func _ready() -> void:
	room = get_parent()
	_interface()

func _interface() -> void:
	room.get_node("HUD/Crosshair").hide()
	var info: MarginContainer = room.get_node("HUD/Info")
	info.offset_right = 275
	info.offset_bottom = 130
	var panel: PanelContainer = room.get_node("HUD/Info/Panel")
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.06, 0.07, 0.09, 0.55)
	style.border_color = Color("74707c")
	style.border_width_left = 2
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 8
	style.content_margin_bottom = 8
	panel.add_theme_stylebox_override("panel", style)
	panel.add_theme_font_size_override("font_size", 13)
	room.get_node("HUD/Info/Panel/VBox/Knowledge").hide()
	var crt: ColorRect = room.get_node("RetroOverlay/CRT")
	crt.material = crt.material.duplicate()
	crt.material.set_shader_parameter("scanline_strength", 0.025)
	crt.material.set_shader_parameter("noise_strength", 0.007)
	crt.material.set_shader_parameter("color_levels", 96.0)
	crt.material.set_shader_parameter("saturation", 0.70)
	crt.material.set_shader_parameter("contrast", 1.10)
	crt.material.set_shader_parameter("exposure", 0.92)
	crt.material.set_shader_parameter("vignette_strength", 0.20)
	crt.material.set_shader_parameter("edge_strength", 0.27)
	crt.material.set_shader_parameter("paper_grain", 0.016)
