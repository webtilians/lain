extends SceneTree
## The zone chat box keeps its size however long the conversation gets: the log
## scrolls (to the newest line on its own, back with the wheel or the right stick)
## and the box to write in never leaves the screen. Never calls the server.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func frames(count: int = 3) -> void:
	for i in range(count):
		await process_frame

func chat(presence: Node, first: int, count: int) -> void:
	var lines := []
	for n in range(first, first + count):
		lines.append({"id": str(n), "who": "x", "name": "Haruto" if n % 2 else "Mio",
			"text": "Mensaje %d de una conversación larga que ocupa más de una línea en la caja del chat." % n})
	presence._request_scene = current_scene.get_instance_id()
	presence._received(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(),
		JSON.stringify({"players": [], "chat": lines, "accepted": true}).to_utf8_buffer())

func run() -> void:
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	var server := root.get_node("ServerConnection")
	server.session_path = "user://test_chat_box_session.json"
	server._configured = true
	server._url = "https://mundo.invalid"
	server._token = "t".repeat(43)
	server.awaiting_login = false
	var presence := root.get_node("OnlinePresence")
	presence._ready()  # built now that the game is online
	presence.set_process(false)  # nothing goes to the server in this test
	var scene := Node.new()
	root.add_child(scene)
	current_scene = scene
	presence._layer.visible = true
	await frames()
	var screen := root.get_visible_rect()
	var box: Rect2 = presence._chat_input.get_global_rect()

	chat(presence, 1, 30)
	await frames()
	check(presence._history.size() == 30, "the chat does not keep the conversation: %d" % presence._history.size())
	check(presence._chat_input.get_global_rect() == box and screen.encloses(box),
		"the box to write in moves or leaves the screen: %s in %s" % [presence._chat_input.get_global_rect(), screen])
	var bar: VScrollBar = presence._scroll.get_v_scroll_bar()
	check(bar.max_value > presence._scroll.size.y, "a long conversation does not scroll")
	check(presence._scroll.scroll_vertical > 0
		and presence._scroll.scroll_vertical + presence._scroll.size.y >= bar.max_value - 2,
		"the chat does not show the newest line")

	# Reading back up, then a new line: down to the newest again.
	presence._scroll.scroll_vertical = 0
	chat(presence, 31, 1)
	await frames()
	check(presence._scroll.scroll_vertical + presence._scroll.size.y >= bar.max_value - 2, "a new line does not scroll down")
	check(presence._chat_input.get_global_rect() == box, "a new line moves the box to write in")
	check(presence._scroll in root.get_node("Gamepad").scroll_targets, "the right stick does not scroll the chat")

	server._token = ""
	scene.queue_free()
	current_scene = null
	await frames()
	print("CHAT_BOX_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
