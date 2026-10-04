extends Node
## Sound. Each place has its own ambience (cross-faded when the scene changes)
## and the interface answers with short effects. Presentation only: it never
## reads or writes world state beyond the snapshot the UI already shows.
## The sounds are synthesised by tools/make_sounds.py.
const CONFIG_PATH := "user://audio.cfg"
const LEVELS := [1.0, 0.5, 0.0]
const LEVEL_TEXT := ["F7  ·  SONIDO: sí", "F7  ·  SONIDO: a la mitad", "F7  ·  SONIDO: no"]
const LOOPS := ["rain", "rain_window", "hum", "room", "arcade", "club", "station"]
const FADE := 1.2
const AMBIENCE := {
	"APARTMENT_DISTRICT": [["rain", -10.0]],
	"APARTMENT": [["rain_window", -14.0], ["room", -20.0]],
	"STATION": [["station", -10.0], ["hum", -24.0]],
	"SCHOOL": [["hum", -20.0], ["room", -24.0]],
	"SCHOOL_LAB": [["hum", -18.0], ["room", -24.0]],
	"VIDEO_CLUB": [["hum", -19.0], ["room", -22.0]],
	"GROCERY": [["hum", -18.0], ["room", -22.0]],
	"BOOKSHOP": [["room", -18.0], ["hum", -26.0]],
	"IZAKAYA": [["room", -15.0], ["rain_window", -26.0]],
	"CAFE": [["room", -16.0], ["rain_window", -26.0]],
	"ARCADE": [["arcade", -13.0], ["hum", -26.0]],
	"NIGHTCLUB": [["club", -9.0]],
}
const EFFECTS := {"key": -18.0, "enter": -13.0, "error": -12.0, "mail": -8.0, "complete": -6.0,
	"hint": -9.0, "door": -12.0, "static": -11.0}

var level := 0
var location := ""
var streams := {}
var ambience: Array[AudioStreamPlayer] = []
var pool: Array[AudioStreamPlayer] = []
var scene_id := 0
var last_key := 0
var unread := -1
var opened := -1
var label: Label
var label_layer: CanvasLayer
var next_slot := 0
var last_played := ""
# Headless runs (tests, the server-side tools) have no audio device: everything is
# prepared and tracked, but nothing is played, so no playback outlives the process.
var silent := DisplayServer.get_name() == "headless"

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var config := ConfigFile.new()
	if config.load(CONFIG_PATH) == OK:
		level = clampi(int(config.get_value("audio", "level", 0)), 0, 2)
	for i in range(6):
		var player := AudioStreamPlayer.new()
		player.name = "Effect%d" % i
		add_child(player)
		pool.append(player)
	label_layer = CanvasLayer.new()
	label_layer.layer = 22
	add_child(label_layer)
	label = Label.new()
	label.position = Vector2(29, 160)
	label.add_theme_font_size_override("font_size", 11)
	label.add_theme_color_override("font_color", Color("c0c7c8"))
	label.hide()
	label_layer.add_child(label)
	WorldApi.snapshot_updated.connect(_on_snapshot)
	_apply_level()

func _exit_tree() -> void:
	# Let go of every stream so the engine exits without leaked resources.
	for player in ambience + pool:
		if is_instance_valid(player):
			player.stop()
			player.stream = null
	streams.clear()

func _process(_delta: float) -> void:
	var scene := get_tree().current_scene
	if scene != null and scene.get_instance_id() != scene_id:
		var first := scene_id == 0
		scene_id = scene.get_instance_id()
		enter(location_of(scene))
		if not first:
			play("door")

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F7:
		cycle()
		get_viewport().set_input_as_handled()

func location_of(scene: Node) -> String:
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	for key in paths:
		if paths[key] == scene.scene_file_path:
			return key
	return ""

func stream(sound: String) -> AudioStream:
	if not streams.has(sound):
		var loaded: AudioStream = load("res://audio/%s.wav" % sound)
		if loaded is AudioStreamWAV and sound in LOOPS:
			loaded.loop_mode = AudioStreamWAV.LOOP_FORWARD
			loaded.loop_begin = 0
			loaded.loop_end = int(loaded.get_length() * loaded.mix_rate)
		streams[sound] = loaded
	return streams[sound]

func enter(place: String) -> void:
	# Fade out what was playing and fade in this place's layers.
	location = place
	for player in ambience:
		if is_instance_valid(player):
			var out := create_tween()
			out.tween_property(player, "volume_db", -60.0, FADE)
			out.tween_callback(player.queue_free)
	ambience.clear()
	for layer in AMBIENCE.get(place, []):
		var player := AudioStreamPlayer.new()
		player.name = "Ambience_" + str(layer[0])
		player.stream = stream(layer[0])
		player.volume_db = -60.0
		add_child(player)
		if not silent:
			player.play()
		create_tween().tween_property(player, "volume_db", float(layer[1]), FADE)
		ambience.append(player)

func play(sound: String, jitter: float = 0.0) -> void:
	if level == 2 or not EFFECTS.has(sound):
		return
	if sound == "key":
		# Fast typing would otherwise stack dozens of clicks.
		var now := Time.get_ticks_msec()
		if now - last_key < 28:
			return
		last_key = now
	last_played = sound
	if silent:
		return
	# A free channel if there is one; otherwise the oldest, in turn, never the newest.
	var player: AudioStreamPlayer = pool[next_slot]
	for candidate in pool:
		if not candidate.playing:
			player = candidate
			break
	next_slot = (pool.find(player) + 1) % pool.size()
	player.stream = stream(sound)
	player.volume_db = EFFECTS[sound]
	player.pitch_scale = 1.0 + randf_range(-jitter, jitter)
	player.play()

func react(text: String) -> void:
	# The terminal's answer decides the sound: a completed layer, a hint or an error.
	if "COMPLETADA" in text or "COMPLETE ·" in text:
		play("complete")
		play("static")
	elif text.begins_with("PISTA") or text.begins_with("HINT"):
		play("hint")
	elif text.begins_with("Uso:") or text.begins_with("Usage:") or "no existe" in text or "does not exist" in text \
			or "orden desconocida" in text or "unknown command" in text:
		play("error")

func cycle() -> void:
	level = (level + 1) % LEVELS.size()
	var config := ConfigFile.new()
	config.set_value("audio", "level", level)
	if config.save(CONFIG_PATH) != OK:
		push_warning("No se pudo guardar el volumen.")
	_apply_level()
	label.text = LEVEL_TEXT[level]
	label.show()
	get_tree().create_timer(2.5).timeout.connect(label.hide)

func _apply_level() -> void:
	AudioServer.set_bus_mute(0, LEVELS[level] <= 0.0)
	if LEVELS[level] > 0.0:
		AudioServer.set_bus_volume_db(0, linear_to_db(LEVELS[level]))

func _on_snapshot(snapshot: Dictionary) -> void:
	# New mail or a newly opened layer rings once; the first snapshot only sets the count.
	var messages := int(snapshot.get("unread_messages", 0))
	var layers := 0
	for key in ["layer_one", "layer_two", "layer_three", "layer_four", "layer_five", "layer_six", "layer_seven"]:
		var entry = snapshot.get(key, {})
		if typeof(entry) == TYPE_DICTIONARY and bool(entry.get("active", false)):
			layers += 1
	if unread >= 0 and (messages > unread or layers > opened):
		play("mail")
	unread = messages
	opened = layers
