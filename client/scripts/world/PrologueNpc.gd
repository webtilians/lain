extends StaticBody3D
## A dialogue is an exchange, not a proximity-triggered exposition dump.
## Each choice goes to World Core, which alone may advance the prologue.

@export var npc_id := "PROFESSOR"

var waiting := false
var _owner_id := ""


func _ready() -> void:
	add_to_group("interactable")
	_owner_id = "PROLOGUE_" + npc_id
	PrologueApi.dialogue_received.connect(_on_dialogue)
	PrologueApi.request_error.connect(_on_error)
	EventDialog.choice_selected.connect(_on_choice)


func interact() -> void:
	if waiting or EventDialog.visible:
		return
	if ChapterOne.can_talk(npc_id):
		ChapterOne.open_actor(npc_id,_ask.bind("INTRO"))
		return
	_ask("INTRO")


func _ask(question: String) -> void:
	waiting = true
	EventDialog.show_event(
		"PROFESOR" if npc_id == "PROFESSOR" else "RYOKO",
		"..."
	)
	PrologueApi.talk(npc_id, question)


func _choices() -> Array[Dictionary]:
	if npc_id == "PROFESSOR":
		if Workshop.active():
			return [{"id":"LIFE","text":"Pedir las reglas del Juego de la Vida."},{"id":"ASK_CLASS","text":"¿Qué se enseñaba aquí?"},{"id":"GOODBYE","text":"Dejar al profesor con sus cosas."}]
		return [
			{"id": "ASK_CLASS", "text": "¿Qué se enseñaba aquí?"},
			{"id": "ASK_STUDENT", "text": "¿Alguien sabía entrar en aquella red?"},
			{"id": "ASK_WHERE", "text": "¿Dónde podría encontrar a esa persona?"},
			{"id": "GOODBYE", "text": "Dejar al profesor con sus cosas."},
		]
	return [
		{"id": "ASK_SCHOOL", "text": "¿Estuviste en la escuela?"},
		{"id": "ASK_WIRED", "text": "¿Qué recuerdas de aquella red?"},
		{"id": "ASK_ADDRESS", "text": "¿Conservas algún dato de acceso?"},
		{"id": "ASK_METHOD", "text": "¿Recuerdas cómo se entraba?"},
		{"id": "GOODBYE", "text": "Dejar a Ryoko entre la música."},
	]


func _on_choice(owner_id: String, choice: String) -> void:
	if owner_id != _owner_id or waiting:
		return
	if choice == "LIFE":
		Workshop.open_lesson()
		return
	if choice == "GOODBYE":
		EventDialog.close_event()
		return
	_ask(choice)


func _on_dialogue(actor_id: String, result: Dictionary) -> void:
	if not waiting or actor_id != npc_id:
		return
	waiting = false
	EventDialog.show_choices(
		_owner_id,
		str(result.get("speaker", "DESCONOCIDO")),
		str(result.get("text", "...")),
		_choices(),
	)


func _on_error(message: String) -> void:
	if not waiting:
		return
	waiting = false
	EventDialog.show_choices(
		_owner_id,
		"SIN RESPUESTA",
		"La respuesta se ha perdido. " + message,
		_choices(),
	)
