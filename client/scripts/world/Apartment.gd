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

func _ready() -> void:
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
	var origin: Dictionary = snapshot.get("prologue", {})
	var offline: bool = (
		bool(origin.get("enabled", false))
		and str(origin.get("stage", "")) != "CONNECTED"
	)
	connection_label.text = (
		"LAIN  /  SIN CONEXIÓN A LA WIRED"
		if offline else "LAIN  /  CONECTADO"
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
		"APARTAMENTO" if location == "APARTMENT" else location
	)

	minute_label.text = (
		"TIEMPO  %04d" % int(
			snapshot.get(
				"minute",
				0
			)
		)
	)

	energy_label.text = (
		"ENERGÍA  %.2f" % float(
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

func _on_api_error(
	message: String
) -> void:
	connection_label.text = (
		"SIN CONEXIÓN"
	)

	knowledge_label.text = message
