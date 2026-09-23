extends StaticBody3D

func interact() -> void:
	var prologue: Dictionary = WorldApi.snapshot.get("prologue", {})
	if bool(prologue.get("enabled", false)) and str(
		prologue.get("stage", "")
	) != "CONNECTED":
		PrologueTerminal.open_terminal()
		return
	var terminal = get_tree().get_first_node_in_group("terminal_ui")
	if terminal == null:
		return
	terminal.open_terminal()
