extends SceneTree
var failed := false

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, why: String) -> void:
	if not ok:
		failed = true
		push_error("I18N // " + why)

func run() -> void:
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	var language := root.get_node("Language")
	var original_code: String = language.code
	var original_path: String = language.settings_path
	language.settings_path = "user://test_i18n_language.cfg"
	var connection := root.get_node("ServerConnection")
	connection._configured = true
	connection._url = "https://mundo.invalid"
	connection.awaiting_login = true
	language.select("en")
	check(tr("Entrar") == "Log in", "Static native translation: " + tr("Entrar"))
	check(tr("Sesión: Guardar {v0}") == "Signed in: Guardar {v0}", "Player name was changed")
	check(tr("IDENTIDAD  Nora\nENERGÍA  0.75") == "IDENTITY  Nora\nENERGY  0.75", "Dynamic journal labels")
	check("X-Lain-Language: en" in connection.headers(), "World language header")
	check("X-Lain-Language: en" in connection.account_headers(), "Account language header")
	var saved := ConfigFile.new()
	check(saved.load(language.settings_path) == OK and saved.get_value("language", "code") == "en", "Language not saved")
	var boot: Control = load("res://scenes/boot/Boot.tscn").instantiate()
	root.add_child(boot)
	await process_frame
	check(boot.menu.get_node("LanguageSelector").selected == 1, "Menu selector")
	boot.fields.name.text = "Guardar"
	boot.fields.password.text = "no-change"
	language.select("es")
	check(tr("Entrar") == "Entrar", "Switch back to Spanish")
	check(boot.fields.name.text == "Guardar" and boot.fields.password.text == "no-change", "Switch erased form")
	language.select("en")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="):
			await process_frame
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(arg.trim_prefix("--capture="))
	boot.queue_free()
	language.select(original_code)
	language.settings_path = original_path
	DirAccess.remove_absolute("user://test_i18n_language.cfg")
	await process_frame
	print("I18N_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
