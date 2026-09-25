extends CanvasLayer
## Chapter interface: the server supplies every clue, choice and consequence.
signal archive_saved(message: String)
const OWNER := "CHAPTER_ONE"
var request: HTTPRequest
var busy := false
var journal_request := false
var pending: Dictionary = {}
var choices: Dictionary = {}
var normal_conversation := Callable()
var terminal_context := false
var current_actor := ""
var installed_scene := 0
var notified_run := -1
var toast: Label
var toast_until := 0

func _ready() -> void:
	layer = 95
	request = HTTPRequest.new()
	request.timeout = 20
	add_child(request)
	request.request_completed.connect(_completed)
	EventDialog.choice_selected.connect(_choose)
	toast = Label.new()
	toast.position = Vector2(30,180)
	toast.add_theme_font_size_override("font_size",16)
	toast.add_theme_color_override("font_color",Color("bed4c4"))
	toast.add_theme_color_override("font_shadow_color",Color("161d28"))
	toast.add_theme_constant_override("shadow_offset_x",2)
	toast.add_theme_constant_override("shadow_offset_y",2)
	toast.hide()
	add_child(toast)
	WorldApi.snapshot_updated.connect(_snapshot)

func active() -> bool:
	return bool(WorldApi.snapshot.get("chapter_one",{}).get("active",false))

func can_talk(actor: String) -> bool:
	return active() and actor in WorldApi.snapshot.get("chapter_one",{}).get("characters",[])

func _snapshot(state: Dictionary) -> void:
	var chapter: Dictionary = state.get("chapter_one",{})
	if not chapter.get("active",false):
		return
	var started := int(chapter.get("started_minute",0))
	if notified_run != started:
		notified_run = started
		toast.text = "WIRED · REMITENTE DESCONOCIDO\n«Has vuelto»."
		toast_until = Time.get_ticks_msec()+10000
		toast.show()

func _process(_delta: float) -> void:
	if Time.get_ticks_msec()>toast_until:
		toast.hide()
	var scene := get_tree().current_scene as Node3D
	if not active() or scene == null or scene.get_instance_id()==installed_scene:
		return
	installed_scene=scene.get_instance_id()
	var dressing := Node3D.new()
	dressing.name="ChapterObjects"
	dressing.set_script(load("res://scripts/world/ChapterObjects.gd"))
	dressing.set("location",str(WorldApi.snapshot.get("player",{}).get("location","")))
	scene.add_child(dressing)

func open_actor(actor: String, fallback: Callable = Callable()) -> void:
	if busy:
		return
	normal_conversation=fallback
	current_actor=actor
	terminal_context=false
	_send("TALK",actor,{"choice":"INTRO"})

func open_terminal() -> void:
	if busy:
		return
	normal_conversation=Callable()
	terminal_context=true
	_send("WIRED","OPEN",{})

func examine(target: String) -> void:
	if busy:
		return
	normal_conversation=Callable()
	terminal_context=false
	_send("EXAMINE",target,{"choice":"OPEN"})

func save_link(first: String, second: String, relation: String) -> void:
	_send("LINK","",{"first":first,"second":second,"relation":relation},true)

func save_hypothesis(text: String) -> void:
	_send("HYPOTHESIS","",{"text":text},true)

func _send(action: String, target: String, data: Dictionary, journal: bool = false) -> void:
	if busy:
		return
	journal_request=journal
	pending={"action":action,"target":target,"data":data,
		"request_id":"chapter_"+str(Time.get_unix_time_from_system()).replace(".","_")+"_"+str(Time.get_ticks_usec())}
	_dispatch()

func _dispatch() -> void:
	busy=true
	if not journal_request:
		EventDialog.show_choices(OWNER,"THE WIRED" if terminal_context else "...","Esperando respuesta...",[])
	WorldApi.begin_external_mutation()
	var err := request.request("http://127.0.0.1:8000/api/v1/chapter-one/action",
		PackedStringArray(["Content-Type: application/json"]),HTTPClient.METHOD_POST,JSON.stringify(pending))
	if err!=OK:
		busy=false
		WorldApi.end_external_mutation()
		_failure("No se pudo conectar con el servidor.")

