extends CanvasLayer
## Workstation UI; the server owns saves, compilation, rewards and contracts.
var surface: ColorRect
var content: VBoxContainer
var footer: Label
var heading: Label
var tabs: HBoxContainer
var request: HTTPRequest
var retry_button: Button
var active_player: Node
var busy := false
var pending: Dictionary = {}
var page := "Correo"
var mode := "PC"
var program_draft := ""
var life_draft := ""
var drafts_loaded := false
var installed_scene := 0
var frames: Array = []
var frame_index := 0
var arcade: Dictionary = {}
var run_id := ""
var moves := ""
var courier := Vector2i.ZERO
var collected: Array[Vector2i] = []
var status := ""
var pending_endpoint := "workshop"
var circle_draft := ""
var circle_draft_group := -1
var circle_name_draft := ""
var circle_tab := "Grupo"
var circle_confirm_leave := false
var circle_panel = preload("res://scripts/ui/CirclePanel.gd").new()
var event_panel = preload("res://scripts/ui/CafeEventPanel.gd").new()
var exchange_panel = preload("res://scripts/ui/ExchangePanel.gd").new()
var run_endpoint := "workshop"
var run_event := ""
var run_closes := 0
var event_projection_cache := ""
var snake_model = preload("res://scripts/ui/SignalSnake.gd").new()
var snake_elapsed := 0.0
var snake_autoplay := true

func _ready() -> void:
	layer = 104
	request = HTTPRequest.new()
	request.max_redirects = 0
	request.timeout = 20
	add_child(request)
	request.request_completed.connect(_completed)
	surface = ColorRect.new()
	surface.color = Color("10191e")
	surface.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(surface)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 28)
	surface.add_child(margin)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 12)
	margin.add_child(layout)
	var bar := HBoxContainer.new()
	layout.add_child(bar)
	heading = Label.new()
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.add_child(heading)
	retry_button = button(bar, "Reintentar envío", func(): _retry(pending.duplicate(true), pending_endpoint))
	retry_button.hide()
	button(bar, "Cerrar · Esc", close_pc)
	tabs = HBoxContainer.new()
	layout.add_child(tabs)
	layout.add_child(HSeparator.new())
	content = VBoxContainer.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(content)
	footer = Label.new()
	footer.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	footer.custom_minimum_size.y = 65
	footer.add_theme_color_override("font_color", Color("b7d8c5"))
	layout.add_child(footer)
	surface.hide()
	WorldApi.snapshot_updated.connect(_event_snapshot_changed)

func event_data() -> Dictionary:
	return WorldApi.snapshot.get("cafe_events", {})

func _event_snapshot_changed(_snapshot: Dictionary) -> void:
	if is_open() and not busy and (mode == "CAFE_EVENTS" or (mode == "PC" and page == "Eventos")):
		if JSON.stringify(event_data()) == event_projection_cache: return
		for picker in content.find_children("*", "OptionButton", true, false):
			if picker.get_popup().visible: return
		var positions: Array[int] = []
		for scroll in content.find_children("*", "ScrollContainer", true, false):
			positions.append(scroll.scroll_vertical)
		_render()
		var scrolls := content.find_children("*", "ScrollContainer", true, false)
		for i in range(mini(positions.size(), scrolls.size())):
			scrolls[i].set_deferred("scroll_vertical", positions[i])

func active() -> bool:
	return bool(WorldApi.snapshot.get("workshop", {}).get("active", false))

func is_open() -> bool:
	return surface != null and surface.visible

func data() -> Dictionary:
	return WorldApi.snapshot.get("workshop", {})

func circle_data() -> Dictionary:
	return WorldApi.snapshot.get("circles", {})

func exchange_data() -> Dictionary:
	return WorldApi.snapshot.get("code_exchange", {})

func exchange_active() -> bool:
	return bool(exchange_data().get("active",false))

func open_exchange_contact(peer: String) -> void:
	_open("EXCHANGE_CONTACT")
	_send_exchange("CONTACT",{"peer":peer})

func circles_active() -> bool:
	return bool(circle_data().get("active",false))

func open_circle_contact(peer: String) -> void:
	_open("CIRCLE_CONTACT")
	_send_circle("CONTACT",{"target":peer})

