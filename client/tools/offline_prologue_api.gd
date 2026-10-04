extends Node
## Preview/test guard: no network requests can leave the offline scene.
signal dialogue_received(actor_id: String, result: Dictionary)
signal terminal_received(result: Dictionary)
signal request_error(message: String)
func talk(_actor_id: String, _choice: String = "INTRO") -> void:
	push_error("Offline preview attempted dialogue")
func terminal_command(_line: String) -> void:
	push_error("Offline preview attempted terminal command")
