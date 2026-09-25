extends Node3D
var relay := ""
var personnel := false
func _ready() -> void:
	add_to_group("interactable")
func interact() -> void:
	if NetworkConflict.active():
		NetworkConflict.interact(relay,personnel)
