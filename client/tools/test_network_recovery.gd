extends SceneTree
## A real TCP peer accepts requests but never sends an HTTP response.
var failed := false
var stalled_server := TCPServer.new()
var held_peers: Array[StreamPeerTCP] = []
var prologue_errors := 0

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error("NETWORK_RECOVERY // " + message)

func wait_for_request(request: HTTPRequest) -> void:
	var deadline := Time.get_ticks_msec() + 2000
	while Time.get_ticks_msec() < deadline:
		if stalled_server.is_connection_available():
			held_peers.append(stalled_server.take_connection())
		await create_timer(0.02).timeout
		if request.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED:
			return
	check(false, "Request remained active after a stalled connection")
	request.cancel_request()

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_process(false)
	api._state_request.cancel_request()
	root.get_node("OnlinePresence").set_process(false)
	check(stalled_server.listen(0, "127.0.0.1") == OK, "Cannot start isolated TCP fixture")
	root.get_node("ServerConnection")._url = "http://127.0.0.1:%s" % stalled_server.get_local_port()
	var actor: Node3D = load("res://scripts/world/ActorInteractable.gd").new()
	actor.actor_id = "K"
	actor.actor_name = "K"
	root.add_child(actor)
	# Keep the test quick while requiring the production request to have a bound.
	check(actor.chat_request.timeout > 0.0, "NPC requests have no timeout")
	if actor.chat_request.timeout > 0.0:
		actor.chat_request.timeout = 0.15
	actor._send_chat_request("start", {})
	await wait_for_request(actor.chat_request)
	check(not actor.chat_busy, "NPC remains busy after timeout")
	# Closing while a request is in flight must also allow later contact.
	actor._send_chat_request("start", {})
	actor._on_dialog_closed(str(actor.get_instance_id()))
	await wait_for_request(actor.chat_request)
	check(not actor.chat_busy and not actor.pending_pause, "Closed dialogue remains stuck")
	root.get_node("EventDialog").close_event()
	var prologue := root.get_node("PrologueApi")
	check(prologue._request.timeout > 0.0, "Prologue requests have no timeout")
	if prologue._request.timeout > 0.0:
		prologue._request.timeout = 0.15
	prologue.request_error.connect(func(_message: String): prologue_errors += 1)
	for attempt in range(2):
		prologue.talk("PROFESSOR")
		await wait_for_request(prologue._request)
		check(prologue._kind.is_empty(), "Prologue cannot be retried")
	check(prologue_errors == 2, "Missing error feedback after stalled prologue requests")
	for peer in held_peers:
		peer.disconnect_from_host()
	stalled_server.stop()
	actor.queue_free()
	await process_frame
	if not failed:
		print("NETWORK_RECOVERY_OK npc=retryable prologue=retryable")
	quit(1 if failed else 0)
