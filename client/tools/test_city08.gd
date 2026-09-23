extends SceneTree
## Real collision/navigation and presentation regression. Never touches the server.
const LAYOUT = preload("res://scripts/world/CityLayout.gd")
var failed := false
var scene: Node3D
var player: CharacterBody3D

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error("CITY08 // " + message)

func walk(points: Array[Vector3], label: String) -> void:
	# CharacterBody sweep uses production shapes; each segment is <18cm.
	for target in points:
		var attempts := 0
		while Vector2(player.position.x-target.x,player.position.z-target.z).length() > 0.03:
			var offset := target-player.position
			offset.y = 0
			var motion := offset.normalized()*minf(offset.length(),0.18)
			var collision := player.move_and_collide(motion)
			attempts += 1
			if collision != null or attempts > 1600:
				check(false,label+" blocked at "+str(player.position)+" toward "+str(target))
				return
		player._update_camera()
		await physics_frame
	print("CITY08_ROUTE ",label)

func door(target: String) -> void:
	var node: Node3D = scene.get_node("PrologueEntrances/Entrance_"+target)
	check(node.is_in_group("interactable"),target+" not interactive")
	check(node.target_location == target,target+" changed semantic route")
	check(player.position.distance_to(node.global_position) < player.interaction_distance,
		target+" outside interaction range")

func run() -> void:
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	api.snapshot = {"minute":0,"player":{"location":"APARTMENT_DISTRICT","energy":1.0},"known_nodes":[],"visible_actors":[]}
	for name_value in ["EventDialog","CharacterJournal","PrologueTerminal"]:
		root.get_node(name_value).set_process_unhandled_input(false)
		root.get_node(name_value).set_process_unhandled_key_input(false)
	scene = load("res://scenes/apartment_district/ApartmentDistrict.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	player = scene.get_node("Player")
	player.set_physics_process(false)
	player.set_process_unhandled_input(false)
	await physics_frame
	await physics_frame
	# Explicit serialized buffers catch the dummy-renderer empty-art regression,
	# even on CI where the headless renderer cannot read MultiMesh transforms.
	var saved := FileAccess.get_file_as_string("res://art/city08/Neighborhood.tscn")
	check(saved.count("buffer = PackedFloat32Array(") > 100,"Art is missing serialized transforms")
	var art: Node3D = scene.get_node("CityArt")
	check(art.get_node("School").bounds.size.x > 10,"School is absent")
	check(scene.get_node_or_null("HUD/NeighborhoodMap") != null,"Public map missing")
	door("APARTMENT")
	await walk([Vector3(0,0.91,5.7),Vector3(0,0.91,-16),Vector3(-18,0.91,-16),LAYOUT.ENTRIES.SCHOOL],"home-school")
	door("SCHOOL")
	await walk([Vector3(-18,0.91,-16),Vector3(0,0.91,-16),Vector3(0,0.91,-41),Vector3(29,0.91,-41),Vector3(29,0.91,-65),LAYOUT.ENTRIES.NIGHTCLUB],"school-club")
	door("NIGHTCLUB")
	await walk([Vector3(29,0.91,-65),Vector3(29,0.91,-76),Vector3(0,0.91,-76),LAYOUT.ENTRIES.STATION],"club-station")
	door("STATION")
	await walk([Vector3(0,0.91,-102),Vector3(-29,0.91,-102),Vector3(-29,0.91,-16),Vector3(0,0.91,-16),Vector3(0,0.91,5.7),LAYOUT.ENTRIES.APARTMENT],"west-loop-home")
	door("APARTMENT")
	# All visible generated identities get safe, nonoverlapping sidewalk slots.
	for index in range(8):
		api.snapshot.visible_actors.append({"id":"ENTITY_CITY_"+str(index),"name":"Test","patrol_step":index%4})
	api.snapshot_updated.emit(api.snapshot)
	await process_frame
	var spawner: Node3D = scene.get_node("Actors")
	check(spawner.rendered_actors.size()==8,"Generated actors lost in new district")
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.3
	capsule.height = 1.6
	for actor in spawner.rendered_actors.values():
		var query := PhysicsShapeQueryParameters3D.new()
		query.shape = capsule
		query.transform = Transform3D(Basis.IDENTITY,actor.global_position+Vector3(0,0.85,0))
		check(scene.get_world_3d().direct_space_state.intersect_shape(query).is_empty(),"Generated actor spawned in scenery")
	# A foreground building reveals the avatar, then restores its intact facade.
	player.position = Vector3(4.6,0.91,3)
	player._update_camera()
	await create_timer(0.2).timeout
	check(not art.get_node("CornerBooks/Upper").visible,"Camera obstruction not cut away")
	player.position = Vector3(4.6,0.91,10)
	player._update_camera()
	await create_timer(0.2).timeout
	check(art.get_node("CornerBooks/Upper").visible,"Cutaway never restores")
	# Return points are a presentation-only projection and remain clear of solids.
	for origin in LAYOUT.ENTRIES:
		root.get_node("SceneRouter").entry_from_location = origin
		scene._ready()
		check(player.position.is_equal_approx(LAYOUT.ENTRIES[origin]),"Wrong return point: "+origin)
		door(origin)
		var query := PhysicsShapeQueryParameters3D.new()
		query.shape = player.get_node("Collision").shape
		query.transform = player.global_transform
		query.exclude = [player.get_rid()]
		check(scene.get_world_3d().direct_space_state.intersect_shape(query).is_empty(),"Return point overlaps scenery: "+origin)
	print("CITY08_CHECK_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
