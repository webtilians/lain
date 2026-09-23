extends Control

@onready var status: Label = $Center/Status

func _ready() -> void:
	WorldApi.api_error.connect(_on_api_error)
	WorldApi.snapshot_updated.connect(_on_snapshot_updated)
	status.text = "INICIANDO SISTEMA LOCAL..."
	WorldApi.request_state()

func _on_snapshot_updated(snapshot: Dictionary) -> void:
	var origin: Dictionary = snapshot.get("prologue", {})
	if bool(origin.get("enabled", false)) and str(origin.get("stage", "")) != "CONNECTED":
		status.text = "SISTEMA LOCAL DISPONIBLE // SIN CONEXIÓN A LA WIRED"
	else:
		status.text = "WORLD CORE SYNCHRONIZED"

func _on_api_error(message: String) -> void:
	status.text = "CONNECTION FAILED\n\n" + message
