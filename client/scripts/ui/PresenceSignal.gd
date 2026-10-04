extends CanvasLayer
## Protocolo de presencia: existing is being received. With nobody answering
## (no conversation, no other person in the zone, no reply from the network)
## the player's signal fades and the avatar turns translucent and glitchy.
## Presentation only: it never touches movement, collision or world state.
const FADE_AFTER := 180.0
const FADE_SPAN := 60.0
var silence := 0.0
var hud: Label
var meshes: Array[GeometryInstance3D] = []
var player_id := 0
var applied := false

func _ready() -> void:
	layer = 90
	hud = Label.new()
	hud.anchor_left = 1.0
	hud.anchor_right = 1.0
	hud.offset_left = -470
	hud.offset_right = -24
	hud.offset_top = 18
	hud.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	hud.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hud.add_theme_font_size_override("font_size", 15)
	hud.add_theme_color_override("font_color", Color("b9d7c4"))
	hud.add_theme_color_override("font_shadow_color", Color("0b0d10"))
	hud.add_theme_constant_override("shadow_offset_x", 2)
	hud.add_theme_constant_override("shadow_offset_y", 2)
	add_child(hud)
	hud.hide()

func _layer() -> Dictionary:
	# The layer the player is in the middle of; the server decides which.
	var current = WorldApi.snapshot.get("current_layer", null)
	if current is String and WorldApi.snapshot.has(current):
		return WorldApi.snapshot.get(current, {})
	for key in ["layer_seven", "layer_six", "layer_five", "layer_four"]:
		var entry: Dictionary = WorldApi.snapshot.get(key, {})
		if bool(entry.get("active", false)):
			return entry
	return WorldApi.snapshot.get("layer_three", {})

func perceived() -> bool:
	if EventDialog.visible or Workshop.is_open() or ShellTerminal.is_open():
		return true
	return ServerConnection.is_online() and not OnlinePresence._peers.is_empty()

func _process(delta: float) -> void:
	var data := _layer()
	if not bool(data.get("active", false)) or SceneRouter.get("loading") == true:
		hud.hide()
		_apply(0.0)
		return
	silence = 0.0 if perceived() else silence + delta
	var fade := clampf((silence - FADE_AFTER) / FADE_SPAN, 0.0, 1.0)
	_apply(fade)
	var text := str(data.get("title", "")) + "\n" + str(data.get("goal", ""))
	if data.get("decision") == null and not str(data.get("title", "")).is_empty():
		text += "\n¿Atascado? Escribe pista en el Terminal."
	if fade >= 1.0:
		text += "\n\nCASI NO ESTÁS · nadie te ha recibido en " + str(int(silence / 60.0)) + " min. Habla con alguien."
	elif fade > 0.0:
		text += "\n\nSEÑAL DÉBIL · nadie te ha recibido en " + str(int(silence / 60.0)) + " min."
	hud.text = text
	hud.modulate.a = 1.0 if fade > 0.0 else 0.72
	hud.visible = not (Workshop.is_open() or ShellTerminal.is_open() or CharacterJournal.backdrop.visible
		or Cinematic.is_playing())

func _apply(fade: float) -> void:
	if fade <= 0.0 and not applied:
		return
	var player := get_tree().get_first_node_in_group("player")
	if player == null:
		return
	if player.get_instance_id() != player_id:
		player_id = player.get_instance_id()
		meshes.clear()
		for node in player.find_children("*", "GeometryInstance3D", true, false):
			meshes.append(node)
	var amount := 0.0
	if fade > 0.0:
		# A slow fade with dropped-packet flickers that grow as the signal weakens.
		amount = fade * 0.6
		if randf() < 0.06 + fade * 0.2:
			amount = minf(0.95, amount + randf() * 0.35)
	for mesh in meshes:
		if is_instance_valid(mesh):
			mesh.transparency = amount
	applied = amount > 0.0
