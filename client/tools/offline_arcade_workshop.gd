extends "res://scripts/ui/Workshop.gd"
## Test-only network boundary: never connects to the user's game server.
var dispatch_count := 0
func _dispatch() -> void:
	retry_button.hide()
	dispatch_count += 1
	busy = true
