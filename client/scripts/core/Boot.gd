extends Control

@onready var status: Label = $Center/Status

func _ready() -> void:
	WorldApi.api_error.connect(_on_api_error)
	WorldApi.snapshot_updated.connect(_on_snapshot_updated)
	status.text = "CONNECTING TO THE WIRED..."
	WorldApi.request_state()

func _on_snapshot_updated(_snapshot: Dictionary) -> void:
	status.text = "WORLD CORE SYNCHRONIZED"

func _on_api_error(message: String) -> void:
	status.text = "CONNECTION FAILED\n\n" + message
