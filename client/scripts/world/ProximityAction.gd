extends Area3D

@export var action := ""
@export var target := ""
@export var prompt := "E // INTERACT"

var player_inside := false
var busy := false

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)
	WorldApi.snapshot_updated.connect(_on_snapshot_updated)
	WorldApi.api_error.connect(_on_api_error)

func _on_body_entered(body: Node3D) -> void:
	if body.is_in_group("player"):
		player_inside = true

func _on_body_exited(body: Node3D) -> void:
	if body.is_in_group("player"):
		player_inside = false

func _unhandled_input(event: InputEvent) -> void:
	if not player_inside or busy:
		return
	if not event.is_action_pressed("interact"):
		return

	busy = true
	WorldApi.step(action, target)
	get_viewport().set_input_as_handled()

func _on_snapshot_updated(_snapshot: Dictionary) -> void:
	busy = false

func _on_api_error(_message: String) -> void:
	busy = false
