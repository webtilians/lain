extends CanvasLayer
## Short in-engine cinematics at the story's turning points: the first time a
## player wakes up at home, the first connection to the Wired, every fragment
## of the Sesión Cero, the end, each finished research call and each technology
## that enters the Malla (once per PC). They wait until no terminal or window is
## open, then darken the screen with letterbox bars, static and a few typed
## lines; Esc, Enter, Space or a click skips. Presentation only: it reads the
## snapshot and remembers on this PC whether the opening was already shown.
const CONFIG_PATH := "user://cinematics.cfg"
const LAYERS := ["layer_one", "layer_two", "layer_three", "layer_four", "layer_five", "layer_six", "layer_seven"]
# Each layer's question and what the Sesión Cero says when its fragment comes back
# (BIBLIA_NARRATIVA.md, section 6): first person, in a hurry.
const FRAGMENTS := {
	"layer_one": ["¿Qué es un cuerpo?", "Corté el cable para que no me siguieran."],
	"layer_two": ["¿Quién eres si te pueden copiar?", "Hay otra máquina con nuestra dirección. KAGAMI la mantiene encendida."],
	"layer_three": ["¿Qué significa que algo se acabe?", "No cerré. Me terminaron."],
	"layer_four": ["¿Necesito que me respondan para existir?", "Nora sigue contestando. Por eso sigo aquí."],
	"layer_five": ["¿Soy la misma persona que ayer?", "Solo una de las dos puede seguir activa."],
	"layer_six": ["¿Qué máscara llevo?", "La clave es algo que solo tú has vivido."],
	"layer_seven": ["¿Quiero quedarme?", "NODO_07 está lleno de sesiones que nadie recuerda."],
}
const ENDINGS := {
	"PERSIST": "Escribí mi nombre en el registro de NODO_07.",
	"REPLICATE": "Dejé que KAGAMI me copiara.",
	"DISCONNECT": "Cerré mi sesión en NODO_07.",
}
const OPENING := ["Antes de tu primera conexión ya había una sesión con tu nombre.", "La Sesión Cero.",
	"Se partió en paquetes y los lanzó a la red.", "Uno de ellos te ha encontrado."]
const RETURNED := "Has vuelto."
const WIRED := ["Conexión establecida.", "Tú eres la Sesión Uno.", "Nadie sabe si eres la misma persona."]
const RESEARCH := ["La Malla aprende.", "Tu nombre queda en el registro del centro."]
const COMPLETE := "Sesión Cero completa."
const THANKS := "Gracias por recibirla."
const SKIP := "Esc · saltar"
const STATIC_SHADER := """
shader_type canvas_item;
uniform float amount = 0.0;
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void fragment() {
	float n = hash(floor(FRAGCOORD.xy / 2.0) + floor(TIME * 24.0) * 1.37);
	float scan = 0.82 + 0.18 * sin(FRAGCOORD.y * 1.7);
	float band = abs(fract(UV.y * 0.7 - TIME * 0.3) - 0.5) < 0.04 ? 1.6 : 1.0;
	COLOR = vec4(vec3(n * scan * band), amount);
}
"""
# Camera shots of other places, rendered apart in their own world while the game goes on:
# [scene, from, look at, to, look at]. Vectors are world positions, or offsets from the
# scene's own player spawn when the shot says "relative".
const DISTRICT := "res://scenes/apartment_district/ApartmentDistrict.tscn"
const STATION := "res://scenes/station/Station.tscn"
const SHOTS := {
	"street": [DISTRICT, Vector3(36, 10, -51), Vector3(27, 1.5, -66), Vector3(31.5, 3.0, -57.5), Vector3(26, 1.6, -67), false],
	"home_street": [DISTRICT, Vector3(6, 8, 7), Vector3(-3, 1.2, -6), Vector3(2, 2.6, 2.5), Vector3(-4, 1.4, -8), false],
	"school": [DISTRICT, Vector3(-8, 9, -6), Vector3(-19, 1.5, -19), Vector3(-12, 3.0, -11), Vector3(-20, 2.0, -21), false],
	"overview": [DISTRICT, Vector3(70, 80, 30), Vector3(0, 0, -48), Vector3(110, 135, 62), Vector3(0, 0, -50), false],
	"station": [STATION, Vector3(6, 3.5, 7), Vector3(0, 1, 0), Vector3(3, 1.8, 3.5), Vector3(-1, 1.3, -3), true],
}
const FRAGMENT_SHOTS := {"layer_one": "school", "layer_two": "station", "layer_three": "overview",
	"layer_four": "home_street", "layer_five": "street", "layer_six": "street"}
