extends Control
## Start menu. Offline it boots the local world as before. Online it signs the
## player in (or creates an account) before the first world request.

const ERRORS := {
	"INVALID_LOGIN": "Nombre o contraseña incorrectos.",
	"NAME_TAKEN": "Ese nombre ya existe. Elige otro.",
	"INVALID_NAME": "El nombre debe tener entre 3 y 16 letras, números, espacios o guiones.",
	"WEAK_PASSWORD": "La contraseña debe tener al menos 6 caracteres.",
	"INVALID_INVITE": "El código de invitación no es correcto.",
	"REGISTRATION_CLOSED": "Ahora mismo no se pueden crear cuentas nuevas.",
	"PLEASE_WAIT": "Demasiados intentos. Espera unos minutos.",
	"PLAYER_ALREADY_CONNECTED": "Tu cuenta está abierta en otro equipo. Espera unos segundos y vuelve a intentarlo.",
	"INVALID_PLAYER_ACCESS": "Tu sesión ha caducado. Entra de nuevo.",
}
const RED := Color("c2253f")
const DIM := Color("9a8f9e")

@onready var status: Label = $Center/Status
var request: HTTPRequest
var menu: VBoxContainer
var form: VBoxContainer
var notice: Label
var fields: Dictionary = {}
var pending := ""
var me: Dictionary = {}

func _ready() -> void:
	WorldApi.api_error.connect(_on_api_error)
	WorldApi.snapshot_updated.connect(_on_snapshot_updated)
	if not ServerConnection.is_online_mode():
		status.text = "INICIANDO SISTEMA LOCAL..."
		WorldApi.request_state()
		return
	if not ServerConnection.awaiting_login:
		_enter()
		return
	request = HTTPRequest.new()
	request.timeout = 20
	request.max_redirects = 0
	add_child(request)
	request.request_completed.connect(_completed)
	_build()
	if not ServerConnection.configuration_error.is_empty():
		_say(ServerConnection.configuration_error)
	elif ServerConnection.has_session():
		_check_session()
	else:
		show_login()

func _build() -> void:
	status.hide()
	menu = VBoxContainer.new()
	menu.custom_minimum_size = Vector2(440, 0)
	menu.add_theme_constant_override("separation", 10)
	$Center.add_child(menu)
	var title := _label(menu, "L  A  I  N", 72, Color("e9e2ea"))
	title.add_theme_color_override("font_shadow_color", Color(0.76, 0.15, 0.25, 0.55))
	title.add_theme_constant_override("shadow_offset_x", 0)
	title.add_theme_constant_override("shadow_offset_y", 0)
	title.add_theme_constant_override("shadow_outline_size", 18)
	_label(menu, "PROTOCOLO DE PRESENCIA", 15, RED)
	menu.add_child(_gap(18))
	form = VBoxContainer.new()
	form.add_theme_constant_override("separation", 8)
	menu.add_child(form)
	notice = _label(menu, "", 15, Color("e7b493"))
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var version := Label.new()
	version.text = "versión " + (ServerConnection.client_version if not ServerConnection.client_version.is_empty() else "de desarrollo") + "  ·  " + ServerConnection.base_url().replace("https://", "")
	version.add_theme_font_size_override("font_size", 12)
	version.add_theme_color_override("font_color", DIM)
	version.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	version.position = Vector2(18, -30)
	add_child(version)

func _label(parent: Node, text: String, size: int, colour: Color) -> Label:
	var node := Label.new()
	node.text = text
	node.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	node.add_theme_font_size_override("font_size", size)
	node.add_theme_color_override("font_color", colour)
	parent.add_child(node)
	return node

func _gap(height: int) -> Control:
	var node := Control.new()
	node.custom_minimum_size.y = height
	return node

func _button(text: String, callback: Callable, primary := false) -> Button:
	var node := Button.new()
	node.text = text
	node.custom_minimum_size.y = 40
	if primary:
		var style := StyleBoxFlat.new()
		style.bg_color = RED
		style.set_corner_radius_all(4)
		node.add_theme_stylebox_override("normal", style)
		var hover := style.duplicate()
		hover.bg_color = Color("d9304c")
		node.add_theme_stylebox_override("hover", hover)
	node.pressed.connect(callback)
	form.add_child(node)
	return node

func _field(key: String, placeholder: String, secret := false, submit := Callable()) -> LineEdit:
	var edit := LineEdit.new()
	edit.placeholder_text = placeholder
	edit.secret = secret
	edit.max_length = 64 if key == "invite" else (128 if secret else 16)
	edit.custom_minimum_size.y = 38
	if submit.is_valid():
		edit.text_submitted.connect(func(_text): submit.call())
	form.add_child(edit)
	fields[key] = edit
	return edit

func _reset(text := "") -> void:
	fields.clear()
	for child in form.get_children():
		form.remove_child(child)
		child.queue_free()
	_say(text)

func _say(text: String) -> void:
	notice.text = text

func _value(key: String) -> String:
	return fields[key].text.strip_edges() if fields.has(key) else ""

func show_login(text := "") -> void:
	_reset(text)
	var who := _field("name", "Nombre", false, _login)
	_field("password", "Contraseña", true, _login)
	_button("Entrar", _login, true)
	_button("Crear una cuenta nueva", show_register)
	_button("Salir", func(): get_tree().quit())
	if not ServerConnection.account_name.is_empty():
		who.text = ServerConnection.account_name
	who.grab_focus()

