extends SceneTree
## Exercises physical access, separate identities and simultaneous threats.
var failed := false
var capture := ""
func _initialize() -> void:
	call_deferred("run")
func check(ok: bool, reason: String) -> void:
	if not ok:
		failed = true
		push_error("NOEMA01 // " + reason)
func approach(scene: Node3D, player: CharacterBody3D, item: Node3D) -> void:
	player.position = item.global_position + Vector3(0,0,1.3)
	player.position.y = .91
	var query := PhysicsShapeQueryParameters3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = .35
	capsule.height = 1.8
	query.shape = capsule
	query.transform = Transform3D(Basis.IDENTITY,player.position)
	query.exclude = [player.get_rid()]
	var hits := scene.get_world_3d().direct_space_state.intersect_shape(query)
	var blockers := ""
	for hit in hits: blockers += " " + str(hit.collider.get_path())
	check(hits.is_empty(), str(scene.name)+": blocked approach "+str(item.name)+blockers)
	var nearest: Node3D = null
	var distance: float = player.interaction_distance
	for other in get_nodes_in_group("interactable"):
		if other is Node3D and other.has_method("interact"):
			var d: float = player.position.distance_to(other.global_position)
			if d < distance:
				distance = d
				nearest = other
	check(nearest == item, str(scene.name)+": E cannot select "+str(item.name))
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
	var controller := root.get_node("NetworkConflict")
	var journal := root.get_node("CharacterJournal")
	var dialog := root.get_node("EventDialog")
	var workshop := root.get_node("Workshop")
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	var views: Array = JSON.parse_string(FileAccess.get_file_as_string("res://tools/fixtures/noema01.json"))
	for view in views:
		api.snapshot = view.state
		var scene: Node3D = load(paths[api.snapshot.player.location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		var player: CharacterBody3D = scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		await process_frame
		await process_frame
		await physics_frame
		if view.mode != "pc":
			var objects: Node3D = scene.get_node("ConflictObjects")
			for anchor_name in ["RelayCabinet","Maintenance","RecordsStaff"]:
				approach(scene,player,objects.get_node(anchor_name))
			check(objects.get_node("RecordsStaff").faction == "NOEMA", "Wrong records interaction faction")
			check(objects.get_node("Maintenance").faction == "KAGAMI", "Wrong maintenance faction")
			var record: Dictionary = {}
			var lines: Dictionary = {}
			for person in api.snapshot.network_conflict.visible_personnel:
				if person.slot == "RECORDS": record = person
				else: lines = person
			await process_frame
			check(str(record.name) in objects.archivist_label.text, "Records caption overwritten")
			check(str(lines.name) in objects.operative_label.text, "Maintenance caption overwritten")
			if view.mode == "physical":
				check(not "NOEMA" in objects.archivist_label.text, "Cover leaks faction")
			elif view.mode == "exposed":
				check("NOEMA" in objects.archivist_label.text, "Verified affiliation missing")
				check(api.snapshot.network_conflict.pending.size() == 1, "Other corporation order lost")
			player._update_camera()
			player.camera.size = 18
		if view.mode in ["cabinet","dialogue","exposed"]:
			controller._present(view.result)
			if view.mode == "cabinet":
				var targets: Array = []
				for choice in controller.options.values():
					if choice.action == "CLAIM": targets.append(choice.get("faction","KAGAMI"))
				check("NOEMA" in targets and "KAGAMI" in targets, "Cabinet cannot select both corporations")
		elif view.mode == "journal":
			journal.open_journal()
			journal._choose_view("NETWORK","")
			check("NOEMA" in journal.details.text and "KAGAMI" in journal.details.text, "Separate operator names missing")
			check("Reescritura" in journal.details.text and "Intervención técnica" in journal.details.text, "Attack methods missing")
			check("2 ORDEN" in controller.warning.text, "HUD ignores concurrent orders")
		elif view.mode == "pc":
			workshop.open_pc()
			workshop._select("Wired")
			var all_text := ""
			for label in workshop.content.find_children("*","RichTextLabel",true,false):
				all_text += label.text
			for label in workshop.content.find_children("*","Label",true,false):
				all_text += label.text
			check("NOEMA" in all_text and "KAGAMI" in all_text, "Workshop lost controller breakdown")
		await snap(view.name)
		if dialog.visible:
			var viewport := Rect2(Vector2.ZERO,root.get_visible_rect().size)
			check(viewport.encloses(dialog.body_label.get_global_rect()), "Clipped dialogue text: "+str(view.name))
			for button in dialog.choices_box.get_children():
				dialog.choices_scroll.ensure_control_visible(button)
				await process_frame
				await process_frame
				check(viewport.encloses(button.get_global_rect()), "Clipped dialogue choice")
				check(dialog.choices_scroll.get_global_rect().encloses(button.get_global_rect()), "Choice cannot scroll into view")
			dialog.close_event()
		if journal.backdrop.visible: journal.close_journal()
		if workshop.is_open(): workshop.close_pc()
		player.set_physics_process(false)
		current_scene = null
		scene.queue_free()
		await process_frame
	print("NOEMA01_GAMEPLAY_", "FAILED" if failed else "OK", " views=",views.size()," locations=4")
	quit(1 if failed else 0)
