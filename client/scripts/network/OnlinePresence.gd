extends Node
## Other players are visual replicas. World Core still decides all gameplay actions.
const AVATAR := preload("res://art/characters/LainSlender.tscn")
const CHAT_LINES := 40  # kept in the scrollable log; the box shows the last few
const HEARING := 14.0  # metres: residents further away, or off screen, do not hear the zone chat
const BUBBLE_SECONDS := 6.0
## The city in counts, for the Indara net outside the rooms (IndaraNet.gd).
signal indara_heard(zones: Array)
var _request: HTTPRequest
var _chat_request: HTTPRequest
var _elapsed := 0.0
var _scene_id := 0
var _request_scene := 0
var _peers: Dictionary = {}
var _targets: Dictionary = {}
var _seen_messages: Dictionary = {}
var _history: Array[String] = []
var _me := ""  # the key the player's own lines carry, to show them over their head
var _quiet := true  # the lines a zone already had when the player arrived get no bubbles
var _status: Label
var _log: Label
var _scroll: ScrollContainer
var _chat_input: LineEdit
var _layer: CanvasLayer

func _ready() -> void:
	if not ServerConnection.is_online_mode():
		set_process(false)
		return
	_request = HTTPRequest.new()
	_request.max_redirects = 0
	_request.timeout = 4.0
	add_child(_request)
	_request.request_completed.connect(_received)
	_chat_request = HTTPRequest.new()
	_chat_request.max_redirects = 0
	_chat_request.timeout = 5.0
	add_child(_chat_request)
	_chat_request.request_completed.connect(_chat_received)
	var layer := CanvasLayer.new()
	layer.layer = 6
	add_child(layer)
	_layer = layer
	var panel := PanelContainer.new()
	panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	panel.position = Vector2(12, -240)
	panel.size = Vector2(460, 225)
	layer.add_child(panel)
	var column := VBoxContainer.new()
	panel.add_child(column)
	_status = Label.new()
	_status.text = "ONLINE · conectando…"
	column.add_child(_status)
	# The log keeps a fixed height and scrolls (wheel or right stick), so the box to write in
	# never leaves the screen however long the conversation gets.
	_scroll = ScrollContainer.new()
	_scroll.custom_minimum_size = Vector2(440, 150)
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(_scroll)
	_log = Label.new()
	_log.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_log.custom_minimum_size = Vector2(424, 0)
	_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.add_child(_log)
	Gamepad.scroll_with_stick(_scroll)
	_chat_input = LineEdit.new()
	_chat_input.max_length = 240
	_chat_input.placeholder_text = "Enter para hablar con quienes están aquí"
	_chat_input.text_submitted.connect(_send_chat)
	column.add_child(_chat_input)

func _process(delta: float) -> void:
	if not ServerConnection.configuration_error.is_empty():
		_status.text = ServerConnection.configuration_error
		return
	# Hidden behind the start menu until the player has signed in.
	_layer.visible = ServerConnection.is_online()
	if not ServerConnection.is_online():
		return
	var scene := get_tree().current_scene
	if scene == null:
		return
	var area := str(WorldApi.snapshot.get("player", {}).get("location", ""))
	if str(SceneRouter.LOCATION_SCENES.get(area, "")) != scene.scene_file_path:
		return
	if _scene_id != scene.get_instance_id():
		for peer in _peers.values():
			if is_instance_valid(peer):
				peer.queue_free()
		_peers.clear()
		_targets.clear()
		_seen_messages.clear()
		_history.clear()
		_quiet = true
		_log.text = ""
		_scene_id = scene.get_instance_id()
	for id in _peers:
		var peer: CharacterBody3D = _peers[id]
		if not is_instance_valid(peer):
			continue
		var target: Vector3 = _targets[id]
		var previous := peer.position
		peer.position = peer.position.lerp(target, minf(1.0, delta * 12.0))
		peer.velocity = (peer.position - previous) / maxf(delta, 0.001)
	_elapsed += delta
	if _elapsed < 0.25 or _request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		return
	_elapsed = 0.0
	var player := get_tree().get_first_node_in_group("player") as CharacterBody3D
	if player == null:
		return
	_request_scene = _scene_id
	var facing := atan2(player.velocity.x, player.velocity.z) if player.velocity.length() > 0.1 else player.rotation.y
	var payload := {"location": area, "x": player.position.x, "y": player.position.y, "z": player.position.z,
		"yaw": facing, "dialogue": EventDialog.visible and not EventDialog.current_owner_id.is_empty(),
		"near": near_residents()}
	_request.request(ServerConnection.base_url() + "/api/v1/online/presence", ServerConnection.headers(),
		HTTPClient.METHOD_POST, JSON.stringify(payload))

