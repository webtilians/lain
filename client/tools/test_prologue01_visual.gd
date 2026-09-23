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
		else:
			check(encounters == 0, "school corridor must not have Ryoko")
		check(scene.get_node_or_null("HUD/Hint") != null,
			location + ": missing readable route guidance")
		current_scene = null
		scene.queue_free()
		await process_frame

	var terminal = root.get_node("PrologueTerminal")
	api.snapshot["prologue"] = {"enabled": true, "stage": "FIND_TERMINAL"}
	terminal.open_terminal()
	check(terminal.surface.visible, "DOS terminal does not open")
	check("LAIN-DOS" in terminal.transcript.text, "DOS prompt is missing")
	terminal._on_command("help")
	check("Telnet" in terminal.transcript.text or "TELNET" in terminal.transcript.text,
		"Terminal lacks external syntax research hint")
	terminal.close_terminal()
	check(not terminal.surface.visible, "Terminal cannot close")
	print("PROLOGUE01_VISUAL_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
