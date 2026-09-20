extends Node3D

@export var actor_id: String = ""
@export var actor_name: String = ""

var awaiting_result := false
var chat_request: HTTPRequest
var chat_busy := false
var chat_turn_id := 0
var chat_interaction_id := ""
var chat_action := ""
var pending_pause := false

func _ready() -> void:
	add_to_group("interactable")

	EventDialog.choice_selected.connect(
		_on_choice_selected
	)
	EventDialog.dialog_closed.connect(
		_on_dialog_closed
	)

	WorldApi.action_resolved.connect(
		_on_action_resolved
	)

	WorldApi.api_error.connect(
		_on_api_error
	)

	chat_request = HTTPRequest.new()
	add_child(chat_request)
	chat_request.request_completed.connect(
		_on_chat_request_completed
	)

func interact() -> void:
	if awaiting_result or chat_busy or EventDialog.visible:
		return

	if not _actor_is_present():
		return

	EventDialog.show_choices(
		str(get_instance_id()),
		actor_name,
		"Te acercas a " + actor_name + ".\n\n¿Qué quieres hacer?",
		[
			{
				"id": "CONTACT",
				"text": "1. Hablar con " + actor_name,
			},
			{
				"id": "LEAVE",
				"text": "2. Alejarse",
			},
		]
	)

func _on_choice_selected(
	owner_id: String,
	choice_id: String
) -> void:
	if owner_id != str(get_instance_id()):
		return

	if awaiting_result:
		return

	if chat_busy:
		return

	if choice_id in [
		"ASK_IDENTITY",
		"ASK_SIGNAL",
		"TELL_OBSERVED",
	]:
		_request_chat_reply(choice_id)
		return

	if choice_id == "LEAVE":
		EventDialog.close_event()
		return

	if choice_id != "CONTACT":
		return

	if not _actor_is_present():
		EventDialog.show_event(
			"CONTACTO NO DISPONIBLE",
			actor_name + " ya no está aquí."
		)
		return

	awaiting_result = true

	EventDialog.show_event(
		actor_name,
		"Intentando establecer contacto..."
	)

	WorldApi.step(
		"CONTACT",
		actor_id
	)

func _on_action_resolved(
	result: Dictionary,
	_updated_snapshot: Dictionary
) -> void:
	if not awaiting_result:
		return

	if str(result.get("action", "")) != "CONTACT":
		return

	if str(result.get("target", "")) != actor_id:
		return

	awaiting_result = false

	if bool(result.get("accepted", false)):
		EventDialog.show_event(
			actor_name,
			"Esperando respuesta..."
		)
		_request_chat_start()
		return

	var reason := str(
		result.get("reason", "UNKNOWN")
	)
	var explanation := "No se ha podido establecer contacto."

	match reason:
		"ACTOR_NOT_PRESENT":
			explanation = actor_name + " ya no está aquí."
		"NOT_ENOUGH_ENERGY":
			explanation = "No tienes energía suficiente."
		"UNKNOWN_ACTOR":
			explanation = "No se reconoce a este personaje."

	EventDialog.show_event(
		"CONTACTO RECHAZADO",
		explanation + "\n\nREASON // " + reason
	)

func _on_api_error(
	message: String
) -> void:
	if not awaiting_result:
		return

	awaiting_result = false

	EventDialog.show_event(
		"ERROR DE CONEXIÓN",
		message
	)

func _actor_is_present() -> bool:
	var player_data: Dictionary = WorldApi.snapshot.get(
		"player",
		{}
	)

	if str(player_data.get("location", "")).is_empty():
		return false

	for actor_data in WorldApi.snapshot.get(
		"visible_actors",
		[]
	):
		if typeof(actor_data) != TYPE_DICTIONARY:
			continue

		if str(actor_data.get("id", "")) == actor_id:
			return true

	return false

func _request_chat_start() -> void:
	_send_chat_request(
		"start",
		{}
	)

func _request_chat_reply(
	choice_id: String
) -> void:
	if chat_turn_id <= 0:
		return

	_send_chat_request(
		"reply",
		{
			"choice_id": choice_id,
			"after_turn_id": chat_turn_id,
		}
	)

func _send_chat_request(
	action_name: String,
	payload: Dictionary,
	silent: bool = false
) -> void:
	if chat_busy:
		return

	chat_busy = true
	chat_action = action_name
	if not silent:
		EventDialog.show_event(
			actor_name,
			"Esperando respuesta..."
		)

	var url := (
		"http://127.0.0.1:8000"
		+ "/api/v1/player/conversations/"
		+ actor_id
		+ "/"
		+ action_name
	)

	var error := chat_request.request(
		url,
		[
			"Content-Type: application/json"
		],
		HTTPClient.METHOD_POST,
		JSON.stringify(payload)
	)

	if error != OK:
		chat_busy = false
		EventDialog.show_event(
			"CONNECTION ERROR",
			"No se pudo enviar la petición."
		)

func _on_dialog_closed(owner_id: String) -> void:
	if owner_id != str(get_instance_id()):
		return
	if chat_busy:
		pending_pause = true
		return
	_request_chat_pause()


func _request_chat_pause() -> void:
	if chat_interaction_id.is_empty():
		return
	var interaction_to_pause := chat_interaction_id
	chat_turn_id = 0
	chat_interaction_id = ""
	_send_chat_request(
		"pause",
		{"interaction_id": interaction_to_pause},
		true
	)


func _on_chat_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	var completed_action := chat_action
	chat_action = ""
	chat_busy = false

	if completed_action == "pause":
		if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
			push_warning("Could not pause conversation; next CONTACT may resume it")
		return

	if pending_pause and result != HTTPRequest.RESULT_SUCCESS:
		pending_pause = false
		return

	if result != HTTPRequest.RESULT_SUCCESS:
		EventDialog.show_event(
			"CONNECTION ERROR",
			"Se ha interrumpido la conexión."
		)
		return

	var parsed = JSON.parse_string(
		body.get_string_from_utf8()
	)

	if pending_pause and (response_code < 200 or response_code >= 300):
		pending_pause = false
		return

	if response_code < 200 or response_code >= 300:
		var explanation := (
			"El agente no puede continuar la conversación."
		)

		if typeof(parsed) == TYPE_DICTIONARY:
			explanation += (
				"\n\nREASON // "
				+ str(parsed.get("detail", "UNKNOWN"))
			)

		EventDialog.show_event(
			"CONVERSATION INTERRUPTED",
			explanation
		)
		return

	if typeof(parsed) != TYPE_DICTIONARY:
		EventDialog.show_event(
			"CONNECTION ERROR",
			"Respuesta incorrecta del servidor."
		)
		return

	print("DIALOGUE // SOURCE = ", parsed.get("response_source", "UNKNOWN"))
	chat_turn_id = int(
		parsed.get("turn_id", 0)
	)
	chat_interaction_id = str(
		parsed.get("interaction_id", "")
	)
	if pending_pause:
		pending_pause = false
		_request_chat_pause()
		return

	var choices: Array[Dictionary] = []
	for choice in parsed.get("choices", []):
		if typeof(choice) == TYPE_DICTIONARY:
			choices.append(choice)

	EventDialog.show_choices(
		str(get_instance_id()),
		str(parsed.get("actor_name", actor_name)),
		str(parsed.get("line", "")),
		choices
	)
