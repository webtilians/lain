extends CanvasLayer

@onready var sender_label: Label = (
	$Background/Window/Margin/VBox/Sender
)
@onready var subject_label: Label = (
	$Background/Window/Margin/VBox/Subject
)
@onready var body_label: Label = (
	$Background/Window/Margin/VBox/Body
)
@onready var status_label: Label = (
	$Background/Window/Margin/VBox/Status
)
@onready var connect_button: Button = (
	$Background/Window/Margin/VBox/Connect
)

var current_message_id := ""

func _ready() -> void:
	visible = false
	connect_button.pressed.connect(_on_connect_pressed)
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
	if not visible:
		return
	_render_snapshot(next_snapshot)

func _render_snapshot(next_snapshot: Dictionary) -> void:
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
	sender_label.text = "FROM: %s" % str(message.get("sender", "UNKNOWN"))
	subject_label.text = "SUBJECT: %s" % str(message.get("subject", ""))
	body_label.text = str(message.get("body", ""))

	var acknowledged := bool(message.get("acknowledged", false))
	if acknowledged:
		status_label.text = "CONNECTION ACCEPTED"
		connect_button.text = "CONNECTED"
		connect_button.disabled = true
	else:
		status_label.text = "INCOMING CONNECTION"
		connect_button.text = "CONNECT"
		connect_button.disabled = false

	connect_button.visible = true

func _on_connect_pressed() -> void:
	if current_message_id.is_empty():
		return

	connect_button.disabled = true
	status_label.text = "CONNECTING..."
	WorldApi.acknowledge_message(current_message_id)