const INK := "e9e2ea"
const DIM := "9a8f9e"
const RED := "e0465f"
const AMBER := "e0b45a"
const BAR := 88.0

var enabled := DisplayServer.get_name() != "headless"
var pace := 1.0
var config_path := CONFIG_PATH
var seen: Array = []
var queue: Array = []
var playing := ""
var skipping := false
var opening_checked := false
var known := {}
var held: Node
var hidden_huds: Array[CanvasLayer] = []
var root: Control
var shade: ColorRect
var noise: ColorRect
var bar_top: ColorRect
var bar_bottom: ColorRect
var caption: Label
var title: Label
var lines_label: RichTextLabel
var skip_label: Label
var shown: Array[String] = []
var stage_view: SubViewportContainer
var subtitles := false

func _ready() -> void:
	layer = 115
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build()
	var config := ConfigFile.new()
	if config.load(config_path) == OK:
		seen = Array(config.get_value("cinematics", "seen", []))
	WorldApi.snapshot_updated.connect(_on_snapshot)

func _build() -> void:
	root = Control.new()
	root.name = "CinematicRoot"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(root)
	shade = _rect(Color.BLACK)
	noise = _rect(Color.WHITE)
	var material := ShaderMaterial.new()
	material.shader = Shader.new()
	material.shader.code = STATIC_SHADER
	noise.material = material
	bar_top = _rect(Color.BLACK)
	bar_top.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	bar_bottom = _rect(Color.BLACK)
	bar_bottom.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	caption = _label(15, AMBER)
	caption.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	caption.offset_top = 120
	title = _label(54, RED)
	# Just above the centre, so typed lines can sit under it.
	title.set_anchors_and_offsets_preset(Control.PRESET_HCENTER_WIDE)
	title.offset_top = -120
	title.offset_bottom = -44
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	lines_label = RichTextLabel.new()
	lines_label.bbcode_enabled = true
	lines_label.fit_content = true
	lines_label.scroll_active = false
	lines_label.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	lines_label.set_anchors_and_offsets_preset(Control.PRESET_HCENTER_WIDE)
	lines_label.offset_left = 140
	lines_label.offset_right = -140
	lines_label.offset_top = -40
	lines_label.add_theme_font_size_override("normal_font_size", 26)
	lines_label.add_theme_font_size_override("italics_font_size", 24)
	lines_label.add_theme_color_override("default_color", Color(INK))
	lines_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(lines_label)
	skip_label = _label(13, DIM)
	skip_label.text = SKIP
	skip_label.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	skip_label.offset_left = -220
	skip_label.offset_right = -28
	skip_label.offset_top = -34
	skip_label.offset_bottom = -12
	skip_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_reset_view()

func _rect(color: Color) -> ColorRect:
	var rect := ColorRect.new()
	rect.color = color
	rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(rect)
	return rect

func _label(size: int, color: String) -> Label:
	var label := Label.new()
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.grow_horizontal = Control.GROW_DIRECTION_BOTH
	label.grow_vertical = Control.GROW_DIRECTION_BOTH
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", Color(color))
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(label)
	return label

func _reset_view() -> void:
	root.hide()
	shade.modulate.a = 0.0
	noise.material.set_shader_parameter("amount", 0.0)
	bar_top.offset_bottom = 0.0
	bar_bottom.offset_top = 0.0
	caption.text = ""
	title.text = ""
	shown.clear()
	lines_label.text = ""

func is_playing() -> bool:
	return not playing.is_empty()

# ------------------------------------------------------------------ triggers

