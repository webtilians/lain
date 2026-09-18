extends StaticBody3D

func interact() -> void:
	var terminal = get_tree().get_first_node_in_group("terminal_ui")
	if terminal == null:
		return
	terminal.open_terminal()
