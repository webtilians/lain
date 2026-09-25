extends SceneTree
var failed := false
var capture := ""
func _initialize() -> void:
	call_deferred("run")
func check(ok: bool, reason: String) -> void:
	if not ok:
		failed = true
		push_error("WORKSHOP01 // " + reason)
func snap(name: String) -> void:
	await process_frame
	await process_frame
	if not capture.is_empty():
		await create_timer(1.0).timeout
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(capture.path_join(name+".png")) == OK, "Capture failed")
func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): capture = arg.trim_prefix("--capture=")
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var ws := root.get_node("Workshop")
	var fixtures: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tools/fixtures/workshop01.json"))
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for where in ["home","cafe","lab"]:
		api.snapshot = fixtures[where]
		var scene: Node3D = load(paths[api.snapshot.player.location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		var player: CharacterBody3D = scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		await process_frame
		await process_frame
		await physics_frame
		if where == "home":
			ws.open_pc()
			check(not player.is_physics_processing(), "PC does not lock movement")
			ws.frames = fixtures.life.frames
			for page in ["Correo","Código","Juego de la Vida","Dispositivos","Wired"]:
				ws._select(page)
				await snap("workshop-"+str(["Correo","Código","Juego de la Vida","Dispositivos","Wired"].find(page)))
				check(Rect2(Vector2.ZERO,root.get_visible_rect().size).encloses(ws.footer.get_global_rect()), "Footer clipped: "+page)
				check(Rect2(Vector2.ZERO,root.get_visible_rect().size).encloses(ws.content.get_global_rect()), "Page overflow: "+page)
			ws._select("Código")
			var editor: CodeEdit = ws.content.find_children("*","CodeEdit",true,false)[0]
			editor.text += 'use("shield")' + "\n"
			await process_frame
			check('use("shield")' in ws.program_draft, "Editor does not preserve draft")
			ws._select("Correo")
			ws._select("Código")
			check(ws.content.find_children("*","CodeEdit",true,false)[0].text == ws.program_draft, "Switching tabs loses draft")
			ws.close_pc()
			ws._completed(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"state":fixtures.home,"result":fixtures.life}).to_utf8_buffer())
			check(not ws.is_open(), "Late response reopens closed PC")
		elif where == "cafe":
			var item: Node3D = scene.get_node("WorkshopObjects/CafeTerminal")
			player.position = Vector3(3.1,.91,-.5)
			var query := PhysicsShapeQueryParameters3D.new()
			var capsule := CapsuleShape3D.new()
			capsule.radius = .35
			capsule.height = 1.8
			query.shape = capsule
			query.transform = Transform3D(Basis.IDENTITY,player.position)
			query.exclude = [player.get_rid()]
			check(scene.get_world_3d().direct_space_state.intersect_shape(query).is_empty(), "Café terminal approach blocked")
			var nearest: Node3D = null
			var distance: float = player.interaction_distance
			for other in get_nodes_in_group("interactable"):
				if other is Node3D and other.has_method("interact"):
					var d: float = player.position.distance_to(other.global_position)
					if d < distance:
						nearest = other
						distance = d
			check(nearest == item, "E cannot select café terminal")
			player._update_camera()
			await snap("cafe-terminal")
			ws.open_cafe()
			ws.arcade = fixtures.arcade.board
			ws.run_id = fixtures.arcade.run_id
			ws._render()
			ws._move("D")
			ws._move("D")
			ws._move("R")
			check(ws.collected.size() == 1 and ws.moves == "DDR", "Arcade movement/collection")
			await snap("bit-courier")
			check(Rect2(Vector2.ZERO,root.get_visible_rect().size).encloses(ws.footer.get_global_rect()), "Arcade footer clipped")
			ws.close_pc()
		else:
			var chapter := root.get_node("ChapterOne")
			chapter.normal_conversation = func(): pass
			chapter.current_actor = "PROFESSOR"
			chapter.terminal_context = false
			chapter._present({"speaker":"Profesor","text":"El aula está abierta.","choices":[]})
			var lesson_found := false
			for b in root.get_node("EventDialog").choices_box.get_children():
				if "Juego de la Vida" in b.text: lesson_found = true
			check(lesson_found, "Professor lesson not reachable")
			root.get_node("EventDialog").close_event()
			root.get_node("NetworkConflict")._present(fixtures.protection)
			await snap("program-shield")
			root.get_node("EventDialog").close_event()
		player.set_physics_process(false)
		current_scene = null
		scene.queue_free()
		await process_frame
	print("WORKSHOP01_GAMEPLAY_", "FAILED" if failed else "OK", " pages=5 locations=3")
	quit(1 if failed else 0)
