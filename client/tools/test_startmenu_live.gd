extends SceneTree
## Real HTTP against a running online World Core (started by tools/smoke_startmenu.py):
## sign up from the start menu, enter the world, then log in again.
var failed := false

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, reason: String) -> void:
	if not ok:
		failed = true
		push_error("STARTMENU_LIVE // " + reason)

func wait_reply(boot: Node, seconds := 20.0) -> void:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while not boot.pending.is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame

func press(boot: Node, text: String) -> void:
	for node in boot.form.get_children():
		if node is Button and node.text == text:
			node.pressed.emit()
			return
	check(false, "Button not found: " + text)

func run() -> void:
	var server := root.get_node("ServerConnection")
	var api := root.get_node("WorldApi")
	server.session_path = "user://test_startmenu_live_session.json"
	server.clear_session()
	check(server.is_online_mode() and server.awaiting_login, "Client did not start in online menu mode")
	var name := "Prueba" + str(randi() % 9000 + 1000)
	var boot: Node = load("res://scenes/boot/Boot.tscn").instantiate()
	root.add_child(boot)
	current_scene = boot
	await process_frame
	press(boot, "Crear una cuenta nueva")
	boot.fields.name.text = name
	boot.fields.password.text = "clave-de-prueba"
	boot.fields.repeat.text = "clave-de-prueba"
	press(boot, "Crear cuenta")
	await wait_reply(boot)
	check(boot.fields.has("invite") and "hace falta un código" in boot.notice.text,
		"The world with an invite code did not ask for it: " + boot.notice.text)
	boot.fields.invite.text = "codigo-equivocado"
	press(boot, "Crear cuenta")
	await wait_reply(boot)
	check("invitación no es correcto" in boot.notice.text, "Wrong invite accepted or unexplained: " + boot.notice.text)
	boot.fields.invite.text = OS.get_environment("LAIN_TEST_INVITE")
	press(boot, "Crear cuenta")
	await wait_reply(boot)
	check(server.has_session() and server.account_name == name, "Sign-up failed: " + boot.notice.text)
	press(boot, "Continuar")
	var deadline := Time.get_ticks_msec() + 30000
	while api.snapshot.get("player", {}).get("name", "") != name and Time.get_ticks_msec() < deadline:
		await process_frame
	check(api.snapshot.get("player", {}).get("name", "") == name, "World snapshot not received for the new player")
	check(str(api.snapshot.get("player", {}).get("location", "")) == "APARTMENT", "New player is not at home")

	# Another PC: log in with name and password.
	server.clear_session()
	server.awaiting_login = true
	await create_timer(0.2).timeout
	# Entering the world changed the scene and already freed the menu.
	if is_instance_valid(boot):
		boot.queue_free()
	await process_frame
	boot = load("res://scenes/boot/Boot.tscn").instantiate()
	root.add_child(boot)
	await process_frame
	boot.fields.name.text = name.to_upper()
	boot.fields.password.text = "clave-de-prueba"
	press(boot, "Entrar")
	await wait_reply(boot)
	check(server.has_session() and not server.awaiting_login, "Login did not enter: " + boot.notice.text)
	server.clear_session()
	print("STARTMENU_LIVE_", "FAILED" if failed else "OK", " player=", name)
	quit(1 if failed else 0)
