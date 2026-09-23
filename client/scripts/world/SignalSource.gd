extends StaticBody3D

@export var node_id := "NODE_07"

var busy := false
var pending_action := ""

func _ready() -> void:
	add_to_group("interactable")

	EventDialog.choice_selected.connect(
		_on_choice_selected
	)

	WorldApi.action_resolved.connect(
		_on_action_resolved
	)

	WorldApi.api_error.connect(
		_on_api_error
	)

func interact() -> void:
	if busy or EventDialog.visible:
		return

	var situation: Dictionary = WorldApi.snapshot.get("station_case", {})
	var case_status := str(situation.get("status", "UNSEEN"))
	var description := (
		"Una estructura emite un pulso irregular.\n\n"
		+ "Puedes investigarla directamente o observarla sin intervenir."
	)
	var choices: Array[Dictionary] = [
		{"id": "INVESTIGATE", "text": "Investigar la señal"},
		{"id": "OBSERVE", "text": "Observar sin intervenir"},
	]
	if case_status == "TRACE_FOUND":
		description = (
			"Has encontrado un pulso ausente dentro de la secuencia.\n"
			+ "El rastro es tuyo: compartirlo o archivarlo tendrá "
			+ "consecuencias distintas para quienes están aquí."
		)
		choices.append({
			"id": "BROADCAST_TRACE",
			"text": "Difundir el rastro entre los presentes",
		})
		choices.append({
			"id": "ARCHIVE_TRACE",
			"text": "Archivar el rastro sin compartirlo",
		})
	elif case_status == "RESOLVED":
		description = str(situation.get("summary", description))
	choices.append({"id": "LEAVE", "text": "Alejarse"})
	EventDialog.show_choices(
		str(get_instance_id()),
		"NODE_07 // SEÑAL ANÓMALA",
		description,
		choices
	)

func _on_choice_selected(
	owner_id: String,
	choice_id: String
) -> void:
	if owner_id != str(get_instance_id()):
		return

	if not EventDialog.visible or busy:
		return

	if choice_id == "LEAVE":
		EventDialog.close_event()
		return

	if choice_id not in [
		"INVESTIGATE", "OBSERVE", "BROADCAST_TRACE", "ARCHIVE_TRACE"
	]:
		return

	busy = true
	pending_action = choice_id
	EventDialog.show_event(
		"NODE_07",
		"PROCESSING..."
	)
	WorldApi.step(choice_id, node_id)

func _on_action_resolved(
	result: Dictionary,
	updated_snapshot: Dictionary
) -> void:
	if not busy:
		return

	busy = false
	var action := pending_action
	pending_action = ""

	if not bool(result.get("accepted", false)):
		_show_rejection(result, updated_snapshot)
		return

	_show_success(action, updated_snapshot)

func _show_rejection(
	result: Dictionary,
	updated_snapshot: Dictionary
) -> void:
	var reason := str(result.get("reason", "UNKNOWN"))
	var player: Dictionary = updated_snapshot.get("player", {})
	var energy := float(player.get("energy", 0.0))
	var explanation := ""

	match reason:
		"NOT_ENOUGH_ENERGY":
			explanation = "No tienes energía suficiente para realizar esta acción."
		"TARGET_NOT_PRESENT":
			explanation = "La señal ya no se encuentra en esta localización."
		"NODE_INACTIVE":
			explanation = "La señal no está activa."
		"CASE_NOT_DISCOVERED":
			explanation = "Necesitas investigar NODE_07 antes de decidir."
		"CASE_ALREADY_RESOLVED":
			explanation = "Ya has tomado una decisión sobre este rastro."
		"CASE_NOT_PRESENT":
			explanation = "Debes estar junto a NODE_07 para decidir."
		_:
			explanation = "World Core no ha permitido ejecutar esta acción."

	EventDialog.show_event(
		"ACTION DENIED",
		explanation
		+ "\n\nREASON // " + reason
		+ "\nENERGY // %.2f" % energy
	)

func _show_success(
	action: String,
	updated_snapshot: Dictionary
) -> void:
	var station_case: Dictionary = updated_snapshot.get("station_case", {})
	if action in ["BROADCAST_TRACE", "ARCHIVE_TRACE"]:
		var witnesses := int(station_case.get("witness_count", 0))
		var explanation := (
			"Has compartido el rastro con %d presencias.\n"
			+ "Sus respuestas aparecerán en el diario (J) cuando reaccionen."
		) % witnesses if action == "BROADCAST_TRACE" else (
			"Has archivado el rastro sin compartirlo.\n"
			+ "Ningún personaje ha recibido este testimonio."
		)
		EventDialog.show_event("EL PULSO AUSENTE", explanation)
		return

	var known_nodes: Array = updated_snapshot.get(
		"known_nodes",
		[]
	)

	for node_data in known_nodes:
		if str(node_data.get("id", "")) != node_id:
			continue

		var belief_data = node_data.get("belief", {})
		if typeof(belief_data) != TYPE_DICTIONARY:
			break

		var confidence := float(
			belief_data.get("confidence", 0.0)
		) * 100.0
		var source := str(
			belief_data.get("source", "UNKNOWN")
		)

		if action == "INVESTIGATE":
			EventDialog.show_event(
				"INVESTIGATION COMPLETE",
				"Has investigado la señal en profundidad.\n\n"
				+ "Has descubierto un pulso ausente en la secuencia. "
				+ "Vuelve a interactuar con NODE_07 para decidir "
				+ "si compartir el rastro o archivarlo.\n\n"
				+ "SOURCE // " + source
				+ "\nCONFIDENCE // %.0f%%" % confidence
			)
		else:
			EventDialog.show_event(
				"OBSERVATION COMPLETE",
				"Has observado la señal sin intervenir.\n\n"
				+ "SOURCE // " + source
				+ "\nCONFIDENCE // %.0f%%" % confidence
			)

		return

	EventDialog.show_event(
		"ACTION COMPLETE",
		"La acción ha sido aceptada.\n\n"
		+ "Todavía no dispones de una interpretación de la señal."
	)

func _on_api_error(
	message: String
) -> void:
	if not busy:
		return

	busy = false
	pending_action = ""
	EventDialog.show_event(
		"CONNECTION ERROR",
		message
	)