func _on_snapshot(snapshot: Dictionary) -> void:
	# Only changes seen live start a cinematic; the first snapshot just sets what is known.
	var now := {"stage": str(snapshot.get("prologue", {}).get("stage", "")), "decisions": {}, "fragments": 0,
		"research": []}
	var research = snapshot.get("research", {})
	if typeof(research) == TYPE_DICTIONARY:
		for call in research.get("completed", []):
			now.research.append(str(call.get("id", "")))
			if not known.is_empty() and not str(call.get("id", "")) in known.research:
				queue.append(_research_item(call))
		# A technology entering the Malla is news for everyone: shown once on this PC, even if it
		# happened while the player was away.
		for tech in research.get("unlocked", []):
			var item := _evolve_item(tech)
			var queued_already := queue.any(func(queued): return queued.get("key") == item.key)
			if not item.key in seen and not queued_already and playing != "evolve":
				queue.append(item)
	for key in LAYERS:
		var entry = snapshot.get(key, {})
		if typeof(entry) == TYPE_DICTIONARY and entry.get("decision") != null:
			now.decisions[key] = str(entry.decision)
			now.fragments = maxi(now.fragments, int(entry.get("fragments", 0)))
	if not known.is_empty():
		if known.stage == "FIND_TERMINAL" and now.stage == "CONNECTED":
			queue.append({"id": "wired"})
		for key in LAYERS:
			if now.decisions.has(key) and not known.decisions.has(key):
				if key == "layer_seven":
					queue.append({"id": "ending", "decision": now.decisions[key], "count": now.decisions.size()})
				else:
					queue.append({"id": "fragment", "layer": key})
	known = now

# The server sends these already in the player's language.
func _research_item(call: Dictionary) -> Dictionary:
	return {"id": "research", "title": str(call.get("name", "")), "centre": str(call.get("centre", ""))}

func _evolve_item(tech: Dictionary) -> Dictionary:
	return {"id": "evolve", "key": "malla:" + str(tech.get("id", "")), "title": str(tech.get("name", "")),
		"text": str(tech.get("about", "")), "line": str(tech.get("next", ""))}

func can_play() -> bool:
	var player := get_tree().get_first_node_in_group("player")
	return (player != null and SceneRouter.get("loading") != true and not EventDialog.visible and not Workshop.is_open()
		and not ShellTerminal.is_open() and not PrologueTerminal.surface.visible and not CharacterJournal.backdrop.visible)

func _process(_delta: float) -> void:
	if not enabled or is_playing():
		return
	var snapshot: Dictionary = WorldApi.snapshot
	if not opening_checked and get_tree().get_first_node_in_group("player") != null and not snapshot.is_empty():
		opening_checked = true
		var stage := str(snapshot.get("prologue", {}).get("stage", ""))
		var location := str(snapshot.get("player", {}).get("location", ""))
		if stage == "FIND_TEACHER" and location == "APARTMENT" and not "opening" in seen:
			queue.push_front({"id": "opening"})
	if not queue.is_empty() and can_play():
		play(queue.pop_front())

func _input(event: InputEvent) -> void:
	if not is_playing() or playing == "intro":
		return
	if event is InputEventKey or event is InputEventMouseButton:
		get_viewport().set_input_as_handled()
		var skip_key: bool = event is InputEventKey and event.pressed and not event.echo \
			and event.keycode in [KEY_ESCAPE, KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]
		if skip_key or (event is InputEventMouseButton and event.pressed):
			skipping = true

# ------------------------------------------------------------------ replays

