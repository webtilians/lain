extends SceneTree
## The zone chat box keeps its size however long the conversation gets: the log
## scrolls (to the newest line on its own, back with the wheel or the right stick)
## and the box to write in never leaves the screen. Only the residents the player
## can see are told to the server as listeners, and each new line shows for a while
## over its speaker's head (a resident, another player or the player). Never calls
## the server.
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

	# Who hears: the residents on screen and close by, nearest first (one behind the camera is close, but unseen).
	var world := Node3D.new()
	scene.add_child(world)
	var player := Node3D.new()
	player.add_to_group("player")
	world.add_child(player)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.look_at_from_position(Vector3(0, 1.5, 6), Vector3.ZERO)
	camera.current = true
	var usable := GDScript.new()
	usable.source_code = "extends Node3D
var actor_id := \"\"
func interact() -> void:
	pass
"
	usable.reload()
	var residents := {}
	for entry in [["RESIDENT_NEAR", Vector3(2, 0, 1)], ["RESIDENT_NEXT", Vector3(-2, 0, -3)],
			["RESIDENT_FAR", Vector3(-40, 0, -40)], ["RESIDENT_BEHIND", Vector3(0, 0, 10)]]:
		var resident := Node3D.new()
		resident.set_script(usable)
		resident.actor_id = entry[0]
		resident.add_to_group("interactable")
		resident.set_meta("who", "key-" + entry[0])
		var name_label := Label3D.new()
		name_label.position.y = 2.0
		resident.add_child(name_label)
		world.add_child(resident)
		resident.global_position = entry[1]
		residents[entry[0]] = resident
	await frames()
	check(presence.near_residents() == ["RESIDENT_NEAR", "RESIDENT_NEXT"],
		"the residents told as listeners are not the ones on screen: " + str(presence.near_residents()))
	check(presence.chat_body("hola")["near"] == ["RESIDENT_NEAR", "RESIDENT_NEXT"], "a chat line does not say who hears it")

	# A new line shows over whoever said it, above their name.
	presence._me = "key-me"
	presence._request_scene = current_scene.get_instance_id()
	presence._received(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"players": [], "accepted": true,
		"me": "key-me", "chat": [{"id": "b1", "who": "key-RESIDENT_NEXT", "name": "Daichi", "text": "Aquí, limpiando."},
			{"id": "b2", "who": "key-me", "name": "Mio", "text": "¿qué haces?"}]}).to_utf8_buffer())
	await frames()
	var bubble: Label3D = residents.RESIDENT_NEXT.get_node_or_null("ChatBubble")
	check(bubble != null and bubble.text == "Aquí, limpiando." and bubble.position.y > 2.0,
		"the line does not show over the resident who said it")
	check(player.get_node_or_null("ChatBubble") != null, "the player's own line does not show over their head")
	check(residents.RESIDENT_NEAR.get_node_or_null("ChatBubble") == null, "a line shows over someone who did not say it")

	server._token = ""
	scene.queue_free()
	current_scene = null
	await frames()
	print("CHAT_BOX_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
