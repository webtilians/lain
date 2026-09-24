extends Node

const LOCATION_SCENES := {
	"IZAKAYA": "res://scenes/city09/Izakaya.tscn",
	"GROCERY": "res://scenes/city09/Grocery.tscn",
	"VIDEO_CLUB": "res://scenes/city09/VideoClub.tscn",
	"BOOKSHOP": "res://scenes/city09/Bookshop.tscn",
	"ARCADE": "res://scenes/city09/Arcade.tscn",
	"CAFE": "res://scenes/city09/Cafe.tscn",
	"APARTMENT": "res://scenes/apartment/ApartmentIso.tscn",
	"APARTMENT_DISTRICT": "res://scenes/apartment_district/ApartmentDistrict.tscn",
	"STATION": "res://scenes/station/Station.tscn",
	"SCHOOL": "res://scenes/prologue/School.tscn",
	"SCHOOL_LAB": "res://scenes/prologue/ComputerLab.tscn",
	"NIGHTCLUB": "res://scenes/prologue/Nightclub.tscn",
}

var current_location := ""
var entry_from_location := ""
var _pending_scene_path := ""

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

	if scene_path == _pending_scene_path:
		return
	# Remember which door brought the player into the expanded district.
	# Semantic location remains authoritative; this affects visuals only.
	if current_location != location:
		entry_from_location = current_location
	current_location = location
	_pending_scene_path = scene_path
	call_deferred("_change_scene", scene_path)

func _change_scene(scene_path: String) -> void:
	get_tree().change_scene_to_file(scene_path)
	_pending_scene_path = ""
