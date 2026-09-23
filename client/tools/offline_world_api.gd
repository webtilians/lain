extends Node
## Offline substitute for offline visual and navigation checks.
signal snapshot_updated(snapshot: Dictionary)
signal api_error(message: String)
signal action_denied(reason: String)
signal action_resolved(result: Dictionary, updated_snapshot: Dictionary)
var snapshot: Dictionary = {}
func request_state() -> void:
	pass
func step(_action: String, _target: String) -> void:
	push_error("Preview cannot send actions")
func acknowledge_message(_message_id: String) -> void:
	pass
