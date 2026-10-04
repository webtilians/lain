extends SceneTree
## Capa 03 client: PC tab, shell, cabinet console and the fading signal.
var failed := false
var capture := ""

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, reason: String) -> void:
	if not ok:
		failed = true
		push_error("LAYER03 // " + reason)

func snap(name: String) -> void:
	await process_frame
	await process_frame
	if not capture.is_empty():
		await create_timer(1.0).timeout
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(capture.path_join(name + ".png")) == OK, "Capture failed")

func reply(shell: Node, output: String, cwd: String) -> void:
	shell.request.cancel_request()
	var body := {"result": {"output": output, "cwd": cwd, "hostname": "navi-enrique", "changed": false}, "state": null}
	shell._completed(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify(body).to_utf8_buffer())

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): capture = arg.trim_prefix("--capture=")
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var fixtures: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tools/fixtures/workshop01.json"))
	var state: Dictionary = fixtures.home
	state["layer_three"] = {"active": true, "title": "Capa 03 · TTL", "packet": "p-f6a2", "hostname": "navi-enrique",
		"assembled": false, "exposed": false, "decision": null, "fragments": 0,
		"goal": "Encuentra en qué armario de enlace murió p-f6a2 y reconstrúyelo.",
		"mail": {"subject": "TTL=1", "from": "desconocido@wired", "body": "Si lees esto, me queda un salto."}}
	api.snapshot = state
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	var scene: Node3D = load(paths[state.player.location]).instantiate()
	root.add_child(scene)
	current_scene = scene
	var player: CharacterBody3D = scene.get_node("Player")
	await process_frame
	await physics_frame
	var ws := root.get_node("Workshop")
	var shell := root.get_node("ShellTerminal")
	var presence := root.get_node("PresenceSignal")

	ws.open_pc()
	var labels := ""
	for node in ws.content.find_children("*", "Label", true, false):
		labels += node.text + "\n"
	check("TTL=1" in labels, "Layer mail missing from Correo")
	var tab_titles: Array = ws.tabs.get_children().map(func(b): return b.text)
	check("Terminal" in tab_titles, "Terminal tab missing")
	ws._select("Terminal")
	await snap("layer03-pc-terminal-tab")
	for b in ws.content.find_children("*", "Button", true, false):
		if b.text == "Abrir el terminal": b.pressed.emit()
	check(shell.is_open() and shell.host == "navi", "PC button does not open the home shell")
	reply(shell, "NAVI · terminal doméstico conectado a la Wired.", "/home/enrique")
	check("NAVI" in shell.output.text, "Banner not printed")
	check(shell.prompt.text.ends_with("navi-enrique:/home/enrique$"), "Prompt does not follow cwd: " + shell.prompt.text)
	shell._submit("cat ~/correo/ttl1.eml")
	check(shell.busy, "Command was not sent")
	reply(shell, "Asunto: TTL=1\nSi lees esto, me queda un salto.", "/home/enrique")
	check("me queda un salto" in shell.output.text and not shell.busy, "Reply not shown")
	await snap("layer03-shell")
	var up := InputEventKey.new()
	up.keycode = KEY_UP
	up.pressed = true
	shell.input.grab_focus()
	shell._input(up)
	check(shell.input.text == "cat ~/correo/ttl1.eml", "History does not recall the last command")
	var esc := InputEventAction.new()
	esc.action = "ui_cancel"
	esc.pressed = true
	shell._input(esc)
	check(not shell.is_open() and ws.is_open(), "Esc must close only the shell")
	check(not player.is_physics_processing(), "Closing the shell over the PC freed the player")
	ws.close_pc()
	check(player.is_physics_processing(), "Player not released after the PC")

	var conflict := root.get_node("NetworkConflict")
	conflict._present({"speaker": "WIRED", "text": "Armario", "choices": [
		{"text": "Conectarse al puerto de consola del armario.", "action": "CONSOLE", "relay": "RELAY_STATION"}]})
	conflict._choose(conflict.OWNER, "0")
	check(shell.is_open() and shell.host == "RELAY_STATION", "Cabinet console does not open the relay shell")
	check(not conflict.busy, "Console choice must not send a network action")
	check(shell.output.text.is_empty() or not "NAVI" in shell.output.text, "Relay shell kept the home output")
	shell.request.cancel_request()
	shell._done("")
	shell.close_shell()
	check(player.is_physics_processing(), "Relay shell did not release the player")

	presence.silence = presence.FADE_AFTER + presence.FADE_SPAN + 5.0
	await process_frame
	await process_frame
	var faded := 0.0
	for mesh in player.find_children("*", "GeometryInstance3D", true, false):
		faded = maxf(faded, mesh.transparency)
	check(faded >= 0.55, "Avatar does not fade without anyone receiving it: " + str(faded))
	check("CASI NO ESTÁS" in presence.hud.text, "Weak signal not announced")
	await snap("layer03-fading")
	ws.open_pc()
	await process_frame
	await process_frame
	var solid := 1.0
	for mesh in player.find_children("*", "GeometryInstance3D", true, false):
		solid = minf(solid, 1.0 - mesh.transparency)
	check(solid >= 0.99 and presence.silence == 0.0, "Being received does not restore the avatar")
	ws.close_pc()

	# Capa 04 takes over the corner HUD and adds its mail to the PC.
	state["layer_four"] = {"active": true, "title": "Capa 04 · Transporte", "decision": null, "fragments": 1,
		"goal": "Alguien llama a tu puerto 4004 desde NODO_07. Contesta a su SYN a mano.",
		"mail": {"subject": "SYN", "from": "syn@wired", "body": "Alguien llama a tu puerto 4004 desde NODO_07 y nadie contesta."}}
	api.snapshot = state
	await process_frame
	await process_frame
	check("Capa 04" in presence.hud.text and "4004" in presence.hud.text, "HUD does not follow the newest layer: " + presence.hud.text)
	ws.open_pc()
	var mails := ""
	for node in ws.content.find_children("*", "Label", true, false):
		mails += node.text + "\n"
	check("SYN" in mails and "TTL=1" in mails, "PC mail must list both layers")
	ws._select("Terminal")
	var terminal_text := ""
	for node in ws.content.find_children("*", "Label", true, false):
		terminal_text += node.text + "\n"
	check("Capa 04" in terminal_text and "1/7" in terminal_text, "Terminal page does not show Capa 04")
	await snap("layer04-pc")
	ws.close_pc()

	# Capa 05 follows the same way, newest mail first.
	state["layer_five"] = {"active": true, "title": "Capa 05 · Sesión", "decision": null, "fragments": 2,
		"goal": "Tu cuenta solo admite una sesión. En la consola del andén, fusiona tu estado con el de la Sesión Cero.",
		"mail": {"subject": "Dos sesiones, una cuenta", "from": "sesiones@wired",
			"body": "NODO_07 ha encontrado una sesión caducada con tu nombre. Lee ~/correo/sesion.eml en el Terminal."}}
	api.snapshot = state
	await process_frame
	await process_frame
	check("Capa 05" in presence.hud.text and "Sesión Cero" in presence.hud.text, "HUD does not follow Capa 05: " + presence.hud.text)
	ws.open_pc()
	mails = ""
	for node in ws.content.find_children("*", "Label", true, false):
		mails += node.text + "\n"
	check(mails.find("Dos sesiones") >= 0 and mails.find("Dos sesiones") < mails.find("SYN"), "Capa 05 mail must come first")
	ws._select("Terminal")
	terminal_text = ""
	for node in ws.content.find_children("*", "Label", true, false):
		terminal_text += node.text + "\n"
	check("Capa 05" in terminal_text and "2/7" in terminal_text, "Terminal page does not show Capa 05")
	await snap("layer05-pc")
	ws.close_pc()

	# And Capa 06 after it.
	state["layer_six"] = {"active": true, "title": "Capa 06 · Presentación", "decision": null, "fragments": 3,
		"goal": "El último paquete de la Sesión Cero llegó con tres caras. En la consola del videoclub, descubre cuál es la suya.",
		"mail": {"subject": "Tres caras", "from": "relay-video@wired",
			"body": "El último paquete de la Sesión Cero ha llegado tres veces. Lee ~/correo/caras.eml en el Terminal."}}
	api.snapshot = state
	await process_frame
	await process_frame
	check("Capa 06" in presence.hud.text and "videoclub" in presence.hud.text, "HUD does not follow Capa 06: " + presence.hud.text)
	ws.open_pc()
	mails = ""
	for node in ws.content.find_children("*", "Label", true, false):
		mails += node.text + "\n"
	check(mails.find("Tres caras") >= 0 and mails.find("Tres caras") < mails.find("Dos sesiones"), "Capa 06 mail must come first")
	ws._select("Terminal")
	terminal_text = ""
	for node in ws.content.find_children("*", "Label", true, false):
		terminal_text += node.text + "\n"
	check("Capa 06" in terminal_text and "3/7" in terminal_text, "Terminal page does not show Capa 06")
	await snap("layer06-pc")
	ws.close_pc()

	# And the last layer, Capa 07.
	state["layer_seven"] = {"active": true, "title": "Capa 07 · Aplicación", "decision": null, "fragments": 4,
		"goal": "Llega a NODO_07. No tiene armario: se llega desde cualquier terminal, hablando su protocolo.",
		"mail": {"subject": "NODO_07", "from": "nora@wired",
			"body": "Nora nunca ha podido entrar en NODO_07. Lee ~/correo/nodo07.eml en el Terminal."}}
	api.snapshot = state
	await process_frame
	await process_frame
	check("Capa 07" in presence.hud.text and "NODO_07" in presence.hud.text, "HUD does not follow Capa 07: " + presence.hud.text)
	ws.open_pc()
	mails = ""
	for node in ws.content.find_children("*", "Label", true, false):
		mails += node.text + "\n"
	check(mails.find("Nora nunca") >= 0 and mails.find("Nora nunca") < mails.find("Tres caras"), "Capa 07 mail must come first")
	ws._select("Terminal")
	terminal_text = ""
	for node in ws.content.find_children("*", "Label", true, false):
		terminal_text += node.text + "\n"
	check("Capa 07" in terminal_text and "4/7" in terminal_text, "Terminal page does not show Capa 07")
	await snap("layer07-pc")
	ws.close_pc()

	# The server can point the HUD at an open lower layer.
	state["layer_one"] = {"active": true, "title": "Capa 01 · Física", "decision": null, "fragments": 4,
		"goal": "Alguien cortó el cable del armario del aula de informática. Lee en el osciloscopio lo último que llevaba.",
		"mail": {"subject": "Parte de incidencia · enlace del pabellón B", "from": "partes@escuela.wired",
			"body": "El enlace del pabellón B lleva días mudo. Lee ~/correo/cable.eml en el Terminal."}}
	state["current_layer"] = "layer_one"
	api.snapshot = state
	await process_frame
	await process_frame
	check("Capa 01" in presence.hud.text and "osciloscopio" in presence.hud.text, "HUD does not follow current_layer: " + presence.hud.text)
	ws.open_pc()
	mails = ""
	for node in ws.content.find_children("*", "Label", true, false):
		mails += node.text + "\n"
	check(mails.find("pabellón B") > mails.find("TTL=1"), "Capa 01 mail must be listed after the other layers")
	ws.close_pc()
	current_scene = null
	scene.queue_free()
	await process_frame
	print("LAYER03_CLIENT_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