func button(parent: Node, text: String, callback: Callable) -> Button:
	var node := Button.new()
	node.text = text
	node.custom_minimum_size.y = 34
	node.pressed.connect(callback)
	parent.add_child(node)
	return node

func label(parent: Node, text: String) -> Label:
	var node := Label.new()
	node.text = text
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	parent.add_child(node)
	return node

func clear(parent: Node) -> void:
	for node in parent.get_children():
		parent.remove_child(node)
		node.queue_free()

func open_pc() -> void:
	_open("PC")

func open_cafe() -> void:
	_open("CAFE")

func open_lesson() -> void:
	_open("LESSON")
	_send("LESSON", {})

func _open(kind: String) -> void:
	if not active() or busy: return
	if EventDialog.visible: EventDialog.close_event()
	mode = kind
	page = "Correo"
	status = ""
	circle_confirm_leave = false
	exchange_panel.confirm_offer = ""
	if not drafts_loaded:
		program_draft = str(data().get("draft", ""))
		life_draft = str(data().get("life_source", ""))
		drafts_loaded = true
	surface.show()
	active_player = get_tree().get_first_node_in_group("player")
	if is_instance_valid(active_player):
		active_player.set_physics_process(false)
		active_player.set_process_unhandled_input(false)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_render()

func close_pc() -> void:
	_capture_drafts()
	surface.hide()
	if is_instance_valid(active_player):
		active_player.set_physics_process(true)
		active_player.set_process_unhandled_input(true)
	active_player = null

func _input(event: InputEvent) -> void:
	if not is_open(): return
	if event.is_action_pressed("ui_cancel"):
		close_pc()
		get_viewport().set_input_as_handled()
	elif mode in ["CAFE", "CAFE_EVENTS"] and not arcade.is_empty() and event is InputEventKey and event.pressed and not event.echo:
		for picker in content.find_children("*", "OptionButton", true, false):
			if picker.get_popup().visible: return
		var directions := {KEY_UP:"U", KEY_DOWN:"D", KEY_LEFT:"L", KEY_RIGHT:"R"}
		if directions.has(event.keycode):
			_move(directions[event.keycode])
			get_viewport().set_input_as_handled()

func _process(delta: float) -> void:
	if snake_autoplay and is_snake() and _arcade_allowed() and not snake_model.finished:
		snake_elapsed += minf(delta, 0.25)
		if snake_elapsed >= 0.25:
			snake_elapsed = 0.0
			_snake_step()
	var scene := get_tree().current_scene as Node3D
	if not active() or scene == null or scene.get_instance_id() == installed_scene: return
	installed_scene = scene.get_instance_id()
	if str(WorldApi.snapshot.get("player", {}).get("location", "")) == "CAFE":
		var objects := Node3D.new()
		objects.name = "WorkshopObjects"
		objects.set_script(load("res://scripts/world/WorkshopObjects.gd"))
		scene.add_child(objects)

func _select(value: String) -> void:
	page = value
	_render()

func _capture_drafts() -> void:
	# TextEdit signals may arrive after a click that changes the current page.
	# Read the live editors before removing them so the last keystroke survives.
	for editor in content.find_children("*","CodeEdit",true,false):
		match str(editor.name):
			"CircleEditor": circle_draft = editor.text
			"ProgramEditor": program_draft = editor.text
			"LifeEditor": life_draft = editor.text
	for entry in content.find_children("CircleName","LineEdit",true,false):
		circle_name_draft = entry.text

