extends Node3D
## Presentation-only entry points on returning to the expanded neighborhood.
## The server still owns the player's semantic location and MOVE validation.

const ENTRY_POSITIONS := {
	"APARTMENT": Vector3(0.0, 0.9, 5.5),
	"SCHOOL": Vector3(-8.75, 0.9, -20.0),
	"NIGHTCLUB": Vector3(8.75, 0.9, -53.0),
	"STATION": Vector3(0.0, 0.9, -63.7),
}


func _ready() -> void:
	var origin := SceneRouter.entry_from_location
	if not ENTRY_POSITIONS.has(origin):
		return
	var player := get_node_or_null("Player") as CharacterBody3D
	if player != null:
		player.position = ENTRY_POSITIONS[origin]
	SceneRouter.entry_from_location = ""
