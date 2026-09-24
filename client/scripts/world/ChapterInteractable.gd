extends Node3D
var target := ""
func _ready() -> void:
	add_to_group("interactable")
func interact() -> void:
	if ChapterOne.active() and not EventDialog.visible:
		ChapterOne.examine(target)
