extends Node

signal snapshot_updated(snapshot: Dictionary)
signal api_error(message: String)

const BASE_URL := "http://127.0.0.1:8000"

var snapshot: Dictionary = {}

var _request: HTTPRequest
var _pending_kind := ""

func _ready() -> void:
	_request = HTTPRequest.new()
	add_child(_request)
	_request.request_completed.connect(
		_on_request_completed
	)

func request_state() -> void:
	if _request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		return

	_pending_kind = "state"

	var error := _request.request(
		BASE_URL + "/api/v1/player/state"
	)

	if error != OK:
		api_error.emit(
			"Could not request player state: %s" % error
		)

func step(
	action: String,
	target: String
) -> void:
	if _request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		return

	_pending_kind = "step"

	var payload := {
		"action": action,
		"target": target,
	}

	var body := JSON.stringify(payload)
	var headers := [
		"Content-Type: application/json"
	]

	var error := _request.request(
		BASE_URL + "/api/v1/player/step",
		headers,
		HTTPClient.METHOD_POST,
		body
	)

	if error != OK:
		api_error.emit(
			"Could not send action: %s" % error
		)

func acknowledge_message(
	message_id: String
) -> void:
	if (
		_request.get_http_client_status()
		!= HTTPClient.STATUS_DISCONNECTED
	):
		return

	_pending_kind = "ack_message"

	var error := _request.request(
		BASE_URL
		+ "/api/v1/player/messages/"
		+ message_id
		+ "/ack",
		[],
		HTTPClient.METHOD_POST
	)

	if error != OK:
		api_error.emit(
			"Could not acknowledge message: %s" % error
		)

func _on_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		api_error.emit(
			"Network error: %s" % result
		)
		return

	var text := body.get_string_from_utf8()
	var parsed = JSON.parse_string(text)

	if response_code < 200 or response_code >= 300:
		api_error.emit(
			"Server returned %s: %s" % [response_code, text]
		)
		return

	if typeof(parsed) != TYPE_DICTIONARY:
		api_error.emit(
			"Invalid response from World Core"
		)
		return

	if (
		_pending_kind == "step"
		or
		_pending_kind == "ack_message"
	):
		snapshot = parsed.get("state", {})
	else:
		snapshot = parsed

	snapshot_updated.emit(snapshot)
	_pending_kind = ""
