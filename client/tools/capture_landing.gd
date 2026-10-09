extends SceneTree
## Images for the download page (deploy/vps/web/img), rendered from the current game, offline:
##   Godot --path client --script res://tools/capture_landing.gd --resolution 1280x720 -- <repo> <session.json> <ryoko.json>
## session.json holds real terminal output (command, output, hostname, cwd) produced by the
## server's own shell code; it is shown in the real ShellTerminal over the computer lab.
## ryoko.json holds a real reply of Ryoko's from the server's prologue code (speaker, text,
## mood, choices); it is shown in the real dialogue window in the club.
## Both files come from tools/landing_inputs.py.
## Every picture is an unedited capture of a real scene with a fixed offline state, in the
## anime look and the highest quality whatever this PC has chosen.
const DISTRICT := "res://scenes/apartment_district/ApartmentDistrict.tscn"
const VIEWS := {"pasaje-azul.webp": Vector3(27.1, 0.91, -65), "barrio-noche.webp": Vector3(-3, 0.91, -4)}
const ROOMS := {"recreativos.webp": ["ARCADE", "res://scenes/city09/Arcade.tscn"]}
var out := ""

func _initialize() -> void:
	call_deferred("capture")

func save(image: Image, name: String) -> void:
	if image.get_width() != 1280:
		image.resize(1280, int(image.get_height() * 1280.0 / image.get_width()), Image.INTERPOLATE_LANCZOS)
	image.convert(Image.FORMAT_RGB8)
	if image.save_webp(out.path_join(name), true, 0.82) != OK:
		push_error("Could not save " + name)
	print("IMAGE_SAVED ", name)

func frame() -> Image:
	await create_timer(0.8).timeout
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()

func open(location: String, path: String, extra := {}) -> Node3D:
	var api := root.get_node("WorldApi")
	api.snapshot = {"minute": 0, "player": {"location": location, "energy": 1.0}, "visible_actors": [], "known_nodes": [],
		"prologue": {"enabled": true, "stage": "FIND_TEACHER", "hint": "En el barrio está la antigua escuela."}}
	api.snapshot.merge(extra, true)
	var scene: Node3D = load(path).instantiate()
	root.add_child(scene)
	current_scene = scene
	scene.get_node("Player").set_physics_process(false)
	scene.get_node("Player").set_process_unhandled_input(false)
	return scene

func look() -> void:
	## The anime look at the highest quality, without saving it over this PC's own choice.
	await process_frame
	var graphics := root.get_node("GraphicsDirector")
	graphics.set_anime(true)
	graphics.apply_quality(2)

func close(scene: Node) -> void:
	scene.queue_free()
	current_scene = null
	await process_frame

func capture() -> void:
	var options := OS.get_cmdline_user_args()
	out = options[0].path_join("deploy/vps/web/img")
	DirAccess.make_dir_recursive_absolute(out)
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node_or_null("Guide")
	var cinematic := root.get_node_or_null("Cinematic")
	if cinematic != null:
		cinematic.enabled = false
	if guide != null:
		guide.config_path = "user://guide_landing.cfg"
		guide.tips = ["shell", "dos"]
		guide.decided = true
		guide.hidden_by_player = true
	# The district at night.
	var district := open("APARTMENT_DISTRICT", DISTRICT)
	await look()
	var player: CharacterBody3D = district.get_node("Player")
	for name in VIEWS:
		player.position = VIEWS[name]
		player._update_camera()
		save(await frame(), name)
	await close(district)
	for name in ROOMS:
		var room := open(ROOMS[name][0], ROOMS[name][1])
		await look()
		save(await frame(), name)
		await close(room)
	# Outside a building, the Indara net: a café full of people talking, and someone arriving at the station.
	var cafe := open("CAFE", "res://scenes/city09/Cafe.tscn")
	await look()
	await process_frame
	var net = cafe.get_node("IndaraNet")
	net.hear([{"zone": "IZAKAYA", "people": 2, "said": 7}, {"zone": "STATION", "people": 0, "said": 0},
		{"zone": "ARCADE", "people": 1, "said": 2}, {"zone": "CAFE", "people": 1, "said": 4}])
	net.hear([{"zone": "IZAKAYA", "people": 2, "said": 8}, {"zone": "STATION", "people": 1, "said": 0},
		{"zone": "ARCADE", "people": 1, "said": 2}, {"zone": "CAFE", "people": 1, "said": 5}])
	# frame() waits 0.8 s: the pulses are on their way along the threads.
	save(await frame(), "red-indara.webp")
	await close(cafe)
	# A conversation with Ryoko in the club, as the server tells it.
	var club := open("NIGHTCLUB", "res://scenes/prologue/Nightclub.tscn",
		{"prologue": {"enabled": true, "stage": "FIND_RYOKO", "hint": ""}})
	await look()
	var visitor: CharacterBody3D = club.get_node("Player")
	visitor.position = Vector3(2.4, 0.9, -2.6)
	visitor._update_camera()
	var reply: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(options[2])).values()[0]
	var choices: Array[Dictionary] = []
	for choice in reply.choices:
		choices.append({"id": str(choice.id), "text": str(choice.text)})
	var dialog := root.get_node("EventDialog")
	dialog.expression = str(reply.get("mood", ""))
	dialog.show_choices("LANDING", str(reply.speaker), str(reply.text), choices)
	await create_timer(2.5).timeout
	save(await frame(), "ryoko.webp")
	dialog.close_event()
	await close(club)
	# The first-minutes guide, at home.
	if guide != null:
		guide.done = []
		guide.start_position = null
		guide.hidden_by_player = false
	var home := open("APARTMENT", "res://scenes/apartment/ApartmentIso.tscn")
	await look()
	save(await frame(), "guia.webp")
	await close(home)
	if guide != null:
		guide.hidden_by_player = true
	# The terminal: real output from the server's shell, in the real ShellTerminal.
	var lab := open("SCHOOL_LAB", "res://scenes/prologue/ComputerLab.tscn")
	await look()
	var shell := root.get_node("ShellTerminal")
	shell.surface.show()
	shell.output.text = ""
	for step in JSON.parse_string(FileAccess.get_file_as_string(options[1])):
		shell.hostname = str(step.hostname)
		shell.cwd = str(step.cwd)
		shell._update_prompt()
		shell._print(shell.prompt.text + " " + str(step.command))
		shell._print(str(step.output))
	save(await frame(), "terminal.webp")
	shell.surface.hide()
	await close(lab)
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://guide_landing.cfg"))
	quit()
