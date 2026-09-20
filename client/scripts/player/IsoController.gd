extends CharacterBody3D

@export var move_speed: float = 3.5
@export var acceleration: float = 20.0
@export var interaction_distance: float = 2.3

const CAMERA_OFFSET := Vector3(
	10.0,
	12.0,
	10.0
)

@onready var camera: Camera3D = (
	$Head/Camera3D
)

var gravity: float = (
	ProjectSettings.get_setting(
		"physics/3d/default_gravity"
	)
)

# ==================================================
# CAMERA
# ==================================================

func _ready() -> void:
	add_to_group("player")

	Input.mouse_mode = (
		Input.MOUSE_MODE_VISIBLE
	)

	camera.top_level = true

	camera.projection = (
		Camera3D.PROJECTION_ORTHOGONAL
	)

	camera.size = 12.0

	_update_camera()

	camera.look_at(
		global_position
		+ Vector3(0.0, 0.6, 0.0),
		Vector3.UP
	)

	print(
		"ISO CONTROLLER ACTIVE"
	)

func _update_camera() -> void:
	camera.global_position = (
		global_position
		+ CAMERA_OFFSET
	)

# ==================================================
# MOVEMENT
# ==================================================

func _physics_process(
	delta: float
) -> void:
	if not is_on_floor():
		velocity.y -= gravity * delta
	elif velocity.y < 0.0:
		velocity.y = 0.0

	var input_vector := Input.get_vector(
		"move_left",
		"move_right",
		"move_forward",
		"move_backward"
	)

	var right := (
		camera.global_transform.basis.x
	)

	var forward := (
		-camera.global_transform.basis.z
	)

	right.y = 0.0
	forward.y = 0.0

	right = right.normalized()
	forward = forward.normalized()

	var direction := (
		right * input_vector.x
		- forward * input_vector.y
	).normalized()

	velocity.x = move_toward(
		velocity.x,
		direction.x * move_speed,
		acceleration * delta
	)

	velocity.z = move_toward(
		velocity.z,
		direction.z * move_speed,
		acceleration * delta
	)

	move_and_slide()

	_update_camera()

# ==================================================
# INTERACTION
# ==================================================

func _unhandled_input(
	event: InputEvent
) -> void:
	if event.is_action_pressed(
		"interact"
	):
		_try_interaction()
		get_viewport().set_input_as_handled()

func _try_interaction() -> void:
	var nearest: Node3D = null
	var nearest_distance := interaction_distance

	for candidate in (
		get_tree().get_nodes_in_group(
			"interactable"
		)
	):
		if not candidate is Node3D:
			continue

		if not candidate.has_method(
			"interact"
		):
			continue

		var distance := (
			global_position.distance_to(
				candidate.global_position
			)
		)

		if distance > nearest_distance:
			continue

		nearest = candidate
		nearest_distance = distance

	if nearest == null:
		print(
			"ISO // NO INTERACTABLE NEARBY"
		)
		return

	print(
		"ISO // INTERACT -> ",
		nearest.name
	)

	nearest.interact()
