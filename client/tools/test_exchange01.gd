extends SceneTree
var failed := false
var views := 0
var capture := ""
func _initialize() -> void: call_deferred("run")
func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error("EXCHANGE01 // "+message)
func find_button(parent: Node, phrase: String) -> Button:
	for b in parent.find_children("*","Button",true,false):
		if phrase in b.text: return b
	return null
func snap(name: String, ws: Node) -> void:
	await process_frame
	await process_frame
	var viewport := Rect2(Vector2.ZERO,root.get_visible_rect().size)
	check(viewport.encloses(ws.footer.get_global_rect()),"Footer overflow "+name)
	check(viewport.encloses(ws.content.get_global_rect()),"Content overflow "+name)
	check(viewport.encloses(ws.tabs.get_global_rect()),"Tabs overflow "+name)
	views += 1
	if not capture.is_empty():
		await create_timer(0.5).timeout
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(capture.path_join(name+".png"))==OK,"Capture failed")
func apply(ws: Node, state: Dictionary, result: Dictionary) -> void:
	ws._completed(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"state":state,"result":result}).to_utf8_buffer())
func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): capture = arg.trim_prefix("--capture=")
	var fixtures: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tools/fixtures/exchange01.json"))
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var ws := root.get_node("Workshop")
	api.snapshot_updated.disconnect(ws._event_snapshot_changed)
	for child in ws.get_children(): child.free()
	ws.set_script(load("res://tools/offline_arcade_workshop.gd"))
	ws._ready()
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for where in ["unknown","club","cafe","missing","ready","history","blocked"]:
		api.snapshot = fixtures[where]
		var scene: Node3D = load(paths[api.snapshot.player.location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		var player: CharacterBody3D = scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		await process_frame
		if where=="club":
			var npc := scene.get_node("RYOKO")
			var found := false
			for option in npc._choices():
				if option.id=="EXCHANGE": found = true
			check(found,"Prologue choice missing")
			var chapter := root.get_node("ChapterOne")
			chapter.current_actor="RYOKO"
			chapter.normal_conversation=func(): pass
			chapter.terminal_context=false
			chapter._present({"speaker":"Ryoko","text":"¿Quieres intercambiar fragmentos?","choices":[]})
			var b := find_button(root.get_node("EventDialog").choices_box,"intercambiar código")
			check(b!=null,"Chapter dialogue choice missing")
			if b!=null: b.pressed.emit()
			check(ws.pending_endpoint=="code-exchange" and ws.pending.data.peer=="RYOKO","Wrong Ryoko endpoint")
			apply(ws,fixtures.club,fixtures.contact)
		elif where=="cafe":
			ws.open_cafe()
			var b := find_button(ws.content,"Intercambiar código")
			check(b!=null,"Cafe entry missing")
			await process_frame
			check(Rect2(Vector2.ZERO,root.get_visible_rect().size).encloses(b.get_global_rect()),"Cafe action clipped")
			b.pressed.emit()
			check(ws.pending.data.peer=="KISSA_TECH","Wrong technician")
			ws.busy=false
			ws.open_cafe()
		else:
			ws.open_pc()
			ws._select("Intercambios")
			ws.exchange_panel.show_history=where=="history"
			ws._render()
			check(not player.is_physics_processing(),"Player moves during exchange")
			if where in ["unknown","missing","blocked"]:
				check(find_button(ws.content,"Revisar intercambio")==null,"Unavailable offer can be accepted")
			if where=="ready":
				find_button(ws.content,"Revisar intercambio con Ryoko").pressed.emit()
				check(ws.dispatch_count==2,"Review unexpectedly sent a request")
				await snap("review",ws)
				find_button(ws.content,"Cancelar").pressed.emit()
				check(find_button(ws.content,"Confirmar copias")==null,"Cancel left confirmation active")
				find_button(ws.content,"Revisar intercambio con Ryoko").pressed.emit()
				find_button(ws.content,"Confirmar copias").pressed.emit()
				check(ws.pending.data.offer=="ryoko_scan_v1" and ws.pending.data.asset=="event_KISSA_000001","Incorrect selected provenance")
				var saved: Dictionary = ws.pending.duplicate(true)
				ws._completed(HTTPRequest.RESULT_CANT_CONNECT,0,PackedStringArray(),PackedByteArray())
				check(ws.retry_button.visible,"Missing retry")
				ws.retry_button.pressed.emit()
				check(ws.pending==saved and ws.pending_endpoint=="code-exchange","Retry changed request")
				apply(ws,fixtures.received,fixtures.first)
				check(find_button(ws.content,"Revisar intercambio con Ryoko")==null,"Completed exchange still available")
		await snap(where,ws)
		ws.close_pc()
		check(player.is_physics_processing(),"Player remains locked")
		scene.queue_free()
		await process_frame
	if failed: quit(1)
	else:
		print("EXCHANGE01_GAMEPLAY_OK views="+str(views)+" contacts=2 retry=stable")
		quit(0)
