extends Node
## One authenticated transport for every gameplay API. Credentials never go in URLs.
var _url := "http://127.0.0.1:8000"
var _token := ""
var instance_id := ""
var configuration_error := ""

func _ready() -> void:
	var configured := OS.get_environment("LAIN_SERVER_URL").strip_edges().trim_suffix("/")
	_token = OS.get_environment("LAIN_PLAYER_TOKEN").strip_edges()
	instance_id = "%s-%s" % [Time.get_ticks_usec(), randi()]
	if not configured.is_empty():
		_url = configured
		if _token.length() < 40:
			configuration_error = "Falta tu acceso personal al servidor. Revisa lain-online.json."
		if not _url.begins_with("https://") and not (OS.get_environment("LAIN_ALLOW_LAN_HTTP") == "1" and _url.begins_with("http://")):
			configuration_error = "La conexión online requiere HTTPS; HTTP solo se admite en una red local configurada."
	elif not _token.is_empty():
		configuration_error = "Falta la dirección del servidor online."

func base_url() -> String:
	return _url

func is_online() -> bool:
	return not _token.is_empty()

func headers() -> PackedStringArray:
	var result := PackedStringArray(["Content-Type: application/json"])
	if is_online():
		result.append("Authorization: Bearer " + _token)
		result.append("X-Lain-Client: " + instance_id)
	return result
