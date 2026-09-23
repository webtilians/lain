extends SceneTree
## Offline scene/terminal smoke. No API calls and no world.db modification.
var failed := false

func _initialize() -> void:
	call_deferred("_run")

func check(condition: bool, reason: String) -> void:
	if not condition:
		failed = true
		push_error("PROLOGUE01_VISUAL // " + reason)

func _run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	var scenes := {
		"SCHOOL": "res://scenes/prologue/School.tscn",
		"SCHOOL_LAB": "res://scenes/prologue/ComputerLab.tscn",
		"NIGHTCLUB": "res://scenes/prologue/Nightclub.tscn",
	}
	for location in scenes:
		api.snapshot = {
			"minute": 0,
			"player": {"id": "PLAYER_1", "location": location, "energy": 1.0},
			"prologue": {"enabled": true, "stage": "FIND_TEACHER",
				"hint": "Encuentra el aula de informatica."},
			"visible_actors": [],
			"known_nodes": [],
		}
		var scene: Node3D = load(scenes[location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		await process_frame
		var player := scene.get_node_or_null("Player") as CharacterBody3D
		check(player != null, location + ": no player")
		if player != null:
			player.set_physics_process(false)
			player.set_process_unhandled_input(false)
		var exits := 0
		var encounters := 0
		for child in scene.get_children():
			if child.name.begins_with("Door_"):
				exits += 1
				check(child.is_in_group("interactable"),
					location + ": exit not interactive")
			if child.name == "PROFESSOR" or child.name == "RYOKO":
				encounters += 1
				check(child.is_in_group("interactable"),
					location + ": NPC cannot be interacted with")
		check(exits > 0, location + ": no valid exit")
		if location == "SCHOOL_LAB" or location == "NIGHTCLUB":
			check(encounters == 1, location + ": expected one authored NPC")
			var actor_id := "PROFESSOR" if location == "SCHOOL_LAB" else "RYOKO"
			var actor = scene.get_node(actor_id)
			# Simulate a returned INTRO without connecting to the API:
			# approaching the NPC must present questions, not a final clue.
			actor.waiting = true
			actor._on_dialogue(actor_id, {
				"speaker": actor_id,
				"text": "Todavía no has preguntado nada.",
				"stage": "FIND_TEACHER",
			})
			var event_dialog = root.get_node("EventDialog")
			check(event_dialog.choices_box.visible,
				location + ": conversation has no player choices")
			var question_buttons := 0
			for widget in event_dialog.choices_box.get_children():
				if widget is Button:
					question_buttons += 1
					check("telnet" not in widget.text.to_lower(),
						location + ": dialogue choices spoil the protocol")
			check(question_buttons >= 4,
				location + ": NPC only gives an automatic one-line response")
			event_dialog.close_event()
		else:
			check(encounters == 0, "school corridor must not have Ryoko")
		check(scene.get_node_or_null("HUD/Hint") != null,
			location + ": missing readable route guidance")
		current_scene = null
		scene.queue_free()
		await process_frame

	api.snapshot["player"]["location"] = "APARTMENT_DISTRICT"
	var district := load(
		"res://scenes/apartment_district/ApartmentDistrict.tscn"
	).instantiate() as Node3D
	root.add_child(district)
	current_scene = district
	await process_frame
	var entrances: Node3D = district.get_node("PrologueEntrances")
	var school_door: Node3D = entrances.get_node("Entrance_SCHOOL")
	var club_door: Node3D = entrances.get_node("Entrance_NIGHTCLUB")
	check(school_door.is_in_group("interactable"),
		"The school building does not have a physical entrance")
	check(club_door.is_in_group("interactable"),
		"The nightclub building does not have a physical entrance")
	check(school_door.global_position.distance_to(
		club_door.global_position) > 30.0,
		"School and nightclub are still adjacent in the old street")
	check(school_door.global_position.x < -9.0
		and club_door.global_position.x > 9.0,
		"School and nightclub are not on opposing neighborhood blocks")
	var ground: CSGBox3D = district.get_node("Ground")
	check(ground.size.z > 65.0 and ground.size.x > 30.0,
		"The district has not been expanded beyond the old corridor")
	check(entrances.get_node_or_null("MidtownSquare") != null,
		"Neighborhood square missing")
	check(entrances.get_node_or_null("Cabina_Telefonica") != null,
		"Neighborhood has no secondary landmark")
	var previous: String = "NIGHTCLUB"
	root.get_node("SceneRouter").entry_from_location = previous
	current_scene = null
	district.queue_free()
	await process_frame
	var returned := load(
		"res://scenes/apartment_district/ApartmentDistrict.tscn"
	).instantiate() as Node3D
	root.add_child(returned)
	current_scene = returned
	await process_frame
	var returned_player: CharacterBody3D = returned.get_node("Player")
	check(returned_player.position.z < -48.0
		and returned_player.position.x > 7.0,
		"Returning from the club incorrectly respawns at the apartment")
	current_scene = null
	returned.queue_free()
	await process_frame

	var terminal = root.get_node("PrologueTerminal")
	api.snapshot["prologue"] = {"enabled": true, "stage": "FIND_TERMINAL"}
	terminal.open_terminal()
	check(terminal.surface.visible, "DOS terminal does not open")
	check("LAIN-DOS" in terminal.transcript.text, "DOS prompt is missing")
	terminal._on_command("help")
	check("telnet" not in terminal.transcript.text.to_lower(),
		"Terminal must not spoil the connection protocol")
	check("internet" not in terminal.transcript.text.to_lower(),
		"Terminal must not instruct external research")
	terminal.close_terminal()
	check(not terminal.surface.visible, "Terminal cannot close")
	print("PROLOGUE01_VISUAL_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