func _render() -> void:
	_capture_drafts()
	clear(tabs)
	clear(content)
	var state := data()
	var contract := str(state.get("contract", "INDEPENDENT"))
	heading.text = "NAVI // TALLER   ·   " + str(int(state.get("cost", 0))) + "/" + str(int(state.get("capacity", 0))) + " unidades   ·   " + ("Independiente" if contract == "INDEPENDENT" else contract)
	footer.text = "Esperando respuesta…" if busy else status
	if mode == "LESSON":
		label(content, "AULA DE INFORMÁTICA // UNA MÁQUINA QUE SUEÑA")
		label(content, "El profesor te entrega las reglas de Conway. La plantilla estará en el PC de casa, en Juego de la Vida. Allí puedes escribir, probar y guardar tu solución.")
		return
	if mode == "CAFE":
		_render_cafe()
		return
	if mode == "CAFE_EVENTS":
		button(tabs, "Volver a práctica y técnico", _open.bind("CAFE"))
		event_panel.render(self, true)
		return
	if mode == "CIRCLE_CONTACT":
		heading.text = "CONVERSACIÓN // UNA RED PROPIA"
		label(content,"Hablad de colaborar fuera de las corporaciones.")
		label(content,"Esperando respuesta…" if busy else status).add_theme_font_size_override("font_size",22)
		footer.text = "Cuando cumplas su condición, podrás enviarle la invitación desde Círculo, en el PC de casa."
		return
	if mode == "EXCHANGE_CONTACT":
		heading.text = "CONVERSACIÓN // INTERCAMBIAR CÓDIGO"
		label(content,"Esperando respuesta…" if busy else status).add_theme_font_size_override("font_size",22)
		footer.text = "Consulta la propuesta en PC → Intercambios. Allí eliges qué copia compartir y revisas el acuerdo."
		return
	var pages: Array = ["Correo", "Código", "Juego de la Vida", "Dispositivos", "Wired"]
	if circles_active(): pages.append("Círculo")
	if bool(event_data().get("active", false)): pages.append("Eventos")
	if exchange_active(): pages.append("Intercambios")
	for title in pages:
		var tab := button(tabs, title, _select.bind(title))
		tab.disabled = title == page
	match page:
		"Correo": _mail()
		"Código": _code(false)
		"Juego de la Vida": _code(true)
		"Dispositivos": _devices()
		"Wired": _wired()
		"Círculo": circle_panel.render(self)
		"Eventos": event_panel.render(self, false)
		"Intercambios": exchange_panel.render(self)

func scrolling(parent: Node) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	parent.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_constant_override("separation", 12)
	scroll.add_child(box)
	return box

func _mail() -> void:
	var box := scrolling(content)
	label(box, "UNA MÁQUINA QUE SUEÑA")
	label(box, "En Kissa Café hay un terminal y un coprocesador por reparar. Habla con el técnico allí y pide las reglas al profesor en el aula de informática. Después completa el ejercicio en este PC.")
	label(box, "BIT COURIER · PRÁCTICA INDIVIDUAL\nRecoge tres paquetes y alcanza la salida del minijuego del café. Consigue una interfaz de red y el módulo Exploración. Las competiciones están en Eventos.")
	if bool(event_data().get("active", false)):
		label(box, "TORNEOS DE KISSA\nEl café organiza ediciones con tres intentos, clasificación y premios de código o equipo. Consulta Eventos; compite en el terminal del café. Los rivales de esta fase son PNJ.")
		button(box, "Consultar eventos del café", _select.bind("Eventos"))
	if circles_active():
		label(box,"UNA RED PROPIA\nRyoko y el técnico de Kissa quieren colaborar fuera de las corporaciones. Habla con ellos de crear una red. En Círculo puedes reunir sus aportaciones y compilar un programa compartido.")
	if exchange_active():
		label(box,"CÓDIGO ENTRE CONTACTOS\nRyoko, en AZUL, y el técnico de Kissa proponen intercambiar fragmentos. Habla con cada uno de intercambiar código y revisa sus condiciones aquí. Un premio del café puede abrir otro camino para ampliar tu programa.")
		button(box,"Consultar intercambios",_select.bind("Intercambios"))
	var offers: Dictionary = data().get("offers", {})
	if offers.is_empty():
		label(box, "CORREO CORPORATIVO\nTodavía no hay ofertas. Tus avances pueden llamar la atención de otras redes.")
	for faction in offers:
		label(box, str(offers[faction]))
		button(box, "Aceptar condiciones de " + str(faction), _send.bind("CONTRACT", {"faction":faction}))
	if not offers.is_empty():
		button(box, "Seguir independiente / terminar mi acuerdo", _send.bind("CONTRACT", {"faction":"INDEPENDENT"}))