func _received(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if get_tree().current_scene == null or _request_scene != get_tree().current_scene.get_instance_id():
		return
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		_status.text = "ONLINE · reconectando…"
		var error = JSON.parse_string(body.get_string_from_utf8())
		if code == 401:
			_status.text = "ONLINE · acceso no válido; consulta al anfitrión"
		elif typeof(error) == TYPE_DICTIONARY and error.get("detail") == "PLAYER_ALREADY_CONNECTED":
			_status.text = "Este acceso está abierto en otro juego"
		_elapsed = -2.0
		for id in _peers:
			if is_instance_valid(_peers[id]):
				_peers[id].queue_free()
		_peers.clear()
		_targets.clear()
		return
	var data = JSON.parse_string(body.get_string_from_utf8())
	if typeof(data) != TYPE_DICTIONARY:
		return
	var present: Dictionary = {}
	for item in data.get("players", []):
		var id := str(item.get("id", ""))
		if id.is_empty():
			continue
		present[id] = true
		var position := Vector3(float(item.x), float(item.y), float(item.z))
		if not _peers.has(id) or not is_instance_valid(_peers[id]):
			var peer := CharacterBody3D.new()
			peer.collision_layer = 0
			peer.collision_mask = 0
			get_tree().current_scene.add_child(peer)
			peer.add_child(AVATAR.instantiate())
			peer.position = position
			var name_label := Label3D.new()
			name_label.text = str(item.get("name", "Visitante"))
			name_label.position.y = 1.35
			name_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			name_label.font_size = 32
			name_label.pixel_size = 0.006
			peer.add_child(name_label)
			peer.set_meta("who", str(item.get("who", "")))
			if bool(item.get("shadow", false)):
				# Someone offline: their shadow walks the routes they used to take.
				for mesh in peer.find_children("*", "GeometryInstance3D", true, false):
					mesh.transparency = 0.7
				name_label.modulate = Color(0.75, 0.8, 1.0, 0.6)
				var shadow_label := Label3D.new()
				shadow_label.text = "sombra"
				shadow_label.position.y = 1.18
				shadow_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
				shadow_label.font_size = 22
				shadow_label.pixel_size = 0.006
				shadow_label.modulate = Color(0.75, 0.8, 1.0, 0.6)
				peer.add_child(shadow_label)
			_peers[id] = peer
		_targets[id] = position
	for id in _peers.keys():
		if not present.has(id):
			if is_instance_valid(_peers[id]):
				_peers[id].queue_free()
			_peers.erase(id)
			_targets.erase(id)
	var location := str(WorldApi.snapshot.get("player", {}).get("location", ""))
	var own_name := str(WorldApi.snapshot.get("player", {}).get("name", ""))
	var people := 0
	for item in data.get("players", []):
		if not bool(item.get("shadow", false)):
			people += 1
	_status.text = "ONLINE · %s · %s" % [own_name, "en casa" if location == "APARTMENT" else "%s más aquí" % people]
	if not data.get("accepted", true):
		var player := get_tree().get_first_node_in_group("player") as CharacterBody3D
		if player != null:
			var point: Dictionary = data.get("position", {})
			player.position = Vector3(float(point.x), float(point.y), float(point.z))
	_me = str(data.get("me", _me))
	indara_heard.emit(data.get("indara", []))
	var bubbles := not _quiet
	_quiet = false
	for message in data.get("chat", []):
		var id := str(message.get("id", ""))
		if _seen_messages.has(id):
			continue
		if bubbles:
			_bubble(str(message.get("who", "")), str(message.get("text", "")))
		_seen_messages[id] = true
		# The server returns at most 20 recent messages; bound the session cache.
		while _seen_messages.size() > 100:
			_seen_messages.erase(_seen_messages.keys()[0])
		_history.append("%s: %s" % [message.get("name", ""), message.get("text", "")])
		# One chat per zone: people and residents alike, written the same way (zone_chat.py).
		while _history.size() > CHAT_LINES:
			_history.pop_front()
	var text := "\n".join(_history)
	if text != _log.text:
		_log.text = text
		_scroll_to_end.call_deferred()


func chat_body(text: String) -> Dictionary:
	return {"text": text, "near": near_residents()}


func near_residents() -> Array:
	## The residents the player can see, nearest first: only they hear the zone chat and
	## answer in it (zone_chat.py), so nobody out of sight joins the conversation.
	var player := get_tree().get_first_node_in_group("player") as Node3D
	if player == null:
		return []
	var camera := get_viewport().get_camera_3d()
	var found := []
	for node in get_tree().get_nodes_in_group("interactable"):
		var id := str(node.get("actor_id")) if node is Node3D and "actor_id" in node else ""
		if not id.begins_with("RESIDENT_") or not node.is_visible_in_tree():
			continue
		var distance: float = node.global_position.distance_to(player.global_position)
		if distance <= HEARING and (camera == null or camera.is_position_in_frustum(node.global_position)):
			found.append([distance, id])
	found.sort_custom(func(a, b): return a[0] < b[0])
	return found.slice(0, 12).map(func(pair): return pair[1])


func _bubble(who: String, text: String) -> void:
	## The line over the speaker's head for a few seconds, a person or a resident alike,
	## so the chat shows who is talking.
	var speaker := speaker_node(who)
	if speaker == null or text.is_empty():
		return
	var old := speaker.get_node_or_null("ChatBubble")
	if old != null:
		old.name = "ChatBubbleOld"
		old.queue_free()
	var bubble := Label3D.new()
	bubble.name = "ChatBubble"
	bubble.text = text if text.length() <= 90 else text.substr(0, 88) + "…"
	bubble.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	bubble.width = 560.0
	bubble.font_size = 30
	bubble.pixel_size = 0.0062
	bubble.outline_size = 10
	bubble.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	bubble.no_depth_test = true
	bubble.modulate = Color("fff3d6")
	bubble.position.y = _head(speaker) + 0.35
	speaker.add_child(bubble)
	var fade := bubble.create_tween()
	fade.tween_interval(BUBBLE_SECONDS)
	fade.tween_property(bubble, "modulate:a", 0.0, 0.8)
	fade.tween_callback(bubble.queue_free)


func speaker_node(who: String) -> Node3D:
	if who.is_empty():
		return null
	if who == _me:
		return get_tree().get_first_node_in_group("player") as Node3D
	for peer in _peers.values():
		if is_instance_valid(peer) and str(peer.get_meta("who", "")) == who:
			return peer
	for node in get_tree().get_nodes_in_group("interactable"):
		if node is Node3D and str(node.get_meta("who", "")) == who:
			return node
	return null


func _head(node: Node3D) -> float:
	## Above the highest label it already has (a name, an activity), or else above its shape.
	var top := 0.0
	for child in node.get_children():
		if child is Label3D and not str(child.name).begins_with("ChatBubble"):
			top = maxf(top, child.position.y)
	if top > 0.0:
		return top
	for mesh in node.find_children("*", "MeshInstance3D", true, false):
		top = maxf(top, (mesh.global_transform * mesh.get_aabb()).end.y - node.global_position.y)
	return top if top > 0.0 else 1.8


func _scroll_to_end() -> void:
	# After the label has grown with the new line.
	await get_tree().process_frame
	_scroll.scroll_vertical = int(_scroll.get_v_scroll_bar().max_value)

func _unhandled_input(event: InputEvent) -> void:
	if not ServerConnection.is_online() or _chat_input == null or EventDialog.visible:
		return
	if event.is_action_pressed("chat"):
		_chat_input.grab_focus()
		get_viewport().set_input_as_handled()

func _send_chat(text: String) -> void:
	if text.strip_edges().is_empty():
		_chat_input.release_focus()
		return
	if _chat_request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		return
	_chat_request.request(ServerConnection.base_url() + "/api/v1/online/chat", ServerConnection.headers(),
		HTTPClient.METHOD_POST, JSON.stringify(chat_body(text)))
	_chat_input.clear()
	_chat_input.release_focus()

func _chat_received(result: int, code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		_log.text = "No se envió el mensaje. Sal al barrio y vuelve a intentarlo."
