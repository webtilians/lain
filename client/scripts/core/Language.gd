extends Node
## Presentation language, independent from the account and the shared world.
signal changed
var code := "es"
var settings_path := "user://language.cfg"
var catalog: Dictionary = {}
var translation = preload("res://scripts/core/PlayerTranslation.gd").new()

func _ready() -> void:
	# The window carries the game's name; the project keeps its old internal name
	# so every player's saved settings and session stay where they are.
	get_tree().root.title = "Sesión Cero"
	var parsed = JSON.parse_string(FileAccess.get_file_as_string("res://translations/en.json"))
	if parsed is Dictionary:
		catalog = parsed
	translation.configure(catalog)
	TranslationServer.add_translation(translation)
	var config := ConfigFile.new()
	if config.load(settings_path) == OK:
		code = str(config.get_value("language", "code", "es"))
	if code not in ["es", "en"]:
		code = "es"
	TranslationServer.set_locale(code)

func _exit_tree() -> void:
	TranslationServer.remove_translation(translation)

func select(language_code: String) -> void:
	if language_code not in ["es", "en"]:
		return
	code = language_code
	TranslationServer.set_locale(code)
	var config := ConfigFile.new()
	config.set_value("language", "code", code)
	config.save(settings_path)
	changed.emit()
	# World snapshots and subsequent conversations follow the new language.
	if is_instance_valid(get_node_or_null("/root/WorldApi")) and not ServerConnection.awaiting_login:
		WorldApi.request_state()

func text(source: String) -> String:
	if code == "es":
		return source
	return translation.render(source)

func _unhandled_key_input(event: InputEvent) -> void:
	# Also available in local games, which bypass the online account menu.
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F8:
		select("en" if code == "es" else "es")
		get_viewport().set_input_as_handled()