func _completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	busy=false
	WorldApi.end_external_mutation()
	var payload = JSON.parse_string(body.get_string_from_utf8())
	if result!=HTTPRequest.RESULT_SUCCESS or typeof(payload)!=TYPE_DICTIONARY:
		_failure("Se ha perdido la respuesta. Puedes reintentar la misma petición.")
		return
	if code<200 or code>=300:
		var messages := {"CHARACTER_NOT_PRESENT":"Esa persona ya no está en este lugar.",
			"OBJECT_NOT_PRESENT":"Tienes que acercarte a esa fuente en su localización.",
			"TERMINAL_NOT_PRESENT":"La conexión remota se abre desde el ordenador de casa.",
			"CHAPTER_DECISION_ALREADY_MADE":"Esa decisión ya está guardada.",
			"INVALID_EVIDENCE_LINK":"Elige dos pistas distintas que hayas descubierto.",
			"INVALID_HYPOTHESIS":"Escribe una hipótesis de entre 1 y 500 caracteres."}
		_failure(messages.get(str(payload.get("detail","")),"No puedes realizar esa acción con la información actual."))
		return
	var state: Dictionary = payload.get("state",{})
	if not state.is_empty():
		WorldApi.snapshot=state
		WorldApi.snapshot_updated.emit(state)
	var event: Dictionary = payload.get("result",{})
	if journal_request:
		archive_saved.emit(str(event.get("text","Guardado.")))
	elif EventDialog.visible and EventDialog.current_owner_id==OWNER:
		_present(event)

func _present(event: Dictionary) -> void:
	choices.clear()
	var buttons: Array[Dictionary] = []
	for option in event.get("choices",[]):
		var key := str(buttons.size())
		choices[key]=option
		buttons.append({"id":key,"text":str(option.get("text","..."))})
	if normal_conversation.is_valid():
		buttons.append({"id":"NORMAL","text":"Hablar de otra cosa."})
		if current_actor=="PROFESSOR" and Workshop.active():
			buttons.append({"id":"LIFE","text":"Pedir las reglas del Juego de la Vida."})
	if terminal_context:
		if NetworkConflict.active():
			buttons.append({"id":"NETWORK","text":"Consultar el control de los enlaces."})
		buttons.append({"id":"SIGNALS","text":"Consultar las otras señales de la Wired."})
	buttons.append({"id":"CLOSE","text":"Cerrar la conexión." if terminal_context else "Dejarlo por ahora."})
	EventDialog.show_choices(OWNER,str(event.get("speaker","...")),str(event.get("text","")),buttons)

func _failure(message: String) -> void:
	if journal_request:
		archive_saved.emit(message)
	elif EventDialog.visible and EventDialog.current_owner_id==OWNER:
		EventDialog.show_choices(OWNER,"SIN RESPUESTA",message,[{"id":"RETRY","text":"Reintentar."},{"id":"CLOSE","text":"Cerrar."}])

func _choose(owner: String, selected: String) -> void:
	if owner!=OWNER or busy:
		return
	if selected=="RETRY":
		_dispatch() # Same id: a lost response cannot apply a choice twice.
	elif selected=="LIFE":
		Workshop.open_lesson()
	elif selected=="NETWORK":
		NetworkConflict.open_terminal()
	elif selected=="CLOSE":
		EventDialog.close_event()
	elif selected=="NORMAL":
		EventDialog.close_event()
		if normal_conversation.is_valid():
			normal_conversation.call()
	elif selected=="SIGNALS":
		EventDialog.close_event()
		var terminal = get_tree().get_first_node_in_group("terminal_ui")
		if terminal!=null:
			terminal.open_terminal()
	elif choices.has(selected):
		var option: Dictionary = choices[selected]
		_send(str(option.action),str(option.get("target","")),option.get("data",{}))
