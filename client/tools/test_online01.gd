extends SceneTree
## Real HTTP integration: two Godot processes, one disposable World Core.
var failed := false

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error("ONLINE01 // " + message)

func run() -> void:
	var api := root.get_node("WorldApi")
	var presence := root.get_node("OnlinePresence")
	var role := OS.get_environment("LAIN_TEST_PLAYER_NAME")
	check(root.get_node("ServerConnection").is_online(), "Missing authenticated transport")
	change_scene_to_file("res://scenes/boot/Boot.tscn")
	var deadline := Time.get_ticks_msec() + 75000
	var sent_hello := false
	var sent_ack := false
	var sent_ready := false
	var moving := false
	var captured := false
	while Time.get_ticks_msec() < deadline and not failed:
		await create_timer(0.1).timeout
		if api.snapshot.is_empty():
			continue
		check(api.snapshot.player.name == role, "Wrong player identity")
		var location := str(api.snapshot.player.location)
		var history := "\n".join(presence._history)
		if not sent_hello and presence._peers.size() == 1:
			var peer: Node = presence._peers.values()[0]
			check(peer is CharacterBody3D and peer.get_child_count() >= 2, "Missing avatar or name")
			presence._send_chat("hola-" + role)
			sent_hello = true
		if sent_hello and not captured and presence._peers.size() == 1 and "hola-Alice" in history and "hola-Bob" in history:
			var panel: Control = presence._chat_input.get_parent().get_parent()
			check(Rect2(Vector2.ZERO, root.get_visible_rect().size).encloses(panel.get_global_rect()), "Chat panel outside screen")
			var capture := OS.get_environment("LAIN_ONLINE_CAPTURE")
			if not capture.is_empty() and role == "Alice":
				await RenderingServer.frame_post_draw
				check(root.get_texture().get_image().save_png(capture) == OK, "Screenshot failed")
			captured = true
		if role == "Alice" and captured and not sent_ack:
			presence._send_chat("recibido-Alice")
			sent_ack = true
		if role == "Bob" and captured and "recibido-Alice" in history and not sent_ready:
			presence._send_chat("listo-Bob")
			sent_ready = true
		if role == "Alice" and "listo-Bob" in history and not moving:
			api.step("MOVE", "SCHOOL")
			moving = true
		if role == "Alice" and moving and location == "SCHOOL" and current_scene != null:
			if current_scene.scene_file_path.ends_with("School.tscn") and presence._peers.is_empty():
				print("ONLINE01_CLIENT_OK Alice identity=own chat=both scene=school peers=0")
				quit(1 if failed else 0)
				return
		if role == "Bob" and sent_ready and presence._peers.is_empty():
			check(location == "APARTMENT_DISTRICT", "Other player's movement changed our location")
			print("ONLINE01_CLIENT_OK Bob identity=own chat=both scene=district peers=0")
			quit(1 if failed else 0)
			return
	check(false, "Timed out waiting for two clients and chat")
	quit(1)
