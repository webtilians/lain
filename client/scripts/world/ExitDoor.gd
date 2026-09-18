extends StaticBody3D

@export var target_location := (
	"APARTMENT_DISTRICT"
)

var busy := false

func interact() -> void:
	if busy:
		return

	busy = true

	WorldApi.snapshot_updated.connect(
		_on_world_updated,
		CONNECT_ONE_SHOT
	)

	WorldApi.api_error.connect(
		_on_api_error,
		CONNECT_ONE_SHOT
	)

	WorldApi.step(
		"MOVE",
		target_location
	)

func _on_world_updated(
	_snapshot: Dictionary
) -> void:
	busy = false

func _on_api_error(
	_message: String
) -> void:
	busy = false