func _code(life: bool) -> void:
	if life and int(data().get("lesson", 0)) == 0:
		label(content, "Todavía no tienes la plantilla. Habla con el profesor en el aula de informática y pregunta por el Juego de la Vida.")
		return
	label(content, "next_cell.py · Python acotado: if, return, comparaciones, and/or/not. Sin llamadas ni bucles." if life else "wired.py · Añade una línea use(\"modulo\") por función. Compilar valida y empaqueta el montaje.")
	var row := HBoxContainer.new()
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 18)
	content.add_child(row)
	var editor := CodeEdit.new()
	editor.name = "LifeEditor" if life else "ProgramEditor"
	editor.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	editor.size_flags_stretch_ratio = 1.4
	editor.gutters_draw_line_numbers = true
	editor.add_theme_font_size_override("font_size", 19)
	editor.text = life_draft if life else program_draft
	editor.text_changed.connect(func():
		if life: life_draft = editor.text
		else: program_draft = editor.text)
	row.add_child(editor)
	var side := scrolling(row)
	if life:
		side.add_theme_constant_override("separation", 6)
		label(side, "Viva: 2 o 3 vecinas. Nace: 3. Las demás mueren.\nTablero 8×8, exterior muerto; cambios simultáneos.")
		button(side, "Cargar ejemplo guiado", func():
			life_draft = str(data().get("life_hint", ""))
			editor.text = life_draft)
		if not frames.is_empty():
			label(side, "SIMULACIÓN VERIFICADA · GENERACIÓN " + str(frame_index))
			_board(side, 200)
			button(side, "Siguiente generación", func():
				frame_index = (frame_index + 1) % frames.size()
				_render())
	else:
		label(side, "BIBLIOTECA · LAS COPIAS CUENTAN UNA VEZ")
		for item in data().get("library", []):
			label(side, str(item.name) + " · " + str(int(item.cost)) + " unidades\n" + str(item.effect))
			var snippet := 'use("' + str(item.id) + '")\n'
			button(side, "Insertar " + str(item.name), func():
				if not editor.text.ends_with("\n") and not editor.text.is_empty(): editor.text += "\n"
				editor.text += snippet
				program_draft = editor.text)
	var actions := HBoxContainer.new()
	content.add_child(actions)
	button(actions, "Guardar borrador", func(): _send("SAVE_LIFE" if life else "SAVE_PROGRAM", {"source":editor.text}))
	button(actions, "Probar las reglas" if life else "Compilar y activar", func(): _send("TEST_LIFE" if life else "COMPILE", {"source":editor.text}))
	label(content, "Guardar o probar conserva tu texto. Cerrar el juego descarta cambios sin guardar. Una compilación fallida mantiene el montaje anterior.")

func _devices() -> void:
	var box := scrolling(content)
	label(box, "Una aportación por modelo funcional. Dos Navi A no duplican capacidad. Conecta tus equipos antes de compilar.")
	for item in data().get("assets", []):
		label(box, str(item.name) + " · " + ("Dispositivo" if item.kind == "DEVICE" else "Fragmento") + " · " + ("Prestado" if item.ownership == "LOAN" else "Tuyo") + "\nProcedencia: " + str(item.source) + " · minuto " + str(int(item.minute)))
		if item.kind == "DEVICE":
			var plugged := bool(item.active)
			var b := button(box, ("Desconectar" if plugged else "Conectar") + " · " + str(int(item.capacity)) + " unidades", _send.bind("DEVICE", {"id":item.id, "active":not plugged}))
			b.disabled = str(item.id) == "home_navi"

func _wired() -> void:
	var box := scrolling(content)
	label(box, "MONTAJE ACTIVO: " + ", ".join(data().get("modules", [])))
	if not data().get("shared_modules",[]).is_empty():
		label(box,"FUNCIONES DEL CÍRCULO: "+", ".join(data().shared_modules))
	label(box, "Protección se ejecuta junto al armario de un enlace propio. Exploración permite consultar desde casa enlaces que ya has examinado. Compilar no conquista territorio.")
	for relay in WorldApi.snapshot.get("network_conflict", {}).get("relays", []):
		label(box, str(relay.name) + " · Tu control: " + str(int(relay.mine)) + "% · Defensas: " + str(int(relay.defense)) + "/2")
		for controller in relay.get("controllers", []):
			label(box, str(controller.name) + ": " + str(int(controller.control)) + "%")
		if bool(relay.inspected):
			var b := button(box, "Ejecutar Exploración", _send.bind("SCAN", {"relay":relay.id}))
			b.disabled = not ("scan" in data().get("modules", []) or "scan" in data().get("shared_modules",[]))
	button(box, "Abrir la investigación de la Wired", func():
		close_pc()
		ChapterOne.open_terminal())
	button(box, "Consultar y ocultar enlaces", func():
		close_pc()
		NetworkConflict.open_terminal())

