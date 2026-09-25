extends CanvasLayer
## Public relay state and authoritative responses. Never computes battle results.
const OWNER := "NETWORK_CONFLICT"
var request: HTTPRequest
var busy := false
var pending: Dictionary = {}
var options: Dictionary = {}
var installed_scene := 0
var warning: Label
var observed_report := -1
var notice := ""
var notice_until := 0

func _ready() -> void:
	layer=94
	request=HTTPRequest.new()
	request.timeout=15
	add_child(request)
	request.request_completed.connect(_completed)
	EventDialog.choice_selected.connect(_choose)
	warning=Label.new()
	warning.position=Vector2(28,120)
	warning.size.x=520
	warning.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	warning.add_theme_font_size_override("font_size",17)
	warning.add_theme_color_override("font_color",Color("e7b493"))
	warning.add_theme_color_override("font_shadow_color",Color("151920"))
	warning.add_theme_constant_override("shadow_offset_x",2)
	warning.add_theme_constant_override("shadow_offset_y",2)
	add_child(warning)
	warning.hide()

func active() -> bool:
	return bool(WorldApi.snapshot.get("network_conflict",{}).get("active",false))

func _process(_delta: float) -> void:
	var network: Dictionary=WorldApi.snapshot.get("network_conflict",{})
	var reports: Array=network.get("reports",[])
	if not reports.is_empty():
		var latest:=int(reports[0].get("id",0))
		if observed_report>=0 and latest!=observed_report and reports[0].source=="RELAY_TELEMETRY":
			notice="WIRED · NUEVO INFORME\n"+str(reports[0].text)
			notice_until=Time.get_ticks_msec()+10000
		observed_report=latest
	var threats: Array=network.get("pending",[])
	warning.visible=(not threats.is_empty() or Time.get_ticks_msec()<notice_until) and not CharacterJournal.backdrop.visible
	if not threats.is_empty():
		warning.text="WIRED · INTERVENCIÓN DETECTADA\nRestan "+str(int(threats[0].remaining))+" min del mundo  ·  J: revisar enlaces"
	else:
		warning.text=notice
	var scene:=get_tree().current_scene as Node3D
	if not active() or scene==null or installed_scene==scene.get_instance_id():
		return
	installed_scene=scene.get_instance_id()
	var objects:=Node3D.new()
	objects.name="ConflictObjects"
	objects.set_script(load("res://scripts/world/ConflictObjects.gd"))
	objects.set("location",str(WorldApi.snapshot.get("player",{}).get("location","")))
	scene.add_child(objects)

func interact(relay: String, personnel: bool=false) -> void:
	if busy or EventDialog.visible:
		return
	_send("TALK" if personnel else "OPEN",relay,"")

func _send(action: String, relay: String, rival: String) -> void:
	if busy: return
	pending={"action":action,"relay":relay,"rival":rival,
		"request_id":"network_"+str(Time.get_unix_time_from_system()).replace(".","_")+"_"+str(Time.get_ticks_usec())}
	_dispatch()

func _dispatch() -> void:
	busy=true
	WorldApi.begin_external_mutation()
	EventDialog.show_choices(OWNER,"WIRED","Estableciendo enlace...",[])
	var error:=request.request("http://127.0.0.1:8000/api/v1/network/action",
		PackedStringArray(["Content-Type: application/json"]),HTTPClient.METHOD_POST,JSON.stringify(pending))
	if error!=OK:
		busy=false
		WorldApi.end_external_mutation()
		_failure("No se pudo conectar. Puedes reintentar la misma petición.")

func _completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	busy=false
	WorldApi.end_external_mutation()
	var payload=JSON.parse_string(body.get_string_from_utf8())
	if result!=HTTPRequest.RESULT_SUCCESS or typeof(payload)!=TYPE_DICTIONARY:
		_failure("La respuesta se perdió. Reintentar no duplica una operación.")
		return
	if code<200 or code>=300:
		var messages: Dictionary={"NETWORK_COOLDOWN":"El enlace se está reajustando. Espera al siguiente avance del reloj de la ciudad.",
			"RELAY_NOT_PRESENT":"Tienes que estar junto al enlace o a su personal.",
			"CURRENT_PROOF_REQUIRED":"Esa orden ya no está activa. Vuelve a examinar el tráfico durante una intervención.",
			"DEFENSE_NOT_AVAILABLE":"Necesitas control propio y un espacio libre para preparar esa defensa.",
			"NO_PLAYER_CONTROL":"Ya no conservas control en ese enlace.",
			"INSPECT_RELAY_FIRST":"Examina el enlace antes de intervenir.",
			"INVALID_RIVAL":"Esa cuenta ya no tiene control disponible.",
			"NO_CORPORATE_CONTROL":"Todo el control de este enlace está en manos de usuarios."}
		_failure(messages.get(str(payload.get("detail","")),"Esta operación no está disponible ahora."))
		return
	WorldApi.snapshot=payload.state
	WorldApi.snapshot_updated.emit(payload.state)
	if EventDialog.visible and EventDialog.current_owner_id==OWNER:
		_present(payload.result)

func _present(event: Dictionary) -> void:
	options.clear()
	var buttons: Array[Dictionary]=[]
	for option in event.get("choices",[]):
		var id:=str(buttons.size())
		options[id]=option
		buttons.append({"id":id,"text":str(option.text)})
	buttons.append({"id":"ARCHIVE","text":"Abrir el archivo de enlaces."})
	buttons.append({"id":"CLOSE","text":"Cerrar y volver al barrio."})
	EventDialog.show_choices(OWNER,str(event.get("speaker","WIRED")),str(event.get("text","")),buttons)

func _failure(text: String) -> void:
	if EventDialog.visible and EventDialog.current_owner_id==OWNER:
		EventDialog.show_choices(OWNER,"ENLACE",text,[{"id":"RETRY","text":"Reintentar."},{"id":"CLOSE","text":"Cerrar."}])

func _choose(owner: String, selected: String) -> void:
	if owner!=OWNER or busy: return
	if selected=="CLOSE":
		EventDialog.close_event()
	elif selected=="ARCHIVE":
		open_archive()
	elif selected=="RETRY":
		_dispatch()
	elif options.has(selected):
		var option: Dictionary=options[selected]
		_send(str(option.action),str(option.relay),str(option.get("rival","")))

func open_archive() -> void:
	EventDialog.close_event()
	CharacterJournal.open_journal()
	CharacterJournal._choose_view("NETWORK","")

func open_terminal() -> void:
	if busy: return
	EventDialog.close_event()
	var data: Dictionary=WorldApi.snapshot.get("network_conflict",{})
	var text: String=str(data.get("corporation",""))+" · "+str(data.get("corporate_control",0))+"% del control\n\n"
	var choices: Array[Dictionary]=[]
	for relay in data.get("relays",[]):
		text+=str(relay.name)+": tú "+str(int(relay.mine))+"%\n"
		if int(relay.mine)>0:
			choices.append({"text":"Ocultar: "+str(relay.name)+" · ceder hasta 5 puntos.","action":"GO_DARK","relay":str(relay.id)})
	text+="\nPara disputar un enlace debes encontrar su armario en la ciudad. Desde casa puedes ocultar una conexión tuya."
	_present({"speaker":"WIRED · ENLACES","text":text,"choices":choices})
