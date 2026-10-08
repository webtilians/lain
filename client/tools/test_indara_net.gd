extends SceneTree
## Outside the walls of a building, the Indara net (ARTE.md): the room hangs over it by its
## cables, every other public zone is a jewel on it (home never is), and a pulse runs to the
## room when a line is said or someone arrives in a zone, out of it when a line is said in
## it. Fainter in the realistic look. Never calls the server.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func frames(count: int = 3) -> void:
	for i in range(count):
		await process_frame

func run() -> void:
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_indara_test.cfg"
	guide.hidden_by_player = true
	root.get_node("WorldApi").snapshot = {"minute": 1300, "player": {"location": "NIGHTCLUB", "energy": 1.0},
		"visible_actors": [], "known_nodes": [], "prologue": {"enabled": true, "stage": "FIND_RYOKO", "hint": ""}}
	var scene: Node3D = load("res://scenes/prologue/Nightclub.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	await frames(6)

	var net = scene.get_node_or_null("IndaraNet")
	check(net != null, "there is no Indara net outside the club")
	if net == null:
		await finish(scene)
		return
	check(net.level < scene.get_node("Floor").global_position.y - 5.0, "the net is not under the room: %.1f" % net.level)
	check(net.cables.size() == 3, "the room does not hang from three cables")
	for index in net.cables.size():
		check(absf(net.corners[index].y - net.level) > 5.0 and is_equal_approx(net.feet[index].y, net.level),
			"a cable does not reach from the room to the net")
	check(net.knots.size() == 10, "every other public zone should be a jewel: %d" % net.knots.size())
	check(not net.knots.has("APARTMENT") and not net.knots.has("NIGHTCLUB"), "home or the club itself is on the net")
	var spots := {}
	for knot in net.knots.values():
		spots[knot] = true
		check(is_equal_approx(fposmod(knot.x, net.CELL), 0.0) and is_equal_approx(fposmod(knot.z, net.CELL), 0.0),
			"a jewel is not on a knot of the net")
	check(spots.size() == net.knots.size(), "two zones share a jewel")
	var environment := scene.find_children("*", "WorldEnvironment", true, false)[0].environment as Environment
	check(environment.background_color.get_luminance() < 0.05, "the dark around the room is not dark")

	# What the server says of the city: nothing pulses for what had already happened.
	for pulse in net.pulses.duplicate():
		for bead in pulse.beads:
			bead.queue_free()
		net.pulses.erase(pulse)
	net.quiet = 99.0
	net.hear([{"zone": "CAFE", "people": 1, "said": 4}, {"zone": "NIGHTCLUB", "people": 1, "said": 2}])
	check(net.pulses.is_empty(), "the net pulses for lines said before the player came in")
	var dim: float = net.jewels["CAFE"].material_override.albedo_color.get_luminance()
	# A line said in the café and someone arriving there: pulses into the room, brighter jewel.
	net.hear([{"zone": "CAFE", "people": 2, "said": 5}, {"zone": "NIGHTCLUB", "people": 1, "said": 2}])
	var colours: Array = net.pulses.map(func(pulse: Dictionary) -> Color: return pulse.colour)
	check(colours.has(net.VOICE) and colours.has(net.ARRIVAL), "nothing ran to the room from the café")
	check(net.jewels["CAFE"].material_override.albedo_color.get_luminance() > dim, "the café does not glow brighter with people")
	var into: Dictionary = net.pulses[0]
	check(into.path[0] == net.knots["CAFE"] and into.path[-1] in net.corners, "the pulse does not go from the café up into the room")
	# A line said in the club itself goes out to the city.
	net.hear([{"zone": "CAFE", "people": 2, "said": 5}, {"zone": "NIGHTCLUB", "people": 1, "said": 3}])
	var out: Dictionary = net.pulses[-1]
	check(out.path[0] in net.corners and out.path[-1] in net.knots.values(), "a line said in the club does not go out")
	# Pulses run and are gone at the end of their way.
	for i in range(40):
		net._process(0.5)
	check(net.pulses.is_empty(), "the pulses never reach the end of their way")

	# Home is never on the net, even if a server said so.
	net.hear([{"zone": "APARTMENT", "people": 1, "said": 9}])
	check(not net.knots.has("APARTMENT"), "home appeared on the net")

	# Fainter in the realistic look (F9), and back.
	root.get_node("GraphicsDirector").set_anime(false)
	check(net.net.get_shader_parameter("strength") < 1.0, "the net is as bright in the realistic look")
	root.get_node("GraphicsDirector").set_anime(true)
	check(is_equal_approx(net.net.get_shader_parameter("strength"), 1.0), "the net does not come back with the anime look")
	await finish(scene)

func finish(scene: Node3D) -> void:
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://guide_indara_test.cfg"))
	scene.queue_free()
	current_scene = null
	await frames()
	print("INDARA_NET_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
