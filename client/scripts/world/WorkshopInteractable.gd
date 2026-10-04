extends Node3D
func _ready() -> void:
	add_to_group("interactable")
func interact() -> void:
	if Workshop.active() and not EventDialog.visible and not Workshop.is_open():
		Workshop.open_cafe()
