extends RefCounted
## Presentation only. Ownership, capacity, acceptance and compilation are server-owned.
func render(ui: Node) -> void:
	var state: Dictionary = ui.circle_data()
	var group = state.get("group")
	ui.label(ui.content,"CÍRCULO INDEPENDIENTE · Colaboración local con PNJ")
	ui.label(ui.content,"Cada modelo y fragmento cuenta una vez. El montaje compartido y el personal son independientes; sus capacidades no se suman.")
	if group == null:
		var box: VBoxContainer = ui.scrolling(ui.content)
		ui.label(box,"Todavía no perteneces a un círculo. Habla con Ryoko en AZUL y con el técnico en el terminal de Kissa Café.")
		var name := LineEdit.new()
		name.name = "CircleName"
		name.max_length = 32
		name.placeholder_text = "Nombre del círculo"
		name.text = ui.circle_name_draft
		name.text_changed.connect(func(value: String): ui.circle_name_draft = value)
		box.add_child(name)
		var create: Button = ui.button(box,"Crear círculo",func(): ui._send_circle("CREATE",{"name":name.text}))
		create.disabled = not bool(state.get("independent",false))
		if create.disabled: ui.label(box,"Termina tu contrato corporativo en Correo para crear una red independiente.")
		contacts(ui,box,state,[])
		return
	if ui.circle_draft_group != int(group.id):
		ui.circle_draft_group = int(group.id)
		ui.circle_draft = str(group.draft)
	ui.label(ui.content,str(group.name)+" · montaje compartido "+str(int(group.cost))+"/"+str(int(group.capacity))+" unidades · "+("Sin programa activo" if group.modules.is_empty() else ", ".join(group.modules)))
	var nav := HBoxContainer.new()
	ui.content.add_child(nav)
	for title in ["Grupo","Aportaciones","Programa","Historial"]:
		var b: Button = ui.button(nav,title,func(): ui.circle_tab = title; ui._render())
		b.disabled = ui.circle_tab == title
	match ui.circle_tab:
		"Programa": program(ui,group)
		"Aportaciones": resources(ui,group)
		"Historial":
			var box: VBoxContainer = ui.scrolling(ui.content)
			for event in group.events:
				ui.label(box,"Minuto "+str(int(event.minute))+" · "+str(event.text))
		_:
			var box: VBoxContainer = ui.scrolling(ui.content)
			var members: Array = []
			for member in group.members:
				members.append(str(member.id))
				ui.label(box,str(member.name)+" · "+("Colaborador PNJ" if member.kind=="NPC" else "Tu cuenta"))
				if member.kind=="NPC":
					ui.button(box,"Finalizar colaboración con "+str(member.name),ui._send_circle.bind("REMOVE",{"target":member.id}))
			contacts(ui,box,state,members)
			if not state.independent: ui.label(box,"Tu contrato corporativo suspende tus aportaciones y el acceso al montaje compartido. Puedes retirar recursos o disolver el círculo.")
			ui.button(box,"Disolver el círculo…",func(): ui.circle_confirm_leave = true; ui._render())
			if ui.circle_confirm_leave:
				ui.label(box,"Se desconectará el programa compartido. Cada miembro conserva sus recursos y tu programa personal sigue intacto.")
				ui.button(box,"Confirmar disolución",ui._send_circle.bind("LEAVE",{}))
				ui.button(box,"Mantener el círculo",func(): ui.circle_confirm_leave = false; ui._render())

func contacts(ui: Node, box: Node, state: Dictionary, members: Array) -> void:
	for peer in state.get("contacts",[]):
		if str(peer.id) in members: continue
		ui.label(box,str(peer.name)+" · PNJ · "+("AZUL" if peer.location=="NIGHTCLUB" else "Kissa Café")+"\n"+str(peer.motive)+"\n"+str(peer.condition))
		if not peer.met:
			ui.label(box,"Habla de crear una red con esta persona primero.")
		elif not peer.available:
			ui.label(box,"Ya colabora con otro círculo.")
		elif state.get("group") != null:
			var invite: Button = ui.button(box,"Invitar a "+str(peer.name),ui._send_circle.bind("INVITE",{"target":peer.id}))
			invite.disabled = not bool(peer.ready)
		else:
			ui.label(box,"Contacto conocido. Crea el círculo para invitarlo.")

func resources(ui: Node, group: Dictionary) -> void:
	var columns := HBoxContainer.new()
	columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	columns.add_theme_constant_override("separation",24)
	ui.content.add_child(columns)
	var box: VBoxContainer = ui.scrolling(columns)
	ui.label(box,"TUS RECURSOS · Aportar permite usar el recurso dentro del círculo; no transfiere la propiedad. Conecta los equipos en Dispositivos.")
	for item in group.eligible:
		var title: String = str(item.model)
		for asset in ui.data().get("assets",[]):
			if str(asset.id)==str(item.id): title = str(asset.name)
		var b: Button = ui.button(box,("Retirar " if item.shared else "Aportar ")+title,ui._send_circle.bind("CONTRIBUTE",{"id":item.id,"active":not bool(item.shared)}))
		b.disabled = not bool(item.shared) and not bool(item.available)
		if not str(item.reason).is_empty(): ui.label(box,str(item.reason))
	var shared: VBoxContainer = ui.scrolling(columns)
	shared.get_parent().size_flags_stretch_ratio = 1.6
	ui.label(shared,"APORTACIONES DEL CÍRCULO · Una copia de cada modelo y función")
	for item in group.contributions:
		var acquired: String = "adquisición sin fecha comunicada" if item.acquired_minute == null else "adquirido min "+str(int(item.acquired_minute))
		ui.label(shared,str(item.name)+" · "+str(item.owner)+" · "+("Cuenta" if item.counted else str(item.reason))+"\nProcedencia: "+str(item.source)+" · "+acquired+" · aportado min "+str(int(item.shared_minute)))

func program(ui: Node, group: Dictionary) -> void:
	var row := HBoxContainer.new()
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation",16)
	ui.content.add_child(row)
	var editor := CodeEdit.new()
	editor.name = "CircleEditor"
	editor.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	editor.size_flags_stretch_ratio = 1.5
	editor.gutters_draw_line_numbers = true
	editor.text = ui.circle_draft
	editor.text_changed.connect(func(): ui.circle_draft = editor.text)
	row.add_child(editor)
	var side: VBoxContainer = ui.scrolling(row)
	ui.label(side,"FRAGMENTOS APORTADOS")
	for item in group.library:
		ui.label(side,str(item.name)+" · "+str(int(item.cost))+" unidades")
		var line := 'use("'+str(item.id)+'")'+"\n"
		ui.button(side,"Insertar "+str(item.name),func():
			if not editor.text.is_empty() and not editor.text.ends_with("\n"): editor.text += "\n"
			editor.text += line
			ui.circle_draft = editor.text)
	ui.button(ui.content,"Guardar, compilar y activar círculo",func(): ui._send_circle("COMPILE",{"source":editor.text}))
	ui.label(ui.content,"Compilar guarda el borrador. Una retirada puede detener el montaje; vuelve a compilar tras reparar los recursos. El programa personal no se modifica.")
