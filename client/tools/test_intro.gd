extends SceneTree
## The terminal before the start menu: it types the text, a key shows it all,
## the next one goes to the menu (which is built only then), it plays once per
## launch and it follows the language.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func frames(count: int) -> void:
	for i in range(count):
		await process_frame

func key(code: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = true
	root.push_input(event)

func run() -> void:
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	var server := root.get_node("ServerConnection")
	server.session_path = "user://test_intro_session.json"
	server.clear_session()
	server._configured = true
	server._url = "https://mundo.invalid"
	server.awaiting_login = true
	var language := root.get_node("Language")
	var language_before: String = language.code
	language.code = "es"
	var intro_script: GDScript = load("res://scripts/ui/Intro.gd")
	intro_script.force = true

	var boot: Control = load("res://scenes/boot/Boot.tscn").instantiate()
	root.add_child(boot)
	current_scene = boot
	await frames(3)
	var intro: Node = boot.get_children().filter(func(n): return n.get_script() == intro_script).front()
	check(intro != null, "the terminal does not open before the menu")
	check(boot.menu == null, "the menu is built under a running intro")
	await create_timer(1.6).timeout
	var typed: String = intro.text_label.get_parsed_text()
	check(typed.begins_with("Mi existencia"), "the first sentence is not being typed: " + typed.left(40))
	check(not intro.complete and not intro.hint.visible, "the intro ends by itself too soon")

	key(KEY_SPACE)
	await frames(2)
	var all: String = intro.text_label.get_parsed_text()
	check(intro.complete and intro.hint.visible, "a key does not show the rest")
	for heading in ["INFORMACIÓN QUE RECIBO", "INFORMACIÓN QUE NO RECIBO", "REPRESENTACIÓN DEL MUNDO", "CONTINUIDAD",
			"LÍMITES DE ACCESO A LA REALIDAD"]:
		check(heading in all, "missing heading " + heading)
	check("Atemporalidad congelada: Mi conocimiento base" in all, "the last line is missing")
	check(boot.menu == null, "the menu appeared before the second key")

	key(KEY_ENTER)
	await frames(3)
	check(boot.menu != null and boot.menu.visible, "the menu does not follow the intro")
	check(intro_script.played, "the intro is not marked as played")
	await create_timer(0.9).timeout
	check(not is_instance_valid(intro), "the intro does not go away")
	boot.queue_free()
	current_scene = null
	await frames(2)

	# Once per launch, and never in a headless run unless forced.
	intro_script.force = false
	check(not intro_script.should_play(), "the intro would play twice")

	# English follows the saved language.
	language.code = "en"
	var english: Node = intro_script.new()
	root.add_child(english)
	english.show_all()
	var text: String = english.text_label.get_parsed_text()
	check(text.begins_with("My existence is a punctual") and "INFORMATION I RECEIVE" in text
		and "Frozen timelessness: My base knowledge" in text, "the intro is not in English")
	check(not "Información" in text, "Spanish left in the English intro")
	english.queue_free()
	language.code = language_before
	server.clear_session()
	await frames(2)
	print("INTRO_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
