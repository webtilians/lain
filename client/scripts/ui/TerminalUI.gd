extends CanvasLayer

@onready var sender_label: Label = $Background/Window/Margin/VBox/Sender
@onready var subject_label: Label = $Background/Window/Margin/VBox/Subject
@onready var body_label: Label = $Background/Window/Margin/VBox/Body
@onready var status_label: Label = $Background/Window/Margin/VBox/Status
@onready var connect_button: Button = $Background/Window/Margin/VBox/Connect
@onready var mail_button: Button = $Background/Window/Margin/VBox/Tabs/Mail
@onready var wired_button: Button = $Background/Window/Margin/VBox/Tabs/Wired

var current_message_id := ""
var mode := "MAIL"

func _ready() -> void:
	visible = false
	connect_button.pressed.connect(_on_connect_pressed)
	mail_button.pressed.connect(_show_mail)
	wired_button.pressed.connect(_show_wired)
	WorldApi.snapshot_updated.connect(_on_snapshot_updated)

func open_terminal() -> void:
	visible = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var player = get_tree().get_first_node_in_group("player")
	if player != null:
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
	_render_snapshot(WorldApi.snapshot)

func close_terminal() -> void:
	visible = false
	var player = get_tree().get_first_node_in_group("player")
	if player != null:
		player.set_physics_process(true)
		player.set_process_unhandled_input(true)
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("ui_cancel"):
		close_terminal()
		get_viewport().set_input_as_handled()

func _on_snapshot_updated(next_snapshot: Dictionary) -> void:
	if visible:
		_render_snapshot(next_snapshot)

func _render_snapshot(next_snapshot: Dictionary) -> void:
	var wired: Dictionary = next_snapshot.get("wired", {})
	wired_button.visible = bool(wired.get("connected", false))
	if mode == "WIRED":
		_render_wired(next_snapshot)
	else:
		_render_mail(next_snapshot)

func _render_mail(next_snapshot: Dictionary) -> void:
	mode = "MAIL"
	var messages: Array = next_snapshot.get("messages", [])
	if messages.is_empty():
		current_message_id = ""
		sender_label.text = "FROM: ---"
		subject_label.text = "SUBJECT: NO MAIL"
		body_label.text = ""
		status_label.text = "INBOX EMPTY"
		connect_button.visible = false
		return

	var message: Dictionary = messages[0]
	current_message_id = str(message.get("id", ""))
	sender_label.text = "FROM: %s" % message.get("sender", "UNKNOWN")
	subject_label.text = "SUBJECT: %s" % message.get("subject", "")
	body_label.text = str(message.get("body", ""))

	if bool(message.get("acknowledged", false)):
		status_label.text = "CONNECTION ACCEPTED"
		connect_button.text = "CONNECTED"
		connect_button.disabled = true
	else:
		status_label.text = "INCOMING CONNECTION"
		connect_button.text = "CONNECT"
		connect_button.disabled = false

	connect_button.visible = true

func _render_wired(next_snapshot: Dictionary) -> void:
	mode = "WIRED"
	sender_label.text = "THE WIRED"
	subject_label.text = "REMOTE SIGNALS"
	connect_button.visible = false

	var wired: Dictionary = next_snapshot.get("wired", {})
	var signals: Array = wired.get("signals", [])
	if signals.is_empty():
		body_label.text = "NO SIGNALS DETECTED"
		status_label.text = "CONNECTED"
		return

	var lines: Array[String] = []
	for signal_data in signals:
		lines.append(str(signal_data.get("node_id", "UNKNOWN")))
		lines.append("LOCATION // %s" % signal_data.get("location", "UNKNOWN"))
		lines.append("SIGNAL // %.2f" % float(signal_data.get("strength", 0.0)))
		lines.append("CONFIDENCE // %.0f%%" % (float(signal_data.get("confidence", 0.0)) * 100.0))
		lines.append("")

	body_label.text = "\n".join(lines)
	status_label.text = "SOURCE // UNKNOWN"

func _show_mail() -> void:
	mode = "MAIL"
	_render_mail(WorldApi.snapshot)

func _show_wired() -> void:
	mode = "WIRED"
	_render_wired(WorldApi.snapshot)

func _on_connect_pressed() -> void:
	if current_message_id.is_empty():
		return
	connect_button.disabled = true
	status_label.text = "CONNECTING..."
	WorldApi.acknowledge_message(current_message_id)
