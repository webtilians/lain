extends Node

signal dialogue_received(actor_id: String, result: Dictionary)
signal terminal_received(result: Dictionary)
signal request_error(message: String)

var _request: HTTPRequest
var _kind := ""
var _actor_id := ""


func _ready() -> void:
	_request = HTTPRequest.new()
	add_child(_request)
	_request.request_completed.connect(_on_completed)


func _send(path: String, data: Dictionary, kind: String, actor_id: String = "") -> void:
	if _request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		request_error.emit("Todavía se está procesando otra petición.")
		return
	_kind = kind
	_actor_id = actor_id
	var err := _request.request(
		"http://127.0.0.1:8000" + path,
		PackedStringArray(["Content-Type: application/json"]),
		HTTPClient.METHOD_POST,
		JSON.stringify(data)
	)
	if err != OK:
		_kind = ""
		request_error.emit("No se pudo conectar con el servidor: %s" % err)


func talk(actor_id: String, choice: String = "INTRO") -> void:
	if actor_id not in ["PROFESSOR", "RYOKO"]:
		request_error.emit("Personaje del prólogo desconocido.")
		return
	_send(
		"/api/v1/prologue/talk/" + actor_id,
		{"choice": choice}, "TALK", actor_id,
	)


func terminal_command(line: String) -> void:
	_send("/api/v1/prologue/terminal", {"command": line}, "TERMINAL")


func _on_completed(result: int, response_code: int,
	_headers: PackedStringArray, body: PackedByteArray) -> void:
	var kind := _kind
	var actor := _actor_id
	_kind = ""
	_actor_id = ""
	if result != HTTPRequest.RESULT_SUCCESS:
		request_error.emit("Se ha perdido la conexión con el servidor.")
		return
	var parsed = JSON.parse_string(body.get_string_from_utf8())
	if response_code < 200 or response_code >= 300:
		var reason := "UNKNOWN"
		if typeof(parsed) == TYPE_DICTIONARY:
			reason = str(parsed.get("detail", "UNKNOWN"))
		request_error.emit(reason)
		return
	if typeof(parsed) != TYPE_DICTIONARY:
		request_error.emit("La respuesta del servidor no es válida.")
		return
	var payload: Dictionary = parsed
	var state: Dictionary = payload.get("state", {})
	if not state.is_empty():
		WorldApi.snapshot = state
		WorldApi.snapshot_updated.emit(state)
	var event: Dictionary = payload.get("result", {})
	if kind == "TALK":
		dialogue_received.emit(actor, event)
	elif kind == "TERMINAL":
		terminal_received.emit(event)
