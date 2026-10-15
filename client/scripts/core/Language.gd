extends Node
## Presentation language, independent from the account and the shared world.
signal changed
const CODES := ["es", "en", "ru"]  # Spanish is the source; the others come from res://translations
const NAMES := {"es": "Español", "en": "English", "ru": "Русский"}
## A wink for Olya, who brought the game to her friends: choosing Russian greets her.
const GREETING := ["Привет, Оля!", "Мы тебя ждали."]
var code := "es"
var settings_path := "user://language.cfg"
var catalogs := {}  # language -> PlayerTranslation

func _ready() -> void:
	# The window carries the game's name; the project keeps its old internal name
	# so every player's saved settings and session stay where they are.
	get_tree().root.title = "Sesión Cero"
	for language in CODES.slice(1):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string("res://translations/%s.json" % language))
		if parsed is Dictionary:
			var translation = preload("res://scripts/core/PlayerTranslation.gd").new()
			translation.configure(parsed, language)
			TranslationServer.add_translation(translation)
			catalogs[language] = translation
	var config := ConfigFile.new()
	if config.load(settings_path) == OK:
		code = str(config.get_value("language", "code", "es"))
	if code not in CODES:
		code = "es"
	TranslationServer.set_locale(code)

func _exit_tree() -> void:
	for translation in catalogs.values():
		TranslationServer.remove_translation(translation)

func select(language_code: String) -> void:
	if language_code not in CODES:
		return
	var before := code
	code = language_code
	TranslationServer.set_locale(code)
	var config := ConfigFile.new()
	config.set_value("language", "code", code)
	config.save(settings_path)
	changed.emit()
	if code == "ru" and before != "ru":
		greet()
	# World snapshots and subsequent conversations follow the new language.
	if is_instance_valid(get_node_or_null("/root/WorldApi")) and not ServerConnection.awaiting_login:
		WorldApi.request_state()

func text(source: String) -> String:
	if code == "es" or not catalogs.has(code):
		return source
	return catalogs[code].render(source)

func greet() -> CanvasLayer:
	## «Hi Olya, we were waiting for you», over whatever is on screen, and gone in a few seconds.
	var old := get_node_or_null("Greeting")
	if old != null:
		old.free()
	var layer := CanvasLayer.new()
	layer.name = "Greeting"
	layer.layer = 128
	add_child(layer)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(center)
	var column := VBoxContainer.new()
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_theme_constant_override("separation", 6)
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.add_child(column)
	for index in GREETING.size():
		var line := Label.new()
		line.text = GREETING[index]
		line.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
		line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		line.add_theme_font_size_override("font_size", 52 if index == 0 else 26)
		line.add_theme_color_override("font_color", Color("ffe3f1") if index == 0 else Color("e9e2ea"))
		line.add_theme_color_override("font_shadow_color", Color(1.0, 0.25, 0.69, 0.75))
		line.add_theme_constant_override("shadow_offset_x", 0)
		line.add_theme_constant_override("shadow_offset_y", 0)
		line.add_theme_constant_override("shadow_outline_size", 22 if index == 0 else 12)
		column.add_child(line)
	column.modulate.a = 0.0
	var show := create_tween()
	show.tween_property(column, "modulate:a", 1.0, 0.7)
	show.tween_interval(3.4)
	show.tween_property(column, "modulate:a", 0.0, 0.9)
	show.tween_callback(layer.queue_free)
	return layer

func _unhandled_key_input(event: InputEvent) -> void:
	# Also available in local games, which bypass the online account menu.
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F8:
		select(CODES[(CODES.find(code) + 1) % CODES.size()])
		get_viewport().set_input_as_handled()
