extends RefCounted
## Offers and receipts only; the server decides ownership and completion.
var selected: Dictionary = {}
var confirm_offer := ""
var confirm_asset := ""
var show_history := false

func render(ui: Node) -> void:
	var state: Dictionary = ui.exchange_data()
	ui.label(ui.content,"INTERCAMBIOS · Contactos PNJ")
	ui.label(ui.content,"Compartís copias de código y conserváis los originales. Cada función cuenta una sola vez. Lo recibido necesita capacidad y compilación en Código.")
	var nav := HBoxContainer.new()
	ui.content.add_child(nav)
	ui.button(nav,"Propuestas",func(): show_history = false; ui._render()).disabled = not show_history
	ui.button(nav,"Recibos y procedencia",func(): show_history = true; ui._render()).disabled = show_history
	var box: VBoxContainer = ui.scrolling(ui.content)
	if show_history:
		if state.get("history",[]).is_empty(): ui.label(box,"Todavía no has completado ningún intercambio.")
		for receipt in state.get("history",[]):
			ui.label(box,"MINUTO "+str(int(receipt.minute))+" · "+str(receipt.peer_name))
			ui.label(box,"Compartiste "+str(receipt.sent.name)+" · Procedencia: "+str(receipt.sent.source)+" · adquirido min "+str(int(receipt.sent.acquired_minute)))
			ui.label(box,"Recibiste "+str(receipt.received.name)+" · "+str(receipt.received.source)+" · adquirido min "+str(int(receipt.received.acquired_minute))+"\nLa fecha de adquisición original del PNJ no se conoce. Tu copia te pertenece y permanece aunque termine su colaboración.")
			box.add_child(HSeparator.new())
		return
	for offer in state.get("offers",[]):
		ui.label(box,str(offer.name)+" · "+("AZUL" if offer.location=="NIGHTCLUB" else "Kissa Café"))
		if not offer.met:
			ui.label(box,str(offer.reason))
		else:
			ui.label(box,str(offer.motive))
			ui.label(box,"Compartes: "+str(offer.wanted_name)+"  →  Recibes: "+str(offer.given_name))
			if not str(offer.reason).is_empty(): ui.label(box,str(offer.reason))
			if offer.ready:
				var picker := OptionButton.new()
				picker.name = "Copy_"+str(offer.id)
				picker.clip_text = true
				picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				box.add_child(picker)
				var choices: Array = offer.copies
				var current := 0
				for i in choices.size():
					picker.add_item(str(choices[i].source)+" · min "+str(int(choices[i].minute)))
					if selected.get(offer.id,"")==choices[i].id: current = i
				picker.select(current)
				selected[offer.id] = str(choices[current].id)
				picker.item_selected.connect(func(i: int): selected[offer.id] = str(choices[i].id); confirm_offer = ""; ui._render())
				ui.button(box,"Revisar intercambio con "+str(offer.name),func():
					confirm_offer = str(offer.id); confirm_asset = str(selected[offer.id]); ui._render()).disabled = ui.busy
				if confirm_offer == offer.id and confirm_asset == selected[offer.id]:
					ui.label(box,"Enviarás este fragmento y su procedencia a "+str(offer.name)+". Recibirás una copia propia de "+str(offer.given_name)+". No se comparten recuerdos, conversaciones ni otros archivos.")
					ui.button(box,"Confirmar copias",func():
						ui._send_exchange("ACCEPT",{"offer":str(offer.id),"asset":confirm_asset})
						confirm_offer = "").disabled = ui.busy
					ui.button(box,"Cancelar",func(): confirm_offer = ""; ui._render())
		box.add_child(HSeparator.new())