func show_register(text := "") -> void:
	_reset(text)
	_field("name", "Nombre (3 a 16 letras o números)").grab_focus()
	_field("password", "Contraseña (6 caracteres o más)", true)
	_field("repeat", "Repite la contraseña", true)
	_field("invite", "Código de invitación", false, _register)
	_button("Crear cuenta", _register, true)
	_button("Ya tengo cuenta", show_login)

func show_menu(text := "") -> void:
	_reset(text)
	var who := Label.new()
	who.text = "Sesión: " + str(me.get("name", ServerConnection.account_name))
	who.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	form.add_child(who)
	_button("Continuar", _enter, true).grab_focus()
	if bool(me.get("has_password", true)):
		_button("Cambiar contraseña", show_password)
	else:
		_button("Ponle una contraseña a tu cuenta", show_password)
		if text.is_empty():
			_say("Tu cuenta aún no tiene contraseña. Ponle una para poder entrar desde cualquier PC.")
	_button("Cerrar sesión", _logout)
	_button("Salir", func(): get_tree().quit())

func _logout() -> void:
	ServerConnection.clear_session()
	show_login("Has cerrado la sesión en este PC.")

func show_password(text := "") -> void:
	_reset(text)
	if bool(me.get("has_password", false)):
		_field("current", "Contraseña actual", true).grab_focus()
	_field("new", "Contraseña nueva (6 caracteres o más)", true)
	_field("repeat", "Repite la contraseña nueva", true, _save_password)
	_button("Guardar", _save_password, true)
	_button("Volver", show_menu)

func _login() -> void:
	if _value("name").is_empty() or fields["password"].text.is_empty():
		_say("Escribe tu nombre y tu contraseña.")
		return
	_call("login", HTTPClient.METHOD_POST, "/api/v1/auth/login", {"name": _value("name"), "password": fields["password"].text})

func _register() -> void:
	if fields["password"].text != fields["repeat"].text:
		_say("Las contraseñas no coinciden.")
		return
	_call("register", HTTPClient.METHOD_POST, "/api/v1/auth/register",
		{"name": _value("name"), "password": fields["password"].text, "invite": _value("invite")})

func _save_password() -> void:
	if fields["new"].text != fields["repeat"].text:
		_say("Las contraseñas no coinciden.")
		return
	var current: String = fields["current"].text if fields.has("current") else ""
	_call("password", HTTPClient.METHOD_POST, "/api/v1/auth/password", {"current": current, "new": fields["new"].text})

func _check_session() -> void:
	_reset("Comprobando tu sesión...")
	_call("me", HTTPClient.METHOD_GET, "/api/v1/auth/me", {})

func _call(kind: String, method: int, path: String, body: Dictionary) -> void:
	if not pending.is_empty():
		return
	pending = kind
	for child in form.get_children():
		if child is Button: child.disabled = true
	_say("Conectando...")
	var payload := "" if method == HTTPClient.METHOD_GET else JSON.stringify(body)
	var error := request.request(ServerConnection.base_url() + path, ServerConnection.account_headers(), method, payload)
	if error != OK:
		_completed(HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray())

func _completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var kind := pending
	pending = ""
	for child in form.get_children():
		if child is Button: child.disabled = false
	var payload = JSON.parse_string(body.get_string_from_utf8()) if body.size() > 0 else null
	if result != HTTPRequest.RESULT_SUCCESS or typeof(payload) != TYPE_DICTIONARY:
		var offline := "No se pudo conectar con el mundo. Revisa tu conexión a Internet."
		if kind == "me":
			_reset(offline)
			_button("Reintentar", _check_session, true)
			_button("Salir", func(): get_tree().quit())
		else:
			_say(offline)
		return
	if code < 200 or code >= 300:
		var detail := str(payload.get("detail", ""))
		if kind == "me" and code == 401:
			ServerConnection.clear_session()
			show_login(ERRORS["INVALID_PLAYER_ACCESS"])
			return
		var text: String = ERRORS.get(detail, "El servidor no aceptó la petición (" + detail + ").")
		if kind == "me":
			_reset(text)
			_button("Reintentar", _check_session, true)
			_button("Cerrar sesión", _logout)
			_button("Salir", func(): get_tree().quit())
		else:
			_say(text)
		return
	match kind:
		"me":
			me = payload
			ServerConnection.set_session(ServerConnection.session_token(), str(payload.get("name", "")))
			show_menu()
		"login", "register":
			ServerConnection.set_session(str(payload.get("token", "")), str(payload.get("name", "")))
			me = {"name": payload.get("name", ""), "has_password": true}
			if kind == "register":
				show_menu("Cuenta creada. Bienvenido a la Wired, " + str(payload.get("name", "")) + ".")
			else:
				_enter()
		"password":
			me = payload
			show_menu("Contraseña guardada. Ya puedes entrar desde cualquier PC.")

func _enter() -> void:
	ServerConnection.finish_login()
	if menu != null:
		menu.hide()
	status.show()
	status.text = "CONECTANDO AL MUNDO COMPARTIDO..."
	WorldApi.request_state()

func _on_snapshot_updated(snapshot: Dictionary) -> void:
	var origin: Dictionary = snapshot.get("prologue", {})
	if bool(origin.get("enabled", false)) and str(origin.get("stage", "")) != "CONNECTED":
		status.text = "SISTEMA LOCAL DISPONIBLE // SIN CONEXIÓN A LA WIRED"
	else:
		status.text = "WORLD CORE SYNCHRONIZED"

func _on_api_error(message: String) -> void:
	status.text = "CONNECTION FAILED\n\n" + message
