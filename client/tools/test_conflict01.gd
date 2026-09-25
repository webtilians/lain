extends SceneTree
## Physical and UI validation on public server-produced synthetic snapshots.
var failed := false
func _initialize() -> void:
	call_deferred("run")
func check(ok: bool, reason: String) -> void:
	if not ok:
		failed=true
		push_error("CONFLICT01 // "+reason)

func run() -> void:
	var api:=root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var controller:=root.get_node("NetworkConflict")
	var dialog:=root.get_node("EventDialog")
	var journal:=root.get_node("CharacterJournal")
	var paths: Dictionary=load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	var views: Array=JSON.parse_string(FileAccess.get_file_as_string("res://tools/fixtures/conflict01.json"))
	var capture:=""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): capture=arg.trim_prefix("--capture=")
	for view in views:
		api.snapshot=view.state
		var location: String=view.state.player.location
		var scene: Node3D=load(paths[location]).instantiate()
		root.add_child(scene)
		current_scene=scene
		var player: CharacterBody3D=scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		await process_frame
		await process_frame
		await physics_frame
		var objects: Node3D=scene.get_node("ConflictObjects")
		if location!="APARTMENT":
			for anchor_name in ["RelayCabinet","Maintenance"]:
				var item: Node3D=objects.get_node(anchor_name)
				player.position=item.global_position+Vector3(0,0,1.3)
				player.position.y=.91
				check(player.position.distance_to(item.global_position)<player.interaction_distance,location+": object out of reach")
				var query:=PhysicsShapeQueryParameters3D.new()
				var capsule:=CapsuleShape3D.new()
				capsule.radius=.35
				capsule.height=1.8
				query.shape=capsule
				query.transform=Transform3D(Basis.IDENTITY,player.position)
				query.exclude=[player.get_rid()]
				var hits:=scene.get_world_3d().direct_space_state.intersect_shape(query)
				var blockers:=""
				for hit in hits: blockers+=" "+str(hit.collider.get_path())
				check(hits.is_empty(),location+": blocked approach to "+anchor_name+blockers)
				var nearest: Node3D=null
				var distance: float=player.interaction_distance
				for other in get_nodes_in_group("interactable"):
					if other is Node3D and other.has_method("interact"):
						var d: float=player.position.distance_to(other.global_position)
						if d<distance:
							distance=d
							nearest=other
				check(nearest==item,location+": E selects another object near "+anchor_name)
			var focus: Node3D=objects.get_node("Maintenance" if view.mode=="personnel" else "RelayCabinet")
			player.position=focus.position+Vector3(0,0,1.3)
			player.position.y=.91
		player._update_camera()
		player.camera.size=18
		if view.mode in ["dialogue","personnel"]:
			controller._present(view.result)
		elif view.mode=="home":
			controller.open_terminal()
		elif view.mode=="journal":
			journal.open_journal()
			journal._choose_view("NETWORK","")
			check("INTERVENCIONES" in journal.details.text,"Journal missing countdown")
			check("CONTRATO DE CESIÓN" in journal.details.text,"Journal missing provenance report")
			check(not journal.chapter_controls.visible,"Chapter hypothesis controls leak into network view")
		await process_frame
		await process_frame
		if dialog.visible:
			check(not player.is_physics_processing(),"Player moves while interacting")
			for button in dialog.choices_box.get_children():
				check(Rect2(Vector2.ZERO,root.get_visible_rect().size).encloses(button.get_global_rect()),view.name+": clipped button "+button.text)
		if not capture.is_empty():
			await create_timer(2.5).timeout
			await RenderingServer.frame_post_draw
			check(root.get_texture().get_image().save_png(capture.path_join(str(view.name)+".png"))==OK,"Capture failed")
		if journal.backdrop.visible: journal.close_journal()
		if dialog.visible:
			dialog.close_event()
			controller._completed(HTTPRequest.RESULT_SUCCESS,200,PackedStringArray(),JSON.stringify({"state":view.state,"result":view.result}).to_utf8_buffer())
			check(not dialog.visible,"Late response reopened a closed dialogue")
		player.set_physics_process(false)
		current_scene=null
		scene.queue_free()
		await process_frame
	print("CONFLICT01_GAMEPLAY_","FAILED" if failed else "OK"," views=",views.size())
	quit(1 if failed else 0)
