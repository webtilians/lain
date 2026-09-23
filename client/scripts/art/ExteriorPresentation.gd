extends Node3D
## Presentation only: no world state, interactions or geometry are created here.
func _ready() -> void:
	var room := get_parent()
	var crosshair := room.get_node_or_null("HUD/Crosshair")
	if crosshair:
		crosshair.hide()
	for label in room.get_node("HUD").get_children():
		if label is Label:
			label.add_theme_color_override("font_color", Color("c3c1bb"))
			label.add_theme_color_override("font_shadow_color", Color("181b25"))
			label.add_theme_constant_override("shadow_offset_x", 1)
			label.add_theme_constant_override("shadow_offset_y", 1)
	var crt: ColorRect = room.get_node("RetroOverlay/CRT")
	crt.material = crt.material.duplicate()
	crt.material.set_shader_parameter("scanline_strength", 0.025)
	crt.material.set_shader_parameter("noise_strength", 0.007)
	crt.material.set_shader_parameter("color_levels", 128.0)
