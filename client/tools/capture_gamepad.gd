extends SceneTree
## A frame of the on-screen keyboard over the terminal (never calls the server):
##   Godot --path client --script res://tools/capture_gamepad.gd --resolution 1280x720 -- C:/out/folder
func _initialize() -> void:
	call_deferred("capture")

func capture() -> void:
	var folder: String = OS.get_cmdline_user_args()[0]
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	var guide := root.get_node("Guide")
	guide.config_path = "user://guide_capture.cfg"
	guide.hidden_by_player = true
	var shell := root.get_node("ShellTerminal")
	shell.surface.show()
	shell.hostname = "casa-mio"
	shell.prompt.text = "mio@casa-mio:/home/mio$"
	shell._print("mio@casa-mio:/home/mio$ ls\ncorreo  notas  instituto")
	var press := InputEventJoypadButton.new()
	press.button_index = JOY_BUTTON_DPAD_DOWN
	press.pressed = true
	Input.parse_input_event(press)
	await process_frame
	shell.input.text = "cat corr"
	shell.input.caret_column = 8
	shell.input.grab_focus()
	for i in range(20):
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(folder.path_join("gamepad-keyboard.png"))
	print("CAPTURE_SAVED gamepad-keyboard")
	quit()