func _render_cafe() -> void:
	label(content, "KISSA // TERMINAL DEL CAFÉ · PRÁCTICA")
	var actions := HBoxContainer.new()
	content.add_child(actions)
	button(actions, "Hablar con el técnico", _send.bind("TECHNICIAN", {}))
	button(actions, "Nueva práctica", _send.bind("ARCADE_START", {}))
	if bool(data().get("arcade_catalog",false)):
		button(actions, "Practicar Serpiente", _send.bind("ARCADE_START", {"game":"signal_snake"}))
	if bool(event_data().get("active", false)):
		button(actions, "Torneos y clasificación", _open.bind("CAFE_EVENTS"))
	if circles_active():
		button(actions,"Hablar de una red propia",open_circle_contact.bind("KISSA_TECH"))
	if exchange_active():
		button(actions,"Intercambiar código",open_exchange_contact.bind("KISSA_TECH"))
	if is_snake() and run_endpoint == "workshop":
		label(content, "SERPIENTE DE SEÑAL · " + str(arcade.get("rules","")) + "\nPráctica sin premio · Mejor marca: " + str(int(data().get("snake_best_score",0))))
	else:
		label(content, "Recoge al menos 3 paquetes y llega a la salida. Máximo 80 movimientos, incluidos los choques con paredes. Flechas del teclado o botones. Mejor puntuación local: " + str(int(data().get("best_score", 0))))
	if not arcade.is_empty() and run_endpoint == "workshop":
		_board(content)
		var controls := HBoxContainer.new()
		content.add_child(controls)
		for direction in ["U", "D", "L", "R"]:
			button(controls, {"U":"Arriba", "D":"Abajo", "L":"Izquierda", "R":"Derecha"}[direction], _move.bind(direction))
		label(content, arcade_status())

func is_snake() -> bool:
	return arcade.get("game_id","bit_courier") == "signal_snake"

func arcade_status() -> String:
	if is_snake():
		return "Pasos: " + str(moves.length()) + "/80 · Señales: " + str(snake_model.collected) + "/6 · Azul: cabeza · Verde: cuerpo · Amarillo: señal" + (" · FINALIZADO" if snake_model.finished else "")
	return "Movimientos: " + str(moves.length()) + "/80 · Paquetes: " + str(collected.size()) + "/5 · Azul: tú / Amarillo: paquete / Verde: salida"

func _arcade_allowed() -> bool:
	if not is_open() or busy or arcade.is_empty() or run_id.is_empty(): return false
	for picker in content.find_children("*", "OptionButton", true, false):
		if picker.get_popup().visible: return false
	if mode == "CAFE": return run_endpoint == "workshop"
	if mode == "CAFE_EVENTS":
		return run_endpoint == "cafe-events" and event_panel.selected == run_event and int(event_data().get("minute",0)) < run_closes
	return false

func _snake_step() -> void:
	if not _arcade_allowed() or snake_model.finished: return
	snake_model.step()
	moves = snake_model.moves
	_render()
	if snake_model.finished: _finish_arcade()

func _finish_arcade() -> void:
	if run_endpoint == "cafe-events":
		_send_event("FINISH", {"run_id":run_id,"moves":moves})
	else:
		_send("ARCADE_FINISH", {"run_id":run_id,"moves":moves})

func _board(parent: Node, minimum: int = 260) -> Control:
	var view := Control.new()
	view.custom_minimum_size = Vector2(minimum, minimum)
	view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	view.draw.connect(_draw_board.bind(view))
	parent.add_child(view)
	return view

