extends StaticBody3D

@export var npc_id := "PROFESSOR"

var waiting := false


func _ready() -> void:
	add_to_group("interactable")
	PrologueApi.dialogue_received.connect(_on_dialogue)
	PrologueApi.request_error.connect(_on_error)


func interact() -> void:
	if waiting or EventDialog.visible:
		return
	waiting = true
	EventDialog.show_event(
		"PROFESOR" if npc_id == "PROFESSOR" else "RYOKO",
		"Esperando respuesta..."
	)
	PrologueApi.talk(npc_id)


func _on_dialogue(actor_id: String, result: Dictionary) -> void:
	if not waiting or actor_id != npc_id:
		return
	waiting = false
	EventDialog.show_event(
		str(result.get("speaker", "DESCONOCIDO")),
		str(result.get("text", "No responde."))
	)


func _on_error(message: String) -> void:
	if not waiting:
		return
	waiting = false
	EventDialog.show_event("NO HAY RESPUESTA", message)
