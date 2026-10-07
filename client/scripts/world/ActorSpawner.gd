extends Node3D

const ACTOR_INTERACTABLE = preload(
	"res://scripts/world/ActorInteractable.gd"
)

@export var location_id: String = ""

@onready var spawns: Node3D = $Spawns

var rendered_actors: Dictionary = {}
var patrol_steps: Dictionary = {}
var movement_tweens: Dictionary = {}
const RESIDENT_LAYOUT = preload("res://scripts/world/ResidentLayout.gd")

const LOCAL_PATROL_OFFSETS := [
	Vector3(0.0, 0.0, 0.0),
	Vector3(0.65, 0.0, 0.0),
	Vector3(0.65, 0.0, 0.55),
	Vector3(0.0, 0.0, 0.55),
]

func _exit_tree() -> void:
	for tween in movement_tweens.values():
		if tween != null and tween.is_running():
			tween.kill()


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
	var echo_index := 0
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
		var next_patrol_step := int(actor_data.get("patrol_step", 0)) % 4
		if actor_id.begins_with("RESIDENT_"):
			spawn_position = RESIDENT_LAYOUT.at(location_id, int(actor_data.get("slot", 0)), next_patrol_step)
		elif actor_id.begins_with("ECHO_"):
			# Beside one of the residents' places, a different one for each echo.
			spawn_position = RESIDENT_LAYOUT.at(location_id, echo_index % 3, 0) + Vector3(1.1, 0, 0.8)
			echo_index += 1
		elif actor_id.begins_with("ENTITY_"):
			var anchor := spawns.get_node_or_null("ENTITY_ANCHOR") as Node3D
			if anchor == null or generated_index >= 8:
				continue
			spawn_position = anchor.global_position + Vector3(
				float(generated_index % 2) * 1.4,
				0.0,
				-float(generated_index / 2) * 1.7
			) + LOCAL_PATROL_OFFSETS[next_patrol_step]
			generated_index += 1
		elif marker != null:
			spawn_position = marker.global_position
		else:
			continue

		present[actor_id] = true

		if not rendered_actors.has(actor_id):
			var actor := _create_actor(
				actor_id,
				str(actor_data.get("name", actor_id)), actor_data
			)
			add_child(actor)
			rendered_actors[actor_id] = actor
			patrol_steps[actor_id] = next_patrol_step
			actor.global_position = spawn_position
			var body := actor.get_node_or_null("CitizenBody")
			if body != null:
				body.last_position = spawn_position
			continue

		var representation: Node3D = (
			rendered_actors[actor_id] as Node3D
		)

		if (actor_id.begins_with("ENTITY_") or actor_id.begins_with("RESIDENT_")) and (
			int(patrol_steps.get(actor_id, 0)) != next_patrol_step
		):
			# Animate only an ACCEPTED World Core WANDER. Polling the same
			# snapshot never creates movement or changes the server's state.
			patrol_steps[actor_id] = next_patrol_step
			if movement_tweens.has(actor_id):
				var previous: Tween = movement_tweens[actor_id]
				if previous.is_running():
					previous.kill()
			var tween := create_tween()
			tween.tween_property(
				representation, "global_position", spawn_position, 1.8
			).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
			movement_tweens[actor_id] = tween
		elif not actor_id.begins_with("ENTITY_") and not actor_id.begins_with("RESIDENT_"):
			representation.global_position = spawn_position
		var activity_label := representation.get_node_or_null("Activity") as Label3D
		if activity_label != null and not representation.has_meta("echo"):
			activity_label.text = str(actor_data.get("activity", ""))

	for actor_id in rendered_actors.keys():
		if present.has(actor_id):
			continue

		var actor: Node3D = (
			rendered_actors[actor_id] as Node3D
		)

		if is_instance_valid(actor):
			actor.queue_free()

		rendered_actors.erase(actor_id)
		patrol_steps.erase(actor_id)
		if movement_tweens.has(actor_id):
			var previous: Tween = movement_tweens[actor_id]
			if previous.is_running():
				previous.kill()
			movement_tweens.erase(actor_id)

func _process(_delta: float) -> void:
	# Echoes flicker now and then, like a signal that keeps dropping.
	for actor in rendered_actors.values():
		if is_instance_valid(actor) and actor.has_meta("echo_meshes"):
			var amount := 0.85 if randf() < 0.03 else 0.55
			for mesh in actor.get_meta("echo_meshes"):
				if is_instance_valid(mesh):
					mesh.transparency = amount

func _create_actor(
	actor_id: String,
	actor_name: String,
	data: Dictionary = {}
) -> Node3D:
	var actor := Node3D.new()
	actor.name = actor_id
	actor.set_script(ACTOR_INTERACTABLE)
	actor.set("actor_id", actor_id)
	actor.set("actor_name", actor_name)
	actor.set_meta("who", str(data.get("who", "")))  # their lines in the zone chat show over this head

	# Visuals only. Authority, visibility and dialogue remain in World Core.
	if actor_id.begins_with("RESIDENT_"):
		var model: Node3D = load("res://art/characters/LainSlender.tscn").instantiate()
		model.set_script(load("res://scripts/art/CitizenAvatar.gd"))
		model.configure(str(data.get("appearance","casual")), int(actor_id.get_slice("_",1)))
		actor.add_child(model)
		var activity := Label3D.new()
		activity.name = "Activity"
		activity.text = str(data.get("activity",""))
		activity.position.y = 2.24
		activity.font_size = 24
		activity.pixel_size = 0.007
		activity.modulate = Color("b8b7ac")
		activity.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		actor.add_child(activity)
	elif actor_id.begins_with("ECHO_"):
		# What is left of a closed session: a citizen's shape, translucent and cold.
		var model: Node3D = load("res://art/characters/LainSlender.tscn").instantiate()
		model.set_script(load("res://scripts/art/CitizenAvatar.gd"))
		model.configure("casual", absi(actor_id.hash()) % 50)
		actor.add_child(model)
		var meshes: Array = model.find_children("*", "GeometryInstance3D", true, false)
		for mesh in meshes:
			mesh.transparency = 0.55
		actor.set_meta("echo_meshes", meshes)
		var tint := OmniLight3D.new()
		tint.light_color = Color("7fd6e0")
		tint.light_energy = 0.6
		tint.omni_range = 1.8
		tint.position.y = 1.2
		actor.add_child(tint)
		var echo_label := Label3D.new()
		echo_label.name = "Activity"
		echo_label.text = "eco · lo que queda de una sesión"
		echo_label.position.y = 2.24
		echo_label.font_size = 24
		echo_label.pixel_size = 0.007
		echo_label.modulate = Color("8fe3ec")
		echo_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		actor.add_child(echo_label)
		actor.set_meta("echo", true)
	elif actor_id.begins_with("ENTITY_"):
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
	name_label.name = "NameLabel"
	name_label.text = actor_name
	name_label.position = Vector3(0.0, 1.9, 0.0)
	name_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	name_label.font_size = 32
	name_label.pixel_size = 0.008
	actor.add_child(name_label)

	return actor
