extends RefCounted
## Presentation only: the server owns the calendar, scores and prizes.
var selected := ""

func render(ws: Node, at_cafe: bool) -> void:
	var data: Dictionary = ws.event_data()
	ws.event_projection_cache = JSON.stringify(data)
	ws.label(ws.content, "KISSA // TABLÓN DE TORNEOS · RIVALES PNJ")
	ws.label(ws.content, str(data.get("rules", "")))
	var events: Array = data.get("events", [])
	if events.is_empty():
		ws.label(ws.content, "El café está preparando el calendario.")
		return
	var found := false
	for item in events:
		if item.id == selected: found = true
	if not found:
		selected = str(events[-1].id)
		for item in events:
			if item.status == "OPEN" or item.status == "UPCOMING":
				selected = str(item.id)
				break
	var picker := OptionButton.new()
	picker.custom_minimum_size.y = 36
	var current: Dictionary = {}
	for item in events:
		var state := str({"OPEN":"Abierto", "UPCOMING":"Próximamente", "CLOSED":"Cerrado"}.get(str(item.status), ""))
		picker.add_item("Torneo " + str(int(item.edition)) + " · " + str(item.get("game_name","Bit Courier")) + " · " + state + " · " + str(item.prize))
		if item.id == selected:
			picker.select(picker.item_count - 1)
			current = item
	picker.item_selected.connect(func(index: int):
		selected = str(events[index].id)
		ws._render())
	ws.content.add_child(picker)
	var columns := HBoxContainer.new()
	columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	columns.add_theme_constant_override("separation", 24)
	ws.content.add_child(columns)
	var left: VBoxContainer = ws.scrolling(columns)
	ws.label(left, str(current.get("game_name","Bit Courier")).to_upper())
	ws.label(left, str(current.get("game_rules","Recoge 3 paquetes y alcanza la salida.")))
	ws.label(left, "PREMIO · " + str(current.prize)).add_theme_font_size_override("font_size", 22)
	var now := int(data.get("minute", 0))
	ws.label(left, "Reloj del mundo: " + str(now) + "\nApertura: " + str(int(current.opens)) + " · Cierre: " + str(int(current.closes)))
	if current.status == "UPCOMING":
		ws.label(left, "Abre dentro de " + str(int(current.opens) - now) + " minutos del mundo.")
	elif current.status == "OPEN":
		ws.label(left, "Quedan " + str(int(current.closes) - now) + " minutos del mundo. El recorrido debe llegar al servidor antes del cierre.")
	else:
		ws.label(left, "CLASIFICACIÓN FINAL" if bool(current.settled) else "Cerrado · adjudicación pendiente del reloj del mundo.")
	ws.label(left, "Intentos iniciados: " + str(int(current.attempts)) + "/" + str(int(data.get("attempts_limit", 3))) )
	if bool(current.won):
		ws.label(left, "PREMIO RECIBIDO · Disponible en Dispositivos o en la biblioteca de Código. Conserva la procedencia de esta edición.")
	ws.label(left, "MEJORES MARCAS · 100 por señal − 2 por movimiento\nEmpates comparten puesto.")
	if current.ranking.is_empty(): ws.label(left, "Todavía no hay marcas publicadas.")
	for entry in current.ranking:
		ws.label(left, str(int(entry.rank)) + ". " + ("Tú" if bool(entry.mine) else ("PNJ · " if bool(entry.npc) else "") + str(entry.name)) + "     " + str(int(entry.score)) + " puntos")
	if not at_cafe:
		ws.label(left, "Para competir, visita el terminal de Kissa Café en el barrio. Puedes consultar aquí los resultados y premios.")
		return
	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	columns.add_child(right)
	var start: Button = ws.button(right, "Reabrir intento" if not str(current.run_id).is_empty() else "Jugar un intento", ws._send_event.bind("START", {"event":current.id}))
	start.disabled = ws.busy or current.status != "OPEN" or (int(current.attempts) >= int(data.attempts_limit) and str(current.run_id).is_empty())
	ws.label(right, "Flechas o botones · Reabrir reinicia este intento.")
	if not ws.arcade.is_empty() and ws.run_endpoint == "cafe-events" and ws.run_event == current.id:
		ws._board(right, 192)
		var controls := HBoxContainer.new()
		right.add_child(controls)
		for direction in ["U", "D", "L", "R"]:
			var b: Button = ws.button(controls, {"U":"↑", "D":"↓", "L":"←", "R":"→"}[direction], ws._move.bind(direction))
			b.disabled = ws.busy or current.status != "OPEN"
		ws.label(right, ws.arcade_status())
	else:
		ws.label(right, str(current.get("game_name","Bit Courier")) + "\nConsulta las reglas y el premio de esta edición antes de iniciar el intento.")
