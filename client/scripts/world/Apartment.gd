extends Node3D

@onready var connection_label: Label = (
	$HUD/Info/Panel/VBox/Connection
)

@onready var location_label: Label = (
	$HUD/Info/Panel/VBox/Location
)

@onready var minute_label: Label = (
	$HUD/Info/Panel/VBox/Minute
)

@onready var energy_label: Label = (
	$HUD/Info/Panel/VBox/Energy
)

@onready var knowledge_label: Label = (
	$HUD/Info/Panel/VBox/Knowledge
)

@onready var transition: ColorRect = (
	$HUD/Transition
)

@onready var transition_label: Label = (
	$HUD/Transition/Label
)

func _ready() -> void:
	transition.visible = false

	WorldApi.snapshot_updated.connect(
		_on_snapshot_updated
	)

	WorldApi.api_error.connect(
		_on_api_error
	)

	if WorldApi.snapshot.is_empty():
		WorldApi.request_state()
	else:
		_on_snapshot_updated(
			WorldApi.snapshot
		)

func _on_snapshot_updated(
	snapshot: Dictionary
) -> void:
	connection_label.text = (
		"WORLD CORE // CONNECTED"
	)

	var player: Dictionary = snapshot.get(
		"player",
		{}
	)

	var location := str(
		player.get(
			"location",
			"UNKNOWN"
		)
	)

	location_label.text = (
		"LOCATION // %s" % location
	)

	minute_label.text = (
		"WORLD TIME // %04d" % int(
			snapshot.get(
				"minute",
				0
			)
		)
	)

	energy_label.text = (
		"ENERGY // %.2f" % float(
			player.get(
				"energy",
				0.0
			)
		)
	)

	var nodes: Array = snapshot.get(
		"known_nodes",
		[]
	)

	knowledge_label.text = (
		"KNOWN NODES // %d" % nodes.size()
	)

	if location != "APARTMENT":
		transition.visible = true
		transition_label.text = (
			"%s\n\nWORLD CORE SYNCHRONIZED" % location
		)
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _on_api_error(
	message: String
) -> void:
	connection_label.text = (
		"WORLD CORE // OFFLINE"
	)

	knowledge_label.text = message
