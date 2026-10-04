extends SceneTree
## Uses public fixtures from an actual World Core playthrough, never port 8000.
## Optional rendered screenshots: -- --capture=C:/absolute/output-directory
var failed := false

func _initialize() -> void:
	call_deferred("run")

func check(value: bool, reason: String) -> void:
	if not value:
		failed=true
		push_error("CHAPTER01 // "+reason)

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var chapter := root.get_node("ChapterOne")
	var dialog := root.get_node("EventDialog")
	var journal := root.get_node("CharacterJournal")
	var capture := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="):
			capture=arg.trim_prefix("--capture=")
	var views: Array = JSON.parse_string(FileAccess.get_file_as_string("res://tools/fixtures/chapter01.json"))
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for view in views:
		api.snapshot=view.state
		var location: String = view.state.player.location
		var scene: Node3D = load(paths[location]).instantiate()
		root.add_child(scene)
		current_scene=scene
		var player: CharacterBody3D=scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		player.position=Vector3(view.at[0],view.at[1],view.at[2])
		player._update_camera()
		if location not in ["APARTMENT","APARTMENT_DISTRICT"]:
			player.camera.size=20
		await process_frame
		await process_frame
		await physics_frame
		check(scene.get_node_or_null("ChapterObjects")!=null,location+": missing case objects")
		for actor in ["RESIDENT_001","RESIDENT_006","PROFESSOR","RYOKO"]:
			check(chapter.can_talk(actor),"Case conversation not offered: "+actor)
		for actor in ["AGENT_K","AGENT_NORA","RESIDENT_002"]:
			check(not chapter.can_talk(actor),"Unrelated NPC conversation hijacked: "+actor)
		var target := ""
		if view.name=="school-sheet": target="CLOSURE_SHEET"
		if view.name=="school-clock": target="SCHOOL_CLOCK"
		if view.name=="computer": target="SCHOOL_PC"
		if not target.is_empty():
			var item: Node3D=scene.get_node("ChapterObjects/"+target)
			check(item.is_in_group("interactable"),target+": missing interaction")
			check(player.global_position.distance_to(item.global_position)<player.interaction_distance,target+": out of reach")
			var query := PhysicsShapeQueryParameters3D.new()
			var shape := CapsuleShape3D.new()
			shape.radius=.22
			shape.height=1.55
			query.shape=shape
			query.transform=Transform3D(Basis.IDENTITY,player.global_position)
			query.exclude=[player.get_rid()]
			check(scene.get_world_3d().direct_space_state.intersect_shape(query).is_empty(),target+": approach intersects scenery")
			# The same nearest-object rule used by E must select this object.
			var nearest: Node3D=null
			var distance: float=player.interaction_distance
			for other in get_nodes_in_group("interactable"):
				if other is Node3D and other.has_method("interact"):
					var d: float=player.global_position.distance_to(other.global_position)
					if d<distance:
						distance=d
						nearest=other
			check(nearest==item,target+": another interaction steals E")
		if view.name=="return-to-school":
			check(scene.get_node("ChapterObjects/CaseEnvelope").visible,"Return visit has no new envelope")
		if view.mode in ["dialogue","terminal"]:
			chapter.terminal_context=view.mode=="terminal"
			chapter.normal_conversation=Callable(self,"noop") if view.name in ["haruto","aiko","ryoko","decision"] else Callable()
			chapter._present(view.result)
			await process_frame
			await process_frame
			check(dialog.visible,"Dialogue did not open")
			check(not player.is_physics_processing(),"Player moves during dialogue")
			check(dialog.choices_box.get_child_count()>=1,"No way to leave the investigation")
			for button in dialog.choices_box.get_children():
				var rect: Rect2=button.get_global_rect()
				check(Rect2(Vector2.ZERO,root.get_visible_rect().size).encloses(rect),view.name+": option clipped: "+button.text)
		elif view.mode=="journal":
			journal.open_journal()
			journal._choose_view("CHAPTER","")
			await process_frame
			await process_frame
			check(journal.chapter_controls.visible,"Clue linking controls missing")
			for text in ["TESTIMONIO","OBSERVACIÓN PROPIA","DOCUMENTO","Fecha que la fuente atribuye","SIN VERIFICAR"]:
				check(text in journal.details.text,"Journal lost provenance: "+text)
			check(journal.first_clue.item_count==view.state.chapter_one.evidence.size(),"Clue choices incomplete")
			check(journal.hypothesis.text==view.state.chapter_one.hypothesis,"Saved hypothesis missing")
			journal.details.get_v_scroll_bar().value=100
			api.snapshot_updated.emit(api.snapshot)
			await process_frame
			check(journal.details.get_v_scroll_bar().value>90,"Polling scrolls archive back to the start")
			journal.details.get_v_scroll_bar().value=0
			check(Rect2(Vector2.ZERO,root.get_visible_rect().size).encloses(journal.chapter_controls.get_global_rect()),"Journal editor outside viewport")
		chapter.toast.hide()
		if not capture.is_empty():
			await create_timer(2.5).timeout
			await RenderingServer.frame_post_draw
			check(root.get_texture().get_image().save_png(capture.path_join(str(view.name)+".png"))==OK,"Capture failed")
		if journal.backdrop.visible:
			journal.close_journal()
			check(player.is_physics_processing(),"Journal leaves player locked")
		if dialog.visible:
			dialog.close_event()
			check(player.is_physics_processing(),"Dialogue leaves player locked")
			chapter._completed(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"result":view.result,"state":view.state}).to_utf8_buffer())
			check(not dialog.visible,"Late reply reopened a closed dialogue")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		current_scene=null
		scene.queue_free()
		await process_frame
	api.snapshot={"chapter_one":{"active":false}}
	check(not chapter.can_talk("PROFESSOR"),"Offline prologue intercepted")
	print("CHAPTER01_GAMEPLAY_","FAILED" if failed else "OK"," views=",views.size())
	quit(1 if failed else 0)

func noop() -> void:
	pass
