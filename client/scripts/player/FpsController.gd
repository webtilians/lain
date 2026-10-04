extends CharacterBody3D

@export var move_speed := 3.2
@export var acceleration := 14.0
@export var mouse_sensitivity := 0.0022
@export var interaction_distance := 4.0

@onready var head: Node3D = $Head
@onready var interaction_ray: RayCast3D = (
	$Head/Camera3D/InteractionRay
)

var gravity: float = (
	ProjectSettings.get_setting(
		"physics/3d/default_gravity"
	)
)

func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _unhandled_input(
	event: InputEvent
) -> void:
	if (
		event is InputEventMouseMotion
		and
		Input.mouse_mode
		== Input.MOUSE_MODE_CAPTURED
	):
		rotate_y(
			-event.relative.x
			* mouse_sensitivity
		)

		head.rotate_x(
			-event.relative.y
			* mouse_sensitivity
		)

		head.rotation.x = clamp(
			head.rotation.x,
			deg_to_rad(-80.0),
			deg_to_rad(80.0)
		)

	if event.is_action_pressed(
		"ui_cancel"
	):
		if (
			Input.mouse_mode
			== Input.MOUSE_MODE_CAPTURED
		):
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		else:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

	if event.is_action_pressed(
		"interact"
	):
		_try_interaction()

func _physics_process(
	delta: float
) -> void:
	if not is_on_floor():
		velocity.y -= gravity * delta

	var input_vector := Input.get_vector(
		"move_left",
		"move_right",
		"move_forward",
		"move_backward"
	)

	var direction := (
		transform.basis
		*
		Vector3(
			input_vector.x,
			0.0,
			input_vector.y
		)
	)

	direction.y = 0.0
	direction = direction.normalized()

	var desired_x := direction.x * move_speed
	var desired_z := direction.z * move_speed

	velocity.x = move_toward(
		velocity.x,
		desired_x,
		acceleration * delta
	)

	velocity.z = move_toward(
		velocity.z,
		desired_z,
		acceleration * delta
	)

	move_and_slide()

func _try_interaction() -> void:
	interaction_ray.force_raycast_update()

	if interaction_ray.is_colliding():
		var collider = interaction_ray.get_collider()
		if (
			collider != null
			and collider.has_method("interact")
		):
			print("RAY INTERACTION: ", collider.name)
			collider.interact()
			return

	var nearest: Node3D = null
	var nearest_distance := interaction_distance
	var interactables := get_tree().get_nodes_in_group(
		"interactable"
	)

	for candidate in interactables:
		if not candidate is Node3D:
			continue

		var distance := global_position.distance_to(
			candidate.global_position
		)
		if distance > nearest_distance:
			continue

		nearest = candidate
		nearest_distance = distance

	if nearest == null:
		print(
			"NO INTERACTABLE WITHIN ",
			interaction_distance,
			" METERS"
		)
		return

	print(
		"PROXIMITY INTERACTION: ",
		nearest.name,
		" DISTANCE: ",
		nearest_distance
	)

	if nearest.has_method("interact"):
		nearest.interact()