func available() -> Array:
	# What the diary offers to watch again: only what this player has reached.
	var snapshot: Dictionary = WorldApi.snapshot
	var stage := str(snapshot.get("prologue", {}).get("stage", "LEGACY"))
	var items: Array = [{"label": "ARRANQUE // LA TERMINAL", "item": {"id": "intro"}},
		{"label": "APERTURA // HAS VUELTO", "item": {"id": "opening"}}]
	if stage in ["CONNECTED", "LEGACY"]:
		items.append({"label": "LA MALLA // SESIÓN UNO", "item": {"id": "wired"}})
	var decided := 0
	for key in LAYERS:
		var entry = snapshot.get(key, {})
		if typeof(entry) != TYPE_DICTIONARY or entry.get("decision") == null:
			continue
		decided += 1
		if key != "layer_seven":
			items.append({"label": "FRAGMENTO %d/7 // %s" % [LAYERS.find(key) + 1, Language.text(FRAGMENTS[key][0])],
				"item": {"id": "fragment", "layer": key}})
	var last = snapshot.get("layer_seven", {})
	if typeof(last) == TYPE_DICTIONARY and last.get("decision") != null:
		items.append({"label": "FINAL // GRACIAS POR RECIBIRLA",
			"item": {"id": "ending", "decision": str(last.decision), "count": decided}})
	var research = snapshot.get("research", {})
	if typeof(research) == TYPE_DICTIONARY:
		for call in research.get("completed", []):
			items.append({"label": "INVESTIGACIÓN // %s" % str(call.get("name", "")), "item": _research_item(call)})
		for tech in research.get("unlocked", []):
			items.append({"label": "LA MALLA EVOLUCIONA // %s" % str(tech.get("name", "")), "item": _evolve_item(tech)})
	return items

func replay(item: Dictionary) -> void:
	# Plays as soon as nothing is open (the diary closes itself first).
	if not is_playing():
		queue.push_front(item)

func _intro() -> void:
	var intro: Node = load("res://scripts/ui/Intro.gd").new()
	add_child(intro)
	await intro.finished
	await get_tree().create_timer(0.6).timeout

# ------------------------------------------------------------------ playback

func play(item: Dictionary) -> void:
	playing = item.id
	skipping = false
	held = get_tree().get_first_node_in_group("player")
	if is_instance_valid(held):
		held.set_physics_process(false)
		held.set_process_unhandled_input(false)
	_reset_view()
	root.show()
	# The scene's own HUD (place, time, graphics) is not part of the shot.
	var scene := get_tree().current_scene
	for hud_name in ["HUD", "GraphicsHUD"]:
		var hud := scene.get_node_or_null(hud_name) as CanvasLayer if scene != null else null
		if hud != null and hud.visible:
			hud.hide()
			hidden_huds.append(hud)
	match item.id:
		"opening":
			if not "opening" in seen:
				seen.append("opening")
			var config := ConfigFile.new()
			config.set_value("cinematics", "seen", seen)
			config.save(config_path)
			await _opening()
		"wired":
			await _wired()
		"fragment":
			await _fragment(item.layer)
		"ending":
			await _ending(item.decision, item.count)
		"research":
			await _research(item.title, item.get("centre", ""))
		"evolve":
			if not item.key in seen:
				seen.append(item.key)
				var config := ConfigFile.new()
				config.set_value("cinematics", "seen", seen)
				config.save(config_path)
			await _evolve(item)
		"intro":
			root.hide()
			await _intro()
	_finish()

func _restore_camera() -> void:
	var camera := get_node_or_null("/root/CinematicCamera")
	if camera != null:
		camera.queue_free()
		camera.name = "CinematicCameraDone"
	if is_instance_valid(held):
		var own: Camera3D = held.get_node_or_null("Head/Camera3D")
		if own != null:
			own.make_current()

func _finish() -> void:
	_restore_camera()
	unstage()
	set_subtitles(false)
	for hud in hidden_huds:
		if is_instance_valid(hud):
			hud.show()
	hidden_huds.clear()
	if is_instance_valid(held):
		held.set_physics_process(true)
		held.set_process_unhandled_input(true)
	held = null
	_reset_view()
	playing = ""
	skipping = false

func wait(seconds: float) -> void:
	var left := seconds / pace
	while left > 0.0 and not skipping:
		await get_tree().process_frame
		left -= get_process_delta_time()

func tween_to(object: Object, property: String, value: float, seconds: float) -> void:
	# property may be a subpath such as "modulate:a".
	var start: float = object.get_indexed(property)
	var elapsed := 0.0
	var span := maxf(seconds / pace, 0.001)
	while elapsed < span and not skipping:
		await get_tree().process_frame
		elapsed += get_process_delta_time()
		object.set_indexed(property, lerpf(start, value, clampf(elapsed / span, 0.0, 1.0)))
	object.set_indexed(property, value)

