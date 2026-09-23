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

		if marker == null:
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

		representation.global_position = (
			marker.global_position
		)

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

	# Visuals only; visibility, identity and dialogue still come from World Core.
	var model_path := "res://art/characters/AgentK.tscn" if actor_id == "AGENT_K" else "res://art/characters/Nora.tscn"
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
