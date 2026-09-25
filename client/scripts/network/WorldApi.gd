extends Node

signal snapshot_updated(snapshot: Dictionary)
signal api_error(message: String)
signal action_denied(reason: String)
signal action_resolved(
	result: Dictionary,
	updated_snapshot: Dictionary
)

const BASE_URL := "http://127.0.0.1:8000"
const STATE_POLL_SECONDS := 1.5

var snapshot: Dictionary = {}
var _poll_elapsed := 0.0
var _state_polling := false
var _ignore_next_state_response := false
var _external_mutation := false

var _state_request: HTTPRequest
var _mutation_request: HTTPRequest

var _mutation_kind := ""

func _ready() -> void:
	_state_request = HTTPRequest.new()
	add_child(_state_request)
	_state_request.request_completed.connect(
		_on_state_request_completed
	)

	_mutation_request = HTTPRequest.new()
	add_child(_mutation_request)
	_mutation_request.request_completed.connect(
		_on_mutation_request_completed
	)

# =====================================================
# STATE
# =====================================================

func _process(delta: float) -> void:
	# The SERVER advances the world. This loop only reads its latest state;
	# it never calls player/step and does not spend the player's energy.
	_poll_elapsed += delta
	if _poll_elapsed < STATE_POLL_SECONDS:
		return
	_poll_elapsed = 0.0
	if _external_mutation:
		return
	if _mutation_request == null:
		return
	if _mutation_request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		return
	request_state(true)


func request_state(silent: bool = false) -> void:
	if _external_mutation:
		return
	if (
		_state_request.get_http_client_status()
		!= HTTPClient.STATUS_DISCONNECTED
	):
		print("WORLD API // STATE REQUEST ALREADY ACTIVE")
		return

	_state_polling = silent
	if not silent:
		print("WORLD API // GET STATE")

	# The server pauses autonomous ticks only for a live, visible NPC
	# conversation. No text, identity or memories are sent in this header.
	var request_headers := PackedStringArray()
	if EventDialog.visible and not EventDialog.current_owner_id.is_empty() and EventDialog.current_owner_id!="NETWORK_CONFLICT":
		request_headers.append("X-Lain-Dialog-Active: 1")

	var error := _state_request.request(
		BASE_URL
		+ "/api/v1/player/state",
		request_headers
	)

	if error != OK:
		api_error.emit(
			"Could not request player state: %s" % error
		)

# =====================================================
# PLAYER ACTION
# =====================================================

func step(
	action: String,
	target: String
) -> void:
	print("WORLD API // STEP ", action, " -> ", target)

	if (
		_mutation_request.get_http_client_status()
		!= HTTPClient.STATUS_DISCONNECTED
	):
		print("WORLD API // BUSY")
		api_error.emit(
			"World API action request already active"
		)
		return

	_mutation_kind = "step"
	if _state_request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		_ignore_next_state_response = true

	var payload := {
		"action": action,
		"target": target,
	}

	var body := JSON.stringify(payload)
	var headers := [
		"Content-Type: application/json"
	]

	var error := _mutation_request.request(
		BASE_URL + "/api/v1/player/step",
		headers,
		HTTPClient.METHOD_POST,
		body
	)

	if error != OK:
		_mutation_kind = ""
		api_error.emit(
			"Could not send action: %s" % error
		)

# =====================================================
# MESSAGE ACK
# =====================================================

func acknowledge_message(
	message_id: String
) -> void:
	print("WORLD API // ACK MESSAGE ", message_id)

	if (
		_mutation_request.get_http_client_status()
		!= HTTPClient.STATUS_DISCONNECTED
	):
		api_error.emit(
			"World API action request already active"
		)
		return

	_mutation_kind = "ack_message"
	if _state_request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		_ignore_next_state_response = true

	var error := _mutation_request.request(
		BASE_URL
		+ "/api/v1/player/messages/"
		+ message_id
		+ "/ack",
		[],
		HTTPClient.METHOD_POST
	)

	if error != OK:
		_mutation_kind = ""
		api_error.emit(
			"Could not acknowledge message: %s" % error
		)

# =====================================================
# STATE RESPONSE
# =====================================================

func begin_external_mutation() -> void:
	_external_mutation=true
	if _state_request.get_http_client_status()!=HTTPClient.STATUS_DISCONNECTED:
		_ignore_next_state_response=true

func end_external_mutation() -> void:
	_external_mutation=false

func _on_state_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	var text := body.get_string_from_utf8()
	if not _state_polling:
		print("WORLD API // STATE RESPONSE ", response_code)
	_state_polling = false
	if _ignore_next_state_response:
		_ignore_next_state_response = false
		return

	if result != HTTPRequest.RESULT_SUCCESS:
		api_error.emit(
			"State network error: %s" % result
		)
		return

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

	var prior_minute := int(snapshot.get("minute", -1))
	var next_minute := int(parsed.get("minute", -1))
	if next_minute < prior_minute:
		return
	var changed: bool = parsed != snapshot
	snapshot = parsed
	if changed:
		if next_minute != prior_minute:
			_debug_snapshot(snapshot)
		snapshot_updated.emit(snapshot)

# =====================================================
# MUTATION RESPONSE
# =====================================================

func _on_mutation_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	var kind := _mutation_kind
	_mutation_kind = ""

	var text := body.get_string_from_utf8()
	print("WORLD API // ", kind, " RESPONSE ", response_code)

	if result != HTTPRequest.RESULT_SUCCESS:
		api_error.emit(
			"Action network error: %s" % result
		)
		return

	var parsed = JSON.parse_string(text)

	if response_code < 200 or response_code >= 300:
		var message := "Server returned %s: %s" % [response_code, text]
		print("WORLD API // ERROR ", message)
		api_error.emit(message)
		return

	if typeof(parsed) != TYPE_DICTIONARY:
		api_error.emit(
			"Invalid response from World Core"
		)
		return

	var action_result: Dictionary = parsed.get(
		"action_result",
		{}
	)

	if kind == "step" and action_result.is_empty():
		api_error.emit(
			"Missing action_result from World Core"
		)
		return

	if not action_result.get("accepted", true):
		var reason: String = action_result.get("reason", "UNKNOWN")
		print("WORLD API // ACTION DENIED (", reason, ")")
		action_denied.emit(reason)

	snapshot = parsed.get("state", {})
	_debug_snapshot(snapshot)
	snapshot_updated.emit(snapshot)

	if kind == "step":
		action_resolved.emit(
			action_result,
		snapshot
	)

# =====================================================
# DEBUG
# =====================================================

func _debug_snapshot(
	next_snapshot: Dictionary
) -> void:
	var player: Dictionary = next_snapshot.get(
		"player",
		{}
	)

	print(
		"WORLD API // LOCATION = ",
		player.get("location", "UNKNOWN")
	)

	print(
		"WORLD API // ENERGY = ",
		player.get("energy", "UNKNOWN")
	)

	var wired: Dictionary = next_snapshot.get(
		"wired",
		{}
	)

	var signals: Array = wired.get(
		"signals",
		[]
	)

	for signal_data in signals:
		print(
			"WORLD API // SIGNAL ",
			signal_data.get("node_id", "UNKNOWN"),
			" CONFIDENCE=",
			signal_data.get("confidence", 0),
			" VERIFIED=",
			signal_data.get("verified", false)
		)
