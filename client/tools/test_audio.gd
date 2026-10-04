extends SceneTree
## Sound: every place plays its own looping ambience, the terminal answers
## with effects, F7 cycles the volume, and nothing touches the world.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var audio := root.get_node("AudioDirector")
	var level_before: int = audio.level
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for location in paths:
		api.snapshot = {"minute": 17, "player": {"location": location, "energy": .8}, "visible_actors": [], "known_nodes": []}
		var snapshot_before: Dictionary = api.snapshot.duplicate(true)
		var scene: Node3D = load(paths[location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		scene.get_node("Player").set_physics_process(false)
		await process_frame
		await process_frame
		check(audio.location == location, location + ": ambience did not follow the scene")
		var expected: Array = audio.AMBIENCE[location]
		check(audio.ambience.size() == expected.size(), location + ": wrong number of ambience layers")
		for player in audio.ambience:
			var wav := player.stream as AudioStreamWAV
			check(wav != null and wav.loop_mode == AudioStreamWAV.LOOP_FORWARD, location + ": ambience does not loop")
			check(audio.silent or player.playing, location + ": ambience is silent")
		check(api.snapshot == snapshot_before, location + ": sound changed the snapshot")
		scene.queue_free()
		current_scene = null
		await process_frame
	for sound in ["key", "enter", "error", "mail", "complete", "hint", "door", "static"]:
		check(audio.stream(sound) is AudioStreamWAV, sound + ": effect missing")
	audio.level = 0
	audio.react("Uso: decode <naranja|verde> <muestras> <ieee|thomas>")
	check(audio.last_played == "error", "errors do not buzz")
	audio.react("CAPA 01 COMPLETADA · fragmento 1/7 de la Sesión Cero recuperado.")
	check(audio.last_played == "static", "completing a layer does not bring Session Zero's static")
	audio.react("PISTA 1/3 · Capa 01 · Física")
	check(audio.last_played == "hint", "hints do not chime")
	audio.last_played = ""
	audio.unread = -1
	audio._on_snapshot({"unread_messages": 0})
	check(audio.last_played == "", "the first snapshot must not ring")
	audio._on_snapshot({"unread_messages": 1})
	check(audio.last_played == "mail", "new mail is silent")
	for step in range(3):
		audio.cycle()
	check(audio.level == 0 and not AudioServer.is_bus_mute(0), "F7 does not cycle back to full volume")
	audio.cycle()
	audio.cycle()
	check(AudioServer.is_bus_mute(0), "F7 'no' does not mute")
	while audio.level != level_before:
		audio.cycle()
	print("AUDIO_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
