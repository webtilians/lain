extends Node3D

const ACTOR_INTERACTABLE = preload(
	"res://scripts/world/ActorInteractable.gd"
)

@export var location_id: String = ""

@onready var spawns: Node3D = $Spawns

var rendered_actors: Dictionary = {}

func _ready() -> void:
	WorldApi.snapshot_updated.connect(
		_sync_actors
	)

	_sync_actors(
		WorldApi.snapshot
	)

func _sync_actors(
	snapshot: Dictionary
) -> void:
	if snapshot.is_empty():
		return

	var player_data: Dictionary = snapshot.get(
		"player",
		{}
	)

	if str(
		player_data.get(
			"location",
			""
		)
	) != location_id:
		return

	var present: Dictionary = {}
	var actors: Array = snapshot.get(
		"visible_actors",
		[]
	)

	# Dynamic identities have no pre-authored marker; stable ordering gives
	# them reproducible slots without altering K/Nora's existing scenes.
	var generated_index := 0
	for actor_data in actors:
		if typeof(actor_data) != TYPE_DICTIONARY:
			continue

		var actor_id := str(
			actor_data.get(
				"id",
				""
			)
		)

		if actor_id.is_empty():
			continue

		var marker := spawns.get_node_or_null(
			actor_id
		) as Node3D
		var spawn_position := Vector3.ZERO
		if actor_id.begins_with("ENTITY_"):
			var anchor := spawns.get_node_or_null("ENTITY_ANCHOR") as Node3D
			if anchor == null or generated_index >= 8:
				continue
			spawn_position = anchor.global_position + Vector3(
				float(generated_index % 2) * 1.4,
				0.0,
				-float(generated_index / 2) * 1.7
			)
			generated_index += 1
		elif marker != null:
			spawn_position = marker.global_position
		else:
			continue

		present[actor_id] = true

		if not rendered_actors.has(actor_id):
			var actor := _create_actor(
				actor_id,
				str(actor_data.get("name", actor_id))
			)
			add_child(actor)
			rendered_actors[actor_id] = actor

		var representation: Node3D = (
			rendered_actors[actor_id] as Node3D
		)

		representation.global_position = spawn_position

	for actor_id in rendered_actors.keys():
		if present.has(actor_id):
			continue

		var actor: Node3D = (
			rendered_actors[actor_id] as Node3D
		)

		if is_instance_valid(actor):
			actor.queue_free()

		rendered_actors.erase(actor_id)

func _create_actor(
	actor_id: String,
	actor_name: String
) -> Node3D:
	var actor := Node3D.new()
	actor.name = actor_id
	actor.set_script(ACTOR_INTERACTABLE)
	actor.set("actor_id", actor_id)
	actor.set("actor_name", actor_name)

	# Visuals only. Authority, visibility and dialogue remain in World Core.
	if actor_id.begins_with("ENTITY_"):
		var digital_body := MeshInstance3D.new()
		digital_body.name = "DigitalBody"
		var mesh := CapsuleMesh.new()
		mesh.radius = 0.24
		mesh.height = 1.45
		digital_body.mesh = mesh
		digital_body.position.y = 0.75
		var material := StandardMaterial3D.new()
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.albedo_color = Color(0.40, 0.83, 0.84, 0.62)
		material.emission_enabled = true
		material.emission = Color(0.16, 0.53, 0.59)
		material.emission_energy_multiplier = 0.75
		digital_body.material_override = material
		actor.add_child(digital_body)
	else:
		var model_path := (
			"res://art/characters/AgentK.tscn"
			if actor_id == "AGENT_K"
			else "res://art/characters/Nora.tscn"
		)
		var model: Node3D = load(model_path).instantiate()
		actor.add_child(model)

	var name_label := Label3D.new()
	name_label.text = actor_name
	name_label.position = Vector3(0.0, 1.9, 0.0)
	name_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	name_label.font_size = 32
	name_label.pixel_size = 0.005
	actor.add_child(name_label)

	return actor
