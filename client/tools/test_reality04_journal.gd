extends SceneTree
## Offline UI/gameplay regression: never contacts server or world.db.
## godot --headless --path client --script res://tools/test_reality04_journal.gd
var failed := false


func _initialize() -> void:
	call_deferred("_run")


func check(condition: bool, reason: String) -> void:
	if not condition:
		failed = true
		push_error("REALITY04_JOURNAL // " + reason)


func _run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	api.snapshot = {
		"minute": 10,
		"player": {
			"id": "PLAYER_1", "location": "STATION", "energy": 0.8,
		},
		"known_nodes": [],
		"visible_actors": [{"id": "ENTITY_JOURNAL", "name": "Node 07 Inquiry"}],
		"character_sheets": {
			"player": {
				"id": "PLAYER_1", "name": "Player", "kind": "PLAYER",
				"faction": "UNALIGNED", "location": "STATION",
				"energy": 0.8, "known_nodes": 1, "case_status": "TRACE_FOUND",
			},
			"visible_npcs": [{
				"id": "ENTITY_JOURNAL", "name": "Node 07 Inquiry",
				"role_label": "Investigador", "focus": "Contrasta testimonios.",
				"observed_location": "STATION",
				"role_assignment": "ORIGIN_PROVISIONAL",
			}],
		},
		"station_case": {
			"id": "STATION_ECHO_07", "title": "El pulso ausente",
			"status": "TRACE_FOUND", "witness_count": 0,
			"summary": "Has encontrado un pulso ausente.",
			"responses": [],
		},
	}
	var scene: Node3D = load("res://scenes/station/Station.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	var player: CharacterBody3D = scene.get_node("Player")
	player.set_physics_process(false)
	player.set_process_unhandled_input(false)
	await process_frame

	var journal = root.get_node("CharacterJournal")
	journal.open_journal()
	check(journal.backdrop.visible, "J does not open the dossier")
	check("ENERGÍA" in journal.details.text, "Player sheet is missing")
	journal._choose_view("NPC", "ENTITY_JOURNAL")
	check("Investigador" in journal.details.text, "NPC origin role not rendered")
	check("Node 07 Inquiry" in journal.details.text, "NPC identity changed")
	journal._choose_view("CASE", "")
	check("pulso ausente" in journal.details.text.to_lower(),
		"Station case not visible")
	journal.close_journal()
	check(not journal.backdrop.visible, "Journal did not close")

	var source: StaticBody3D = scene.get_node("SignalSource")
	source.interact()
	var choices: VBoxContainer = root.get_node("EventDialog").choices_box
	var labels: Array[String] = []
	for child in choices.get_children():
		if child is Button:
			labels.append(child.text)
	var share_found: bool = false
	var archive_found: bool = false
	for label_text in labels:
		if "Difundir" in label_text:
			share_found = true
		if "Archivar" in label_text:
			archive_found = true
	check(share_found, "Direct investigation did not unlock the share choice")
	check(archive_found, "Direct investigation did not unlock the archive choice")
	root.get_node("EventDialog").close_event()

	api.snapshot["station_case"] = {
		"id": "STATION_ECHO_07", "title": "El pulso ausente",
		"status": "RESOLVED", "resolution": "BROADCAST_TRACE",
		"witness_count": 1, "summary": "Has compartido el rastro.",
		"responses": [{
			"actor_id": "ENTITY_JOURNAL", "name": "Node 07 Inquiry",
			"reaction": "Prepara preguntas para contrastar las versiones.",
		}],
	}
	api.snapshot_updated.emit(api.snapshot)
	journal.open_journal()
	journal._choose_view("CASE", "")
	check("Node 07 Inquiry" in journal.details.text,
		"Response from actual recipient not visible in journal")
	journal.close_journal()
	print("REALITY04_JOURNAL_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