func _draw_board(view: Control) -> void:
	var cell := minf(view.size.x, view.size.y) / 8.0
	for y in range(8):
		for x in range(8):
			var tint := Color("25383f")
			if mode in ["CAFE", "CAFE_EVENTS"]:
				if is_snake():
					if Vector2i(x,y) in snake_model.body: tint = Color("61b592")
					if Vector2i(x,y) == snake_model.food: tint = Color("dcc37d")
					if not snake_model.body.is_empty() and Vector2i(x,y) == snake_model.body[0]: tint = Color("73aee3")
				else:
					if _contains(arcade.get("walls", []), Vector2i(x,y)): tint = Color("75868a")
					elif _contains([arcade.get("exit", [-1,-1])], Vector2i(x,y)): tint = Color("61b592")
					elif _contains(arcade.get("chips", []), Vector2i(x,y)) and not Vector2i(x,y) in collected: tint = Color("dcc37d")
					if courier == Vector2i(x,y): tint = Color("73aee3")
			elif not frames.is_empty() and int(frames[frame_index][y][x]) == 1:
				tint = Color("a6cdb2")
			view.draw_rect(Rect2(Vector2(x,y)*cell, Vector2.ONE*(cell-2)), tint)

func _contains(points: Array, point: Vector2i) -> bool:
	for pair in points:
		if int(pair[0]) == point.x and int(pair[1]) == point.y: return true
	return false

func _move(direction: String) -> void:
	if not _arcade_allowed(): return
	if is_snake():
		snake_model.turn(direction)
		return
	if moves.length() >= 80 or _contains([arcade.exit], courier): return
	var offsets := {"U":Vector2i.UP,"D":Vector2i.DOWN,"L":Vector2i.LEFT,"R":Vector2i.RIGHT}
	var next: Vector2i = courier + offsets[direction]
	moves += direction
	if next.x >= 0 and next.y >= 0 and next.x < 8 and next.y < 8 and not _contains(arcade.walls, next):
		courier = next
	if _contains(arcade.chips, courier) and not courier in collected: collected.append(courier)
	_render()
	if moves.length() >= 80 or _contains([arcade.exit], courier):
		_finish_arcade()

func _send_event(action: String, payload: Dictionary) -> void:
	if busy: return
	pending_endpoint = "cafe-events"
	pending = {"action":action,"data":payload,"request_id":"event_"+str(Time.get_unix_time_from_system()).replace(".","_")+"_"+str(Time.get_ticks_usec())}
	_dispatch()

func _send(action: String, payload: Dictionary) -> void:
	if busy: return
	pending_endpoint = "workshop"
	pending = {"action":action,"data":payload,"request_id":"workshop_" + str(Time.get_unix_time_from_system()).replace(".","_") + "_" + str(Time.get_ticks_usec())}
	_dispatch()

func _send_circle(action: String, payload: Dictionary) -> void:
	if busy: return
	pending_endpoint = "circles"
	pending = {"action":action,"data":payload,"request_id":"circle_"+str(Time.get_unix_time_from_system()).replace(".","_")+"_"+str(Time.get_ticks_usec())}
	_dispatch()

func _send_exchange(action: String, payload: Dictionary) -> void:
	if busy: return
	pending_endpoint = "code-exchange"
	pending = {"action":action,"data":payload,"request_id":"exchange_"+str(Time.get_unix_time_from_system()).replace(".","_")+"_"+str(Time.get_ticks_usec())}
	_dispatch()

func _dispatch() -> void:
	if busy: return
	retry_button.hide()
	busy = true
	footer.text = "Esperando respuesta…"
	WorldApi.begin_external_mutation()
	var error := request.request(ServerConnection.base_url() + "/api/v1/"+pending_endpoint+"/action", ServerConnection.headers(), HTTPClient.METHOD_POST, JSON.stringify(pending))
	if error != OK:
		busy = false
		WorldApi.end_external_mutation()
		_failure("No se pudo conectar con el servidor.", true)

func _failure(text: String, retry: bool) -> void:
	status = text
	retry_button.visible = retry
	if not is_open(): return
	footer.text = status

func _retry(command: Dictionary, endpoint: String = "workshop") -> void:
	if busy: return
	pending = command
	pending_endpoint = endpoint
	_dispatch()

