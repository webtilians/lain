extends StaticBody3D

@export var target_location := (
	"APARTMENT_DISTRICT"
)

var busy := false

func _ready() -> void:
	add_to_group("interactable")

	WorldApi.snapshot_updated.connect(
		_on_world_updated
	)
	WorldApi.api_error.connect(
		_on_api_error
	)
	WorldApi.action_denied.connect(
		_on_action_denied
	)

func interact() -> void:
	if busy:
		return

	print("INTERACT EXIT -> ", target_location)

	busy = true
	WorldApi.step(
		"MOVE",
		target_location
	)

func _on_world_updated(
	_snapshot: Dictionary
) -> void:
	if not busy:
		return

	busy = false

func _on_api_error(
	message: String
) -> void:
	print("EXIT INTERACTION ERROR: ", message)

	busy = false

func _on_action_denied(
	reason: String
) -> void:
	if not busy:
		return

	print("ACTION DENIED // ", reason)

	busy = false
