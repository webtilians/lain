extends Node

const LOCATION_SCENES := {
	"APARTMENT": "res://scenes/apartment/Apartment.tscn",
	"APARTMENT_DISTRICT": "res://scenes/apartment_district/ApartmentDistrict.tscn",
}

var current_location := ""

func _ready() -> void:
	WorldApi.snapshot_updated.connect(_on_snapshot_updated)

func _on_snapshot_updated(snapshot: Dictionary) -> void:
	var player: Dictionary = snapshot.get("player", {})
	var location := str(player.get("location", ""))
	if location.is_empty():
		return

	var scene_path: String = LOCATION_SCENES.get(location, "")
	if scene_path.is_empty():
		print("No physical scene for location: ", location)
		return

	var current_scene := get_tree().current_scene
	if (
		current_scene != null
		and current_scene.scene_file_path == scene_path
	):
		current_location = location
		return

	current_location = location
	call_deferred("_change_scene", scene_path)

func _change_scene(scene_path: String) -> void:
	get_tree().change_scene_to_file(scene_path)
