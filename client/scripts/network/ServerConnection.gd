extends Node
## One authenticated transport for every gameplay API. Credentials never go in URLs.
## Online, the start menu (Boot) signs the player in before any world request;
## the token it receives is remembered per server in user://session.json.
var session_path := "user://session.json"
var _url := "http://127.0.0.1:8000"
var _token := ""
var _configured := false
var instance_id := ""
var configuration_error := ""
var awaiting_login := false
var account_name := ""
var client_version := ""

func _ready() -> void:
	var configured := OS.get_environment("LAIN_SERVER_URL").strip_edges().trim_suffix("/")
	_token = OS.get_environment("LAIN_PLAYER_TOKEN").strip_edges()
	client_version = OS.get_environment("LAIN_CLIENT_VERSION").strip_edges()
	instance_id = "%s-%s" % [Time.get_ticks_usec(), randi()]
	if not configured.is_empty():
		_configured = true
		_url = configured
		if _token.is_empty():
			_token = _load_session()
		if not _token.is_empty() and _token.length() < 40:
			configuration_error = "Tu acceso guardado no es válido. Revisa lain-online.json o vuelve a entrar."
		if not _url.begins_with("https://") and not (OS.get_environment("LAIN_ALLOW_LAN_HTTP") == "1" and _url.begins_with("http://")):
			configuration_error = "La conexión online requiere HTTPS; HTTP solo se admite en una red local configurada."
		# Automated clients (smoke tests) go straight in; players see the start menu.
		awaiting_login = OS.get_environment("LAIN_SKIP_MENU") != "1"
	elif not _token.is_empty():
		configuration_error = "Falta la dirección del servidor online."

func base_url() -> String:
	return _url

func is_online_mode() -> bool:
	return _configured

func has_session() -> bool:
	return not _token.is_empty()

func session_token() -> String:
	return _token

func is_online() -> bool:
	return not _token.is_empty() and not awaiting_login

func headers() -> PackedStringArray:
	var result := PackedStringArray(["Content-Type: application/json"])
	if is_online():
		result.append("Authorization: Bearer " + _token)
		result.append("X-Lain-Client: " + instance_id)
	return result

func account_headers() -> PackedStringArray:
	## For the start menu: sends the remembered token before entering the world.
	var result := PackedStringArray(["Content-Type: application/json"])
	if has_session():
		result.append("Authorization: Bearer " + _token)
		result.append("X-Lain-Client: " + instance_id)
	return result

func set_session(token: String, player_name: String) -> void:
	_token = token
	account_name = player_name
	var file := FileAccess.open(session_path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify({"server_url": _url, "token": token, "name": player_name}))

func clear_session() -> void:
	_token = ""
	account_name = ""
	if FileAccess.file_exists(session_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(session_path))

func finish_login() -> void:
	awaiting_login = false

func _load_session() -> String:
	if not FileAccess.file_exists(session_path):
		return ""
	var data = JSON.parse_string(FileAccess.get_file_as_string(session_path))
	if typeof(data) != TYPE_DICTIONARY or str(data.get("server_url", "")) != _url:
		return ""
	account_name = str(data.get("name", ""))
	var token := str(data.get("token", ""))
	return token if token.length() >= 40 and token.length() <= 128 else ""
