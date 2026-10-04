extends SceneTree
var failed := false
var capture := ""
var views := 0
func _initialize() -> void: call_deferred("run")
func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error("CIRCLES01 // "+message)
func snap(name: String) -> void:
	await process_frame
	await process_frame
	views += 1
	if not capture.is_empty():
		await create_timer(1.0).timeout
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(capture.path_join(name+".png"))==OK,"Capture failed")
func has_button(parent: Node, phrase: String) -> bool:
	for button in parent.find_children("*","Button",true,false):
		if phrase in button.text: return true
	return false
func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): capture = arg.trim_prefix("--capture=")
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var ws := root.get_node("Workshop")
	var chapter := root.get_node("ChapterOne")
	var dialog := root.get_node("EventDialog")
	var fixtures: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tools/fixtures/circles01.json"))
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for where in ["empty","club","cafe","active","lab","wired","removed"]:
		api.snapshot = fixtures[where]
		var scene: Node3D = load(paths[api.snapshot.player.location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		var player: CharacterBody3D = scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		await process_frame
		await process_frame
		if where == "club":
			var npc := scene.get_node("RYOKO")
			check(npc.is_in_group("interactable"),"Ryoko not interactable")
			var has_circle := false
			for option in npc._choices():
				if option.id=="CIRCLE": has_circle = true
			check(has_circle,"Prologue path lacks circle conversation")
			chapter.current_actor = "RYOKO"
			chapter.normal_conversation = func(): pass
			chapter.terminal_context = false
			chapter._present({"speaker":"Ryoko","text":"¿Sigues buscando una entrada?","choices":[]})
			check(has_button(dialog.choices_box,"red propia"),"Chapter path lacks circle conversation")
			await snap("ryoko-invitation")
			dialog.close_event()
			ws._open("CIRCLE_CONTACT")
			ws._completed(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"state":fixtures.club,"result":fixtures.contact}).to_utf8_buffer())
			check("Juego de la Vida" in ws.content.get_child(1).text,"Contact conditions missing")
			await snap("ryoko-conditions")
		elif where=="cafe":
			ws.open_cafe()
			check(has_button(ws.content,"red propia"),"Cafe contact not reachable")
			await snap("cafe-contact")
		elif where=="lab":
			root.get_node("NetworkConflict")._present(fixtures.defense)
			check("Defensa preparada" in dialog.body_label.text,"Shared program cannot prepare defense")
			await snap("shared-defense")
			dialog.close_event()
		else:
			ws.open_pc()
			check(has_button(ws.tabs,"Círculo"),"Circle tab missing")
			ws._select("Wired" if where=="wired" else "Círculo")
			check(not player.is_physics_processing(),"Player can move while using PC")
			if where=="empty":
				check(has_button(ws.content,"Crear círculo"),"Cannot create circle")
				var entry: LineEdit = ws.content.find_children("CircleName","LineEdit",true,false)[0]
				entry.text = "Texto sin guardar"
				entry.text_changed.emit(entry.text)
				ws._select("Correo")
				ws._select("Círculo")
				check(ws.content.find_children("CircleName","LineEdit",true,false)[0].text=="Texto sin guardar","Name draft lost")
				await snap("circle-create")
			elif where=="active":
				for page in ["Grupo","Aportaciones","Programa","Historial"]:
					ws.circle_tab = page
					ws._render()
					await snap("circle-"+page)
					if page=="Programa":
						var editor: CodeEdit = ws.content.find_children("CircleEditor","CodeEdit",true,false)[0]
						editor.set_caret_line(editor.get_line_count()-1)
						editor.insert_text_at_caret("# borrador local\n")
						await process_frame
						ws._select("Código")
						ws._select("Círculo")
						check("# borrador local" in ws.content.find_children("CircleEditor","CodeEdit",true,false)[0].text,"Shared draft lost")
						check(not "# borrador local" in ws.program_draft,"Shared draft overwrote personal program")
						for button in ws.content.find_children("*","Button",true,false):
							if button.text=="Insertar Enrutamiento": button.pressed.emit()
						ws._select("Correo")
						ws._select("Círculo")
						check(ws.circle_draft.count('use("routing")')==2,"Inserted module lost when switching tabs")
					var viewport := Rect2(Vector2.ZERO,root.get_visible_rect().size)
					check(viewport.encloses(ws.footer.get_global_rect()),"Footer clipped: "+page)
					check(viewport.encloses(ws.content.get_global_rect()),"Panel overflow: "+page)
			elif where=="wired":
				var found := false
				for b in ws.content.find_children("*","Button",true,false):
					if b.text=="Ejecutar Exploración" and not b.disabled: found = true
				check(found,"Shared scan is disabled in PC")
				await snap("shared-wired")
			else:
				check(api.snapshot.workshop.shared_modules.is_empty(),"Withdrawn program still active")
				ws.circle_tab = "Grupo"
				ws._render()
				check("Sin programa activo" in ws.content.get_child(2).text,"Stopped program not visible")
				await snap("circle-withdrawal")
		if ws.is_open():
			ws.close_pc()
			ws._completed(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"state":fixtures[where],"result":{"text":"Respuesta tardía"}}).to_utf8_buffer())
			check(not ws.is_open(),"Late response reopens closed circle")
		player.set_physics_process(false)
		current_scene = null
		scene.queue_free()
		await process_frame
	print("CIRCLES01_GAMEPLAY_","FAILED" if failed else "OK"," views=",views)
	quit(1 if failed else 0)
