extends SceneTree
## Offline, non-rendering geometry regression. Does not touch any save.
var failed: bool = false


func _initialize() -> void:
	call_deferred("_run")


func check(condition: bool, reason: String) -> void:
	if not condition:
		failed = true
		push_error("VISUAL07_ENVIRONMENT // " + reason)


func _run() -> void:
	var api = root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	api.snapshot = {
		"player": {"id": "PLAYER_1", "location": "APARTMENT_DISTRICT"},
		"visible_actors": [], "minute": 0,
	}
	var street: Node3D = load(
		"res://scenes/apartment_district/ApartmentDistrict.tscn"
	).instantiate()
	root.add_child(street)
	current_scene = street
	await process_frame
	check(street.get_node_or_null("Dressing") == null
		and street.get_node_or_null("DressingContinuation") == null,
		"Duplicated old residential prefab still overlaps new facades")
	var city: Node3D = street.get_node("PrologueEntrances")
	check(city.get_node_or_null("Escuela_Exterior") != null,
		"School facade missing")
	check(city.get_node_or_null("Club_Exterior") != null,
		"Nightclub facade missing")
	check(city.get_node_or_null("Escuela_Portico_Techo") != null,
		"School porch missing")
	check(city.get_node_or_null("Escuela_Cornisa") != null,
		"School masonry detailing missing")
	check(city.get_node_or_null("Club_Marquesina") != null,
		"Club entrance canopy missing")
	check(city.get_node_or_null("Club_Dintel_Neon") != null,
		"Club muted neon missing")
	var trees: int = 0
	for child in city.get_children():
		if not child.name.begins_with("Arbol_"):
			continue
		trees += 1
		var tree := child as Node3D
		var crown := tree.get_node_or_null("Crown") as MeshInstance3D
		check(crown != null, "Tree has no crown")
		# The real frontage begins at x=+/-11.575. The most
		# building-ward point of every crown MUST be farther away.
		check(absf(tree.position.x) + 1.20 < 11.575 - 0.65,
			"Tree canopy overlaps the buildings")
		check(absf(tree.position.z + 20.0) > 4.0
			and absf(tree.position.z + 53.0) > 4.0,
			"Tree is in front of the school or nightclub entrance")
	check(trees >= 3, "Removing colliding trees must not empty the district")
	var school_door: Node3D = city.get_node("Entrance_SCHOOL")
	var club_door: Node3D = city.get_node("Entrance_NIGHTCLUB")
	check(school_door.is_in_group("interactable")
		and club_door.is_in_group("interactable"),
		"Redesigned facades block the active entrance")
	check(school_door.global_position.distance_to(
		club_door.global_position) > 30.0,
		"The district is no longer explorable")
	current_scene = null
	street.queue_free()
	await process_frame

	for name in ["School", "ComputerLab", "Nightclub"]:
		var room: Node3D = load(
			"res://scenes/prologue/" + name + ".tscn"
		).instantiate()
		root.add_child(room)
		current_scene = room
		await process_frame
		var front := room.get_node("FrontWall") as StaticBody3D
		var east := room.get_node("EastWall") as StaticBody3D
		check(front != null and east != null,
			name + " has no bounding walls")
		if front != null and east != null:
			var front_shape: BoxShape3D = front.get_node("Collision").shape
			var east_shape: BoxShape3D = east.get_node("Collision").shape
			check(front_shape.size.y < 1.0 and east_shape.size.y < 1.0,
				name + " is still an opaque box hiding the protagonist")
		check(room.get_node_or_null("Player") != null,
			name + " lost the playable character")
		if name == "ComputerLab":
			for i in range(4):
				check(room.get_node_or_null("CRTScreen_" + str(i)) != null,
					"Computer lab is missing its CRT screens")
			check(room.get_node_or_null("LabBoard") != null,
				"School has no classroom board")
			check(room.get_node_or_null("PROFESSOR") != null,
				"Redesign removed the professor")
		if name == "Nightclub":
			check(room.get_node_or_null("ClubBar") != null,
				"Nightclub bar is missing")
			check(room.get_node_or_null("ClubLightViolet") != null,
				"Nightclub lost its restrained lighting")
			check(room.get_node_or_null("RYOKO") != null,
				"Redesign removed Ryoko")
		current_scene = null
		room.queue_free()
		await process_frame
	print("VISUAL07_ENVIRONMENT_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