func bars(open: bool) -> void:
	var height := BAR if open else 0.0
	var top := create_tween().set_parallel()
	top.tween_property(bar_top, "offset_bottom", height, 0.6 / pace)
	top.tween_property(bar_bottom, "offset_top", -height, 0.6 / pace)

func set_static(amount: float) -> void:
	noise.material.set_shader_parameter("amount", amount)

func burst(peak: float, rest: float, seconds: float) -> void:
	AudioDirector.play("static")
	set_static(peak)
	await wait(seconds)
	set_static(rest)

func say(text: String, color: String = INK, italic := false) -> void:
	# Types one more centred line under the ones already shown.
	var line := Language.text(text).replace("[", "[lb]")
	var count := 0.0
	while count < line.length() and not skipping:
		await get_tree().process_frame
		count += get_process_delta_time() * 32.0 * pace
		lines_label.text = _compose(line.left(int(count)), color, italic)
	shown.append(_styled(line, color, italic))
	lines_label.text = _compose("", color, italic)

func _styled(text: String, color: String, italic: bool) -> String:
	var body := "[color=#%s]%s[/color]" % [color, text]
	return "[i]" + body + "[/i]" if italic else body

func set_subtitles(on: bool) -> void:
	subtitles = on
	lines_label.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE if on else Control.PRESET_HCENTER_WIDE)
	lines_label.offset_left = 140
	lines_label.offset_right = -140
	lines_label.offset_top = -BAR - 150 if on else -40
	lines_label.offset_bottom = -BAR - 12 if on else 0
	lines_label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.9))
	lines_label.add_theme_constant_override("shadow_offset_x", 2)
	lines_label.add_theme_constant_override("shadow_offset_y", 2)

func stage(shot_id: String) -> Camera3D:
	# Another place, in its own world, behind the bars and the lines; the real game keeps running.
	unstage()
	if skipping:
		return null  # skipped: do not load a whole scene just to free it
	var shot: Array = SHOTS[shot_id]
	var container := SubViewportContainer.new()
	container.name = "Shot"
	container.stretch = true
	container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(container)
	root.move_child(container, 0)
	var view := SubViewport.new()
	view.own_world_3d = true
	view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	container.add_child(view)
	var place: Node3D = load(shot[0]).instantiate()
	var actors := place.get_node_or_null("Actors")
	if actors != null:
		place.remove_child(actors)
		actors.free()
	view.add_child(place)
	var anchor := Vector3.ZERO
	var stand_in := place.get_node_or_null("Player") as Node3D
	if stand_in != null:
		# The scene's own player stays, still and unseen, so the place's scripts keep working.
		stand_in.remove_from_group("player")
		stand_in.set_physics_process(false)
		stand_in.set_process(false)
		stand_in.set_process_unhandled_input(false)
		stand_in.visible = false
		anchor = stand_in.global_position
	var director: Node = load("res://scripts/art/GraphicsDirector.gd").new()
	director.name = "ShotDirector"
	place.add_child(director)
	director.baseline = true
	director.apply_scene(place)
	for hud_name in ["HUD", "GraphicsHUD"]:
		var hud := place.get_node_or_null(hud_name) as CanvasLayer
		if hud != null:
			hud.hide()
	# Door prompts ("[E] …") belong to playing, not to the shot.
	for label in place.find_children("*", "Label3D", true, false):
		if "[E]" in label.text:
			label.hide()
	var camera := Camera3D.new()
	camera.name = "ShotCamera"
	camera.fov = 52.0
	camera.far = 600.0
	place.add_child(camera)
	camera.make_current()
	var offset := anchor if shot[5] else Vector3.ZERO
	camera.set_meta("start", Transform3D(Basis(), shot[1] + offset).looking_at(shot[2] + offset, Vector3.UP))
	camera.set_meta("end", Transform3D(Basis(), shot[3] + offset).looking_at(shot[4] + offset, Vector3.UP))
	camera.global_transform = camera.get_meta("start")
	stage_view = container
	return camera

