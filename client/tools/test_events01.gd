extends SceneTree
var failed := false
var capture := ""
var views := 0

func _initialize() -> void: call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error("EVENTS01 // " + message)

func has_button(parent: Node, phrase: String) -> bool:
	for b in parent.find_children("*", "Button", true, false):
		if phrase in b.text: return true
	return false

func snap(name: String, ws: Node) -> void:
	await process_frame
	await process_frame
	var viewport := Rect2(Vector2.ZERO, root.get_visible_rect().size)
	check(viewport.encloses(ws.footer.get_global_rect()), "Footer clipped: " + name)
	check(viewport.encloses(ws.content.get_global_rect()), "Content clipped: " + name)
	views += 1
	if not capture.is_empty():
		await create_timer(0.6).timeout
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(capture.path_join(name + ".png")) == OK, "Capture failed")

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): capture = arg.trim_prefix("--capture=")
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var ws := root.get_node("Workshop")
	var fixtures: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tools/fixtures/events01.json"))
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for view in ["upcoming", "open", "playing", "ranking", "closed", "reward", "mirrored"]:
		api.snapshot = fixtures[view]
		var scene: Node3D = load(paths[api.snapshot.player.location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		var player: CharacterBody3D = scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		await process_frame
		if view in ["upcoming", "reward"]:
			ws.open_pc()
			check(has_button(ws.tabs, "Eventos"), "PC calendar missing")
			ws._select("Eventos")
			check(not has_button(ws.content, "Jugar un intento"), "Can start a run remotely")
			if view == "reward":
				check("buffer" in ws.data().modules, "Reward did not compile")
		else:
			ws.open_cafe()
			check(has_button(ws.content, "Torneos"), "Cafe tournament entry missing")
			ws._open("CAFE_EVENTS")
			if view in ["playing", "mirrored"]:
				var response: Dictionary = fixtures.run if view == "playing" else fixtures.mirrored_run
				ws.pending_endpoint = "cafe-events"
				ws._completed(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"state":api.snapshot,"result":response}).to_utf8_buffer())
				ws.event_panel.selected = response.event_id
				ws._render()
				check(ws.courier == Vector2i(int(response.board.start[0]), int(response.board.start[1])), "Wrong mirrored start")
				ws._move("D")
				ws._move("D")
				ws._move("R" if view == "playing" else "L")
				check(ws.collected.size() == 1, "Mirrored movement or pickup failed")
				var draft: String = ws.moves
				api.snapshot_updated.emit(api.snapshot)
				check(ws.moves == draft, "Polling erased the active run")
				check(ws.run_endpoint == "cafe-events", "Run points at practice endpoint")
			elif view == "closed":
				ws.event_panel.selected = "KISSA_000001"
				ws._render()
				var before: String = ws.moves
				ws._move("D")
				check(ws.moves == before, "Moves allowed after deadline")
			elif view == "ranking":
				var row: Dictionary = api.snapshot.cafe_events.events[0]
				check(row.ranking.size() == 3 and row.ranking[0].mine, "Ranking not public or wrong winner")
				ws.moves = fixtures.winning_moves
				ws.courier = Vector2i(int(ws.arcade.exit[0]), int(ws.arcade.exit[1]))
				ws.collected.clear()
				for chip in ws.arcade.chips: ws.collected.append(Vector2i(int(chip[0]), int(chip[1])))
				ws._completed(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"state":api.snapshot,"result":fixtures.result}).to_utf8_buffer())
		check(not player.is_physics_processing(), "Player moves through cafe while competing")
		await snap(view, ws)
		if view == "closed":
			var scroll: ScrollContainer = ws.content.find_children("*","ScrollContainer",true,false)[0]
			scroll.scroll_vertical = 50
			await process_frame
			var position := scroll.scroll_vertical
			api.snapshot.cafe_events.minute += 10
			api.snapshot_updated.emit(api.snapshot)
			await process_frame
			await process_frame
			check(ws.content.find_children("*","ScrollContainer",true,false)[0].scroll_vertical == position, "Live calendar reset ranking scroll")
		ws.close_pc()
		ws._completed(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"state":api.snapshot,"result":{"text":"Respuesta tardía"}}).to_utf8_buffer())
		check(not ws.is_open(), "Late response reopens terminal")
		player.set_physics_process(false)
		current_scene = null
		scene.queue_free()
		await process_frame
	print("EVENTS01_GAMEPLAY_", "FAILED" if failed else "OK", " views=", views)
	quit(1 if failed else 0)
