extends SceneTree
var failed := false
var capture := ""
var views := 0
var steps := 0

func _initialize() -> void: call_deferred("run")
func check(ok: bool, text: String) -> void:
	if not ok:
		failed = true
		push_error("ARCADE01 // " + text)

func snap(name: String, ws: Node) -> void:
	await process_frame
	await process_frame
	var viewport := Rect2(Vector2.ZERO,root.get_visible_rect().size)
	check(viewport.encloses(ws.footer.get_global_rect()),"Footer overflow: " + name)
	check(viewport.encloses(ws.content.get_global_rect()),"Panel overflow: " + name)
	views += 1
	if not capture.is_empty():
		await create_timer(0.7).timeout
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(capture.path_join(name + ".png")) == OK,"Capture failed")

func apply(ws: Node, state: Dictionary, result: Dictionary) -> void:
	ws._completed(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"state":state,"result":result}).to_utf8_buffer())

func model_matches(model: RefCounted, expected: Dictionary) -> void:
	check(model.collected == int(expected.collected),"Pickup count diverged")
	check(model.finished == bool(expected.finished),"Finish state diverged")
	check(model.collision == bool(expected.collision),"Collision diverged")
	check(model.food_index == int(expected.food_index),"Food cursor diverged")
	check(model.food == Vector2i(int(expected.food[0]),int(expected.food[1])),"Food placement diverged")
	var body: Array[Vector2i] = []
	for p in expected.snake: body.append(Vector2i(int(p[0]),int(p[1])))
	check(model.body == body,"Body or departing tail diverged")
	steps += 1

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): capture = arg.trim_prefix("--capture=")
	var fixtures: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tools/fixtures/arcade01.json"))
	var model = load("res://scripts/ui/SignalSnake.gd").new()
	for trace in fixtures.traces:
		model.reset(trace.board)
		model_matches(model,trace.states[0])
		for i in trace.moves.length():
			model.step(trace.moves[i])
			model_matches(model,trace.states[i+1])
	model.reset(fixtures.practice_run.board)
	model.turn("L")
	check(model.next_direction=="R","Input permits reversing into the neck")
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var ws := root.get_node("Workshop")
	api.snapshot_updated.disconnect(ws._event_snapshot_changed)
	for child in ws.get_children(): child.free()
	ws.set_script(load("res://tools/offline_arcade_workshop.gd"))
	ws._ready()
	ws.snake_autoplay = false
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for where in ["calendar","practice","event","closed"]:
		api.snapshot = fixtures[where]
		var scene: Node3D = load(paths[api.snapshot.player.location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		var player: CharacterBody3D = scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		await process_frame
		if where=="calendar":
			ws.open_pc()
			ws._select("Eventos")
			ws.event_panel.selected="KISSA_000002"
			ws._render()
		else:
			ws.open_cafe()
			var practice_available := false
			for b in ws.content.find_children("*","Button",true,false):
				if b.text=="Practicar Serpiente": practice_available = true
			check(practice_available,"Snake practice entry missing")
			if where=="practice":
				ws.pending_endpoint="workshop"
				apply(ws,fixtures.practice,fixtures.practice_run)
			else:
				ws._open("CAFE_EVENTS")
				ws.event_panel.selected="KISSA_000002"
				ws._render()
				if where=="event":
					ws.pending_endpoint="cafe-events"
					apply(ws,fixtures.event,fixtures.event_run)
			if where in ["practice","event"]:
				var prior := int(ws.dispatch_count)
				for direction in "RRRRRDD":
					ws._move(direction)
					ws._snake_step()
				check(ws.snake_model.collected==3,"Live controls cannot collect signals")
				var before: String = ws.moves
				api.snapshot_updated.emit(api.snapshot)
				check(ws.moves==before,"Polling erased the live snake")
				await snap(where+"-playing",ws)
				ws.close_pc()
				ws.snake_autoplay=true
				ws._process(1.0)
				check(ws.moves==before,"Closed terminal advanced snake")
				ws.snake_autoplay=false
				ws._open("CAFE" if where=="practice" else "CAFE_EVENTS")
				for direction in "DLLDLLDL":
					ws._move(direction)
					ws._snake_step()
				check(ws.dispatch_count==prior+1,"Completion must submit exactly once")
				check(ws.pending.data.moves=="RRRRRDDDLLDLLDL","Wrong replay sent")
				check(ws.pending_endpoint==("workshop" if where=="practice" else "cafe-events"),"Practice and event endpoints mixed")
				var after := int(ws.dispatch_count)
				ws._snake_step()
				check(ws.dispatch_count==after,"Finished run submitted again")
				if where=="event":
					var original: Dictionary = ws.pending.duplicate(true)
					ws._completed(HTTPRequest.RESULT_CANT_CONNECT,0,PackedStringArray(),PackedByteArray())
					api.snapshot.cafe_events.minute += 10
					api.snapshot_updated.emit(api.snapshot)
					await process_frame
					check(ws.retry_button.visible,"Polling removed the lost-response retry")
					ws.retry_button.pressed.emit()
					check(ws.pending==original and ws.pending_endpoint=="cafe-events","Retry changed the request or endpoint")
					check(ws.dispatch_count==after+1,"Retry was not dispatched")
				apply(ws,fixtures.practice_won if where=="practice" else fixtures.closed,fixtures.practice_result if where=="practice" else fixtures.event_result)
			elif where=="closed":
				var before: String = ws.moves
				ws._snake_step()
				check(ws.moves==before,"Closed event accepts moves")
		await snap(where,ws)
		check(not player.is_physics_processing(),"PC does not block player movement")
		ws.close_pc()
		player.set_physics_process(false)
		current_scene=null
		scene.queue_free()
		await process_frame
	print("ARCADE01_GAMEPLAY_", "FAILED" if failed else "OK", " views=",views," rule_steps=",steps)
	quit(1 if failed else 0)