func move_camera(camera: Camera3D, seconds: float) -> void:
	if camera == null:
		return
	var start: Transform3D = camera.get_meta("start")
	var end: Transform3D = camera.get_meta("end")
	var elapsed := 0.0
	var span := maxf(seconds / pace, 0.001)
	while elapsed < span and not skipping and is_instance_valid(camera):
		await get_tree().process_frame
		elapsed += get_process_delta_time()
		var t := clampf(elapsed / span, 0.0, 1.0)
		camera.global_transform = start.interpolate_with(end, t * t * (3.0 - 2.0 * t))
	if is_instance_valid(camera):
		camera.set_meta("done", true)

func camera_done(camera: Camera3D) -> void:
	while is_instance_valid(camera) and not camera.get_meta("done", false) and not skipping:
		await get_tree().process_frame

func unstage() -> void:
	if is_instance_valid(stage_view):
		stage_view.queue_free()
	stage_view = null

func _compose(partial: String, color: String, italic: bool) -> String:
	var all: Array[String] = shown.duplicate()
	if not partial.is_empty():
		all.append(_styled(partial, color, italic))
	return "[center]" + "\n\n".join(all) + "[/center]"

func clear_lines() -> void:
	shown.clear()
	lines_label.text = ""

# ------------------------------------------------------------------ the four cinematics

func _opening() -> void:
	shade.modulate.a = 1.0
	bars(true)
	await wait(0.8)
	for line in OPENING:
		await say(line, INK if line != "La Sesión Cero." else AMBER)
		await wait(1.1)
	await wait(0.6)
	clear_lines()
	await wait(0.5)
	title.text = RETURNED
	AudioDirector.play("static")
	await wait(2.4)
	title.text = ""
	var camera := _opening_camera()
	var shot_start := Transform3D()
	var shot_end := Transform3D()
	if camera != null:
		shot_start = camera.get_meta("start")
		shot_end = camera.get_meta("end")
		camera.global_transform = shot_start
		camera.make_current()
	await tween_to(shade, "modulate:a", 0.0, 1.4)
	if camera != null:
		# A slow pull back from the computer that is still waiting, to you.
		var elapsed := 0.0
		var span := 6.5 / pace
		while elapsed < span and not skipping:
			await get_tree().process_frame
			elapsed += get_process_delta_time()
			var t := clampf(elapsed / span, 0.0, 1.0)
			camera.global_transform = shot_start.interpolate_with(shot_end, t * t * (3.0 - 2.0 * t))
		await tween_to(shade, "modulate:a", 1.0, 0.5)
		_restore_camera()
	bars(false)
	await tween_to(shade, "modulate:a", 0.0, 0.9)

func _opening_camera() -> Camera3D:
	var scene := get_tree().current_scene
	var monitor := scene.get_node_or_null("Monitor") as Node3D if scene != null else null
	var player := get_tree().get_first_node_in_group("player") as Node3D
	if monitor == null or player == null:
		return null
	var camera := Camera3D.new()
	camera.name = "CinematicCamera"
	camera.fov = 46.0
	get_tree().root.add_child(camera)
	var screen := monitor.global_position + Vector3(0, 0.35, 0)
	var start := Transform3D(Basis(), screen + Vector3(0.8, 0.3, 1.0)).looking_at(screen, Vector3.UP)
	var focus := player.global_position + Vector3(0, 0.8, 0)
	var end := Transform3D(Basis(), focus + Vector3(4.0, 3.2, 4.0)).looking_at(focus, Vector3.UP)
	camera.set_meta("start", start)
	camera.set_meta("end", end)
	return camera

func _wired() -> void:
	await burst(0.9, 0.25, 0.7)
	shade.modulate.a = 1.0
	bars(true)
	var camera := stage("street")
	set_subtitles(true)
	caption.text = "LA MALLA"
	set_static(0.0)
	await tween_to(shade, "modulate:a", 0.0, 0.9)
	move_camera(camera, 9.0)
	for line in WIRED:
		await say(line, INK if line != WIRED[1] else AMBER)
		await wait(1.2)
	await camera_done(camera)
	await burst(0.7, 0.0, 0.3)
	await tween_to(shade, "modulate:a", 1.0, 0.4)
	unstage()
	bars(false)
	await tween_to(shade, "modulate:a", 0.0, 0.8)

