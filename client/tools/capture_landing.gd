extends SceneTree
## Images for the download page (deploy/vps/web/img), offline, never calling the server:
##   Godot --path client --script res://tools/capture_landing.gd --resolution 1280x720 -- <repo> <session.json>
## session.json holds real terminal output (command, output, hostname, cwd) produced by the
## server's own shell code; it is shown in the real ShellTerminal over the computer lab.
## The other images are existing game captures from docs/, scaled and saved as WebP.
const SHOTS := {
	"barrio-noche.webp": "docs/gothic12/images/street.png",
	"pasaje-azul.webp": "docs/gothic12/images/club.png",
	"recreativos.webp": "docs/interiors22/despues-arcade.png",
	"izakaya.webp": "docs/interiors22/despues-izakaya.png",
	"guia.webp": "docs/guide/guide-apartment.png",
}

func _initialize() -> void:
	call_deferred("capture")

func save(image: Image, path: String) -> void:
	if image.get_width() != 1280:
		image.resize(1280, int(image.get_height() * 1280.0 / image.get_width()), Image.INTERPOLATE_LANCZOS)
	image.convert(Image.FORMAT_RGB8)
	if image.save_webp(path, true, 0.82) != OK:
		push_error("Could not save " + path)
	print("IMAGE_SAVED ", path)

func capture() -> void:
	var options := OS.get_cmdline_user_args()
	var repo: String = options[0]
	var out := repo.path_join("deploy/vps/web/img")
	DirAccess.make_dir_recursive_absolute(out)
	for name in SHOTS:
		save(Image.load_from_file(repo.path_join(SHOTS[name])), out.path_join(name))
	var api := root.get_node("WorldApi")
	api.set_script(load("res://tools/offline_world_api.gd"))
	root.get_node("PrologueApi").set_script(load("res://tools/offline_prologue_api.gd"))
	var guide := root.get_node_or_null("Guide")
	if guide != null:
		guide.tips = ["shell", "dos"]
		guide.hidden_by_player = true
	api.snapshot = {"minute": 0, "player": {"location": "SCHOOL_LAB", "energy": 1.0}, "visible_actors": [], "known_nodes": []}
	var scene: Node3D = load("res://scenes/prologue/ComputerLab.tscn").instantiate()
	root.add_child(scene)
	current_scene = scene
	scene.get_node("Player").set_physics_process(false)
	scene.get_node("Player").set_process_unhandled_input(false)
	await process_frame
	var shell := root.get_node("ShellTerminal")
	shell.surface.show()
	shell.output.text = ""
	var session = JSON.parse_string(FileAccess.get_file_as_string(options[1]))
	for step in session:
		shell.hostname = str(step.hostname)
		shell.cwd = str(step.cwd)
		shell._update_prompt()
		shell._print(shell.prompt.text + " " + str(step.command))
		shell._print(str(step.output))
	await create_timer(0.6).timeout
	await RenderingServer.frame_post_draw
	save(root.get_texture().get_image(), out.path_join("terminal.webp"))
	shell.surface.hide()
	quit()
