extends "res://tools/test_city08.gd"
const RESIDENTS = preload("res://scripts/world/ResidentLayout.gd")

func run() -> void:
	var paths: Dictionary = load("res://scripts/core/SceneRouter.gd").LOCATION_SCENES
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var catalog: Array = JSON.parse_string(FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://../server/world_core/data/residents09.json")))
	check(catalog.size()>=50,"fewer than 50 citizens")
	for location in ["APARTMENT_DISTRICT","SCHOOL","SCHOOL_LAB","NIGHTCLUB","STATION","IZAKAYA","GROCERY","VIDEO_CLUB","BOOKSHOP","ARCADE","CAFE"]:
		var actors: Array = []
		for item in catalog:
			if item.location == location:
				actors.append({"id":item.id,"name":item.name,"slot":item.slot,"patrol_step":0,"activity":item.activities[0],"appearance":item.appearance})
		api.snapshot = {"minute":0,"player":{"location":location,"energy":1.0},"known_nodes":[],"visible_actors":actors}
		scene = load(paths[location]).instantiate()
		root.add_child(scene)
		current_scene = scene
		player = scene.get_node("Player")
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		await physics_frame
		await physics_frame
		var spawner: Node3D = scene.get_node("Actors")
		check(spawner.rendered_actors.size()==actors.size(),location+" did not render all residents")
		for actor in actors:
			# Probe a player-sized capsule through all four authored segments.
			player.position = RESIDENTS.at(location,actor.slot,0)+Vector3(0,.91,0)
			var query := PhysicsShapeQueryParameters3D.new()
			query.shape = player.get_node("Collision").shape
			query.transform = player.global_transform
			query.exclude = [player.get_rid()]
			var hits := scene.get_world_3d().direct_space_state.intersect_shape(query)
			check(hits.is_empty(),str(actor.id)+" origin blocked: "+str(player.position))
			for step in range(1,5):
				await walk([RESIDENTS.at(location,actor.slot,step%4)+Vector3(0,.91,0)],str(actor.id)+" step"+str(step))
		if location == "APARTMENT_DISTRICT":
			for shop in ["BOOKSHOP","GROCERY","VIDEO_CLUB","CAFE","IZAKAYA","ARCADE"]:
				player.position = Vector3(LAYOUT.ENTRIES[shop].x,.91,12 if shop in ["BOOKSHOP","GROCERY"] else (-41 if shop in ["VIDEO_CLUB","CAFE"] else -76))
				await walk([LAYOUT.ENTRIES[shop]],shop+" entrance")
				door(shop)
		else:
			var exit_target := "SCHOOL" if location=="SCHOOL_LAB" else "APARTMENT_DISTRICT"
			if location != "STATION":
				check(scene.has_node("Door_"+exit_target),location+" missing return door")
		# Same snapshot never advances a resident. Changed server waypoint does.
		if not actors.is_empty():
			var first_id: String = actors[0].id
			var first: Node3D = spawner.rendered_actors[first_id]
			var start: Vector3 = first.position
			spawner._sync_actors(api.snapshot)
			check(first.position.is_equal_approx(start),"polling invented local movement")
			actors[0].patrol_step=1
			spawner._sync_actors(api.snapshot)
			await create_timer(2.0).timeout
			check(first.global_position.distance_to(RESIDENTS.at(location,actors[0].slot,1))<.02,"accepted waypoint not animated")
		print("CITY09_LOCATION_PASS ",location," residents=",actors.size())
		scene.queue_free()
		await process_frame
	if not failed:
		print("CITY09_RESIDENTS_PASS population=56 shops=6")
	quit(1 if failed else 0)