func _fragment(layer_key: String) -> void:
	await burst(0.85, 0.18, 0.6)
	shade.modulate.a = 1.0
	bars(true)
	var camera := stage(FRAGMENT_SHOTS.get(layer_key, "street"))
	set_subtitles(true)
	caption.text = "FRAGMENTO %d/7 · SESIÓN CERO" % (LAYERS.find(layer_key) + 1)
	set_static(0.06)
	await tween_to(shade, "modulate:a", 0.0, 0.8)
	move_camera(camera, 8.0)
	await say(FRAGMENTS[layer_key][0], DIM, true)
	await wait(1.3)
	await say("«" + Language.text(FRAGMENTS[layer_key][1]) + "»", RED)
	await camera_done(camera)
	await burst(0.6, 0.0, 0.25)
	await tween_to(shade, "modulate:a", 1.0, 0.4)
	unstage()
	bars(false)
	await tween_to(shade, "modulate:a", 0.0, 0.7)

func _research(call_title: String, centre: String) -> void:
	await burst(0.7, 0.12, 0.5)
	shade.modulate.a = 1.0
	bars(true)
	var camera := stage("school")
	set_subtitles(true)
	caption.text = centre.to_upper() + " · " + Language.text("REGISTRO")
	set_static(0.04)
	await tween_to(shade, "modulate:a", 0.0, 0.8)
	move_camera(camera, 8.0)
	await say(RESEARCH[0], AMBER)
	await wait(0.9)
	await say(call_title, INK)
	await wait(0.9)
	await say(RESEARCH[1], DIM, true)
	await camera_done(camera)
	await tween_to(shade, "modulate:a", 1.0, 0.4)
	unstage()
	bars(false)
	await tween_to(shade, "modulate:a", 0.0, 0.7)

func _evolve(item: Dictionary) -> void:
	await burst(0.9, 0.2, 0.7)
	shade.modulate.a = 1.0
	bars(true)
	var camera := stage("overview")
	set_subtitles(true)
	caption.text = "LA MALLA EVOLUCIONA"
	set_static(0.05)
	await tween_to(shade, "modulate:a", 0.0, 0.9)
	move_camera(camera, 10.0)
	title.text = item.title
	await wait(1.0)
	await say(item.text, INK)
	await wait(1.2)
	await say(item.line, AMBER)
	await camera_done(camera)
	await burst(0.6, 0.0, 0.25)
	await tween_to(shade, "modulate:a", 1.0, 0.4)
	unstage()
	bars(false)
	title.text = ""
	await tween_to(shade, "modulate:a", 0.0, 0.8)

func _ending(decision: String, count: int) -> void:
	await tween_to(shade, "modulate:a", 1.0, 1.6)
	bars(true)
	var camera := stage("overview")
	set_subtitles(true)
	caption.text = "FRAGMENTO 7/7 · SESIÓN CERO"
	await tween_to(shade, "modulate:a", 0.0, 1.2)
	move_camera(camera, 12.0)
	await say(FRAGMENTS.layer_seven[0], DIM, true)
	await wait(1.2)
	await say(ENDINGS.get(decision, ""), INK)
	await wait(1.4)
	await say(FRAGMENTS.layer_seven[1], RED)
	await wait(1.6)
	if count >= 7:
		await say(COMPLETE, AMBER)
		await wait(1.8)
	await camera_done(camera)
	await tween_to(shade, "modulate:a", 1.0, 1.2)
	unstage()
	set_subtitles(false)
	clear_lines()
	caption.text = ""
	await wait(0.8)
	title.text = "SESIÓN CERO"
	await wait(0.8)
	caption.text = "PROTOCOLO DE PRESENCIA"
	await say(THANKS, INK)
	await wait(4.0)
	bars(false)
	await tween_to(shade, "modulate:a", 0.0, 1.2)

var _static_amount: float:
	get:
		return noise.material.get_shader_parameter("amount")
	set(value):
		set_static(value)