func _completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	busy = false
	retry_button.hide()
	WorldApi.end_external_mutation()
	if result != HTTPRequest.RESULT_SUCCESS:
		_failure("Respuesta perdida. Reintentar conserva el identificador y no duplica recompensas.", true)
		return
	var decoder := JSON.new()
	if decoder.parse(body.get_string_from_utf8()) != OK or typeof(decoder.data) != TYPE_DICTIONARY:
		_failure("Respuesta no válida. Puedes reintentar el mismo envío.", true)
		return
	var payload: Dictionary = decoder.data
	if code < 200 or code >= 300:
		var exchange_errors := {"EXCHANGE_PC_REQUIRED":"Confirma el intercambio en el PC de casa.","MEET_EXCHANGE_PEER_FIRST":"Habla de intercambiar código con esa persona primero.","EXCHANGE_OWNED_CODE_REQUIRED":"Necesitas esa copia propia. Un préstamo o una aportación de otra persona no sirve.","EXCHANGE_DISABLED":"Los intercambios no están activos en este servidor.","INDEPENDENT_REQUIRED":"Termina tu contrato corporativo en Correo para intercambiar."}
		exchange_errors.merge({"PARTNER_NOT_PRESENT":"Debes hablar con esa persona en su localización.","WIRED_CONNECTION_REQUIRED":"Completa primero tu conexión a la Wired."})
		if pending_endpoint == "code-exchange":
			_failure(str(exchange_errors.get(str(payload.get("detail","")),payload.get("detail","No se pudo completar el intercambio."))),code >= 500)
			return
		var errors := {"WORKSHOP_WRONG_LOCATION":"Debes usar el PC de casa, el aula o el terminal del café según la acción.", "LESSON_REQUIRED":"Pide las reglas al profesor primero.", "SCAN_MODULE_REQUIRED":"Compila Exploración y conecta suficientes equipos.", "INSPECT_RELAY_FIRST":"Examina ese armario en persona antes de escanearlo.", "OFFERS_NOT_AVAILABLE":"Las ofertas llegan al completar la misión del Juego de la Vida."}
		errors.merge({"PARTNER_NOT_PRESENT":"Debes hablar con esa persona en su localización.", "INDEPENDENT_REQUIRED":"Termina tu contrato corporativo para colaborar como independiente.", "PARTNER_CONDITION_REQUIRED":"Todavía no cumples la condición de ese colaborador.", "MEET_PARTNER_FIRST":"Habla de la red con esa persona antes de invitarla.", "ASSET_NOT_AVAILABLE":"Conecta el equipo y comprueba que sea tuyo, sin préstamo corporativo.", "CIRCLE_PC_REQUIRED":"Gestiona el círculo desde el PC de casa.", "INVALID_CIRCLE_NAME":"Escribe un nombre de entre 1 y 32 caracteres.", "PARTNER_ALREADY_COMMITTED":"Esa persona ya participa en un círculo.", "ALREADY_IN_CIRCLE":"Ya perteneces a un círculo."})
		errors.merge({"CAFE_REQUIRED":"Debes jugar desde el terminal de Kissa Café.", "EVENT_NOT_OPEN":"Esta edición aún no ha abierto o ya ha cerrado. Consulta el calendario.", "EVENT_ATTEMPTS_USED":"Has utilizado los tres intentos de esta edición.", "EVENT_RUN_REQUIRED":"Abre un intento de este torneo desde el terminal.", "EVENT_ALREADY_FINISHED":"Ese intento ya tiene un resultado guardado."})
		_failure(str(errors.get(str(payload.get("detail", "")), "Acción rechazada: " + str(payload.get("detail", "respuesta no válida")))), false)
		return
	WorldApi.snapshot = payload.state
	WorldApi.snapshot_updated.emit(payload.state)
	var response: Dictionary = payload.result
	status = str(response.get("text", "Guardado."))
	if response.has("frames"):
		frames = response.frames
		frame_index = 0
	if response.has("board"):
		arcade = response.board
		run_id = response.run_id
		run_endpoint = pending_endpoint
		run_event = str(response.get("event_id", ""))
		run_closes = int(response.get("closes", 0))
		moves = ""
		courier = Vector2i(int(arcade.start[0]), int(arcade.start[1]))
		collected.clear()
		if is_snake():
			snake_model.reset(arcade)
			snake_elapsed = -0.75
	if is_open(): _render()
