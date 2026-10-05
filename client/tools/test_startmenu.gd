extends SceneTree
## Online start menu: sign up, log in, errors, expired and legacy sessions.
var failed := false
var capture := ""

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, reason: String) -> void:
	if not ok:
		failed = true
		push_error("STARTMENU // " + reason)

func snap(name: String) -> void:
	await process_frame
	await process_frame
	if not capture.is_empty():
		await create_timer(0.6).timeout
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(capture.path_join(name + ".png")) == OK, "Capture failed")

func answer(boot: Node, code: int, body: Dictionary) -> void:
	boot.request.cancel_request()
	boot._completed(HTTPRequest.RESULT_SUCCESS, code, PackedStringArray(), JSON.stringify(body).to_utf8_buffer())

func buttons(boot: Node) -> Array:
	return boot.form.get_children().filter(func(n): return n is Button).map(func(n): return n.text)

func press(boot: Node, text: String) -> void:
	for node in boot.form.get_children():
		if node is Button and node.text == text:
			node.pressed.emit()
			return
	check(false, "Button not found: " + text + " in " + str(buttons(boot)))

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): capture = arg.trim_prefix("--capture=")
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	var server := root.get_node("ServerConnection")
	server.session_path = "user://test_startmenu_session.json"
	server.clear_session()
	server._configured = true
	server._url = "https://mundo.invalid"
	server.awaiting_login = true
	server.client_version = "0.13.0"

	var boot: Control = load("res://scenes/boot/Boot.tscn").instantiate()
	root.add_child(boot)
	current_scene = boot
	await process_frame
	check(boot.fields.has("name") and boot.fields.has("password"), "Login form not shown without a session")
	check("Entrar" in buttons(boot) and "Crear una cuenta nueva" in buttons(boot), "Login buttons missing")
	await snap("startmenu-login")

	press(boot, "Crear una cuenta nueva")
	check(boot.fields.has("invite") and boot.fields.has("repeat"), "Register form incomplete")
	boot.fields.name.text = "Mio"
	boot.fields.password.text = "lluvia-neon"
	boot.fields.repeat.text = "otra"
	boot.fields.invite.text = "cable-nodo-482"
	press(boot, "Crear cuenta")
	check("no coinciden" in boot.notice.text and boot.pending.is_empty(), "Mismatched passwords were sent")
	boot.fields.repeat.text = "lluvia-neon"
	await snap("startmenu-register")
	press(boot, "Crear cuenta")
	check(boot.pending == "register", "Registration not sent")
	answer(boot, 409, {"detail": "INVALID_INVITE"})
	check("invitación no es correcto" in boot.notice.text, "Invite error not explained: " + boot.notice.text)
	press(boot, "Crear cuenta")
	answer(boot, 200, {"token": "t".repeat(43), "name": "Mio", "actor_id": "PLAYER_1"})
	check(server.has_session() and server.account_name == "Mio", "Session not stored")
	check(FileAccess.file_exists(server.session_path), "Session file not written")
	check("Continuar" in buttons(boot) and "Bienvenido" in boot.notice.text, "Menu not shown after sign-up")
	check(not server.is_online(), "World access opened before Continuar")
	await snap("startmenu-menu")
	press(boot, "Continuar")
	check(server.is_online() and not server.awaiting_login and not boot.menu.visible, "Continuar did not enter the world")

	# A later launch: remembered session, then it expires on the server.
	server.awaiting_login = true
	server._token = server._load_session()
	check(server.session_token() == "t".repeat(43), "Session not reloaded for this server")
	boot.queue_free()
	await process_frame
	boot = load("res://scenes/boot/Boot.tscn").instantiate()
	root.add_child(boot)
	await process_frame
	check(boot.pending == "me", "Remembered session not checked")
	answer(boot, 401, {"detail": "INVALID_PLAYER_ACCESS"})
	check(not server.has_session() and boot.fields.has("password") and "caducado" in boot.notice.text, "Expired session not handled")
	boot.fields.name.text = "Mio"
	boot.fields.password.text = "mal"
	press(boot, "Entrar")
	answer(boot, 401, {"detail": "INVALID_LOGIN"})
	check("incorrectos" in boot.notice.text, "Wrong password not explained")

	# An owner-created account from an old lain-online.json has no password yet.
	server._token = "o".repeat(43)
	boot._check_session()
	answer(boot, 200, {"name": "Enrique", "has_password": false, "actor_id": "PLAYER_2", "signup": "INVITE"})
	check("Ponle una contraseña a tu cuenta" in buttons(boot) and "cualquier PC" in boot.notice.text, "Legacy account not invited to set a password")
	press(boot, "Ponle una contraseña a tu cuenta")
	check(not boot.fields.has("current") and boot.fields.has("new"), "First password must not ask for a current one")
	boot.fields.new.text = "mi-clave-nueva"
	boot.fields.repeat.text = "mi-clave-nueva"
	press(boot, "Guardar")
	answer(boot, 200, {"name": "Enrique", "has_password": true, "actor_id": "PLAYER_2"})
	check("Cambiar contraseña" in buttons(boot) and "Contraseña guardada" in boot.notice.text, "Password not confirmed")
	press(boot, "Cerrar sesión")
	check(not server.has_session() and boot.fields.has("name"), "Logout did not return to the login form")

	# A build without the Windows launcher (the Mac app) brings its server and version in release.json,
	# and the start menu offers a newer version with the download for this system.
	var release_path := "user://test_release.json"
	var file := FileAccess.open(release_path, FileAccess.WRITE)
	file.store_string(JSON.stringify({"server_url": "https://mundo.invalid", "version": "0.27.0",
		"manifest": "https://releases.invalid/manifest.json",
		"downloads": {OS.get_name(): "https://releases.invalid/SesionCero-Mac.zip"}, "page": "https://mundo.invalid"}))
	file.close()
	check(server.load_release(release_path).get("version") == "0.27.0", "release.json not read")
	check(server.load_release("user://missing.json").is_empty(), "A missing release.json is not empty")
	check(server.newer("0.28.0", "0.27.9") and server.newer("0.27.10", "0.27.9") and not server.newer("0.27.0", "0.27.0")
		and not server.newer("0.26.5", "0.27.0") and not server.newer("", "0.27.0"), "Versions compare wrongly")
	server.release = server.load_release(release_path)
	server.client_version = "0.27.0"
	check(server.updates_itself() == OS.get_environment("LAIN_CLIENT_VERSION").is_empty(), "Who updates the game is wrong")
	check(server.download_url() == "https://releases.invalid/SesionCero-Mac.zip", "Wrong download for this system")
	boot.offer_update("0.27.0")
	check(not is_instance_valid(boot.update_box), "The same version is offered as new")
	boot.offer_update("0.28.0")
	check(is_instance_valid(boot.update_box) and boot.update_box.get_parent() == boot.menu, "A newer version is not offered")
	var offered: Array = boot.update_box.get_children().map(func(n): return n.text)
	check("Hay una versión nueva: 0.28.0. Descárgala para jugar con lo último." in offered
		and "Descargar la versión 0.28.0" in offered, "The update notice is wrong: " + str(offered))
	boot.offer_update("0.29.0")
	check(boot.menu.get_children().filter(func(n): return n is VBoxContainer and n == boot.update_box).size() == 1,
		"The update notice repeats")
	await snap("startmenu-update")
	server.release = {}
	DirAccess.remove_absolute(ProjectSettings.globalize_path(release_path))

	server.clear_session()
	current_scene = null
	boot.queue_free()
	await process_frame
	print("STARTMENU_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
