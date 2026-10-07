extends SceneTree
## The dialogue as a visual novel: a text box along the bottom with the speaker's
## name on a tab in their colour, narration dimmer than what is said, the answers as
## buttons above the box. Ryoko and the teacher (in either language) talk with their
## drawn portrait beside the text, which starts past it; it comes in once per
## conversation, not on every answer; anyone else, a plain notice or a closed
## dialogue shows none.
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures.append(message)
		push_error(message)

func frames(count: int = 3) -> void:
	for i in range(count):
		await process_frame

func run() -> void:
	var dialog := root.get_node("EventDialog")
	var choices: Array[Dictionary] = [{"id": "ASK_SCHOOL", "text": "«¿Fuiste alumna del profesor?»"}]
	for path in dialog.PORTRAITS.values():
		var texture: Texture2D = load(path)
		check(texture != null and texture.get_height() >= 600, "a portrait does not load: " + path)

	# Ryoko: the wait, then her answer. The portrait comes in once.
	dialog.show_event("RYOKO", "...")
	await frames()
	check(dialog.portrait.visible and dialog.portrait_key == "RYOKO", "Ryoko talks without her portrait")
	check(dialog.text_margin.get_theme_constant("margin_left") == int(dialog.TEXT_LEFT_PORTRAIT),
		"the text does not move aside for the portrait")
	check(dialog.tab_style.bg_color == dialog.ACCENTS.RYOKO and dialog.title_label.uppercase, "Ryoko's name tab is not hers")
	await create_timer(0.4).timeout
	dialog.show_choices("PROLOGUE_RYOKO", "Ryoko", "«Te manda el profesor.»", choices)
	await frames()
	check(dialog.portrait.modulate.a == 1.0 and dialog.portrait.position.x == dialog.PORTRAIT_LEFT,
		"the portrait comes in again on every answer")
	var face_right: float = dialog.portrait.get_global_rect().position.x + dialog.portrait.get_global_rect().size.x * 0.68
	check(face_right < dialog.body_label.get_global_rect().position.x, "the text runs over the face")
	var screen := root.get_visible_rect()
	check(screen.encloses(dialog.panel.get_global_rect()) and dialog.panel.get_global_rect().position.y > screen.size.y * 0.6,
		"the text box is not along the bottom")
	check(dialog.choices_scroll.get_global_rect().end.y <= dialog.panel.get_global_rect().position.y,
		"the answers cover the text box")
	var answer: Button = dialog.choices_box.get_child(0)
	check(answer.alignment == HORIZONTAL_ALIGNMENT_LEFT and answer.get_theme_stylebox("normal").corner_radius_top_left >= 16,
		"the answers are not rounded buttons")
	await create_timer(1.8).timeout
	check(dialog.body_label.visible_ratio == 1.0, "the text is not shown whole after it is typed")

	# Narration dimmer than what is said, in either language; brackets in the text stay text.
	check(dialog.styled("Te mira. «Hola.»") == "[color=#%s]Te mira. [/color]«Hola.»" % dialog.NARRATION.to_html(false),
		"narration and speech look the same")
	check(dialog.styled("She looks. “Hi.”").ends_with("“Hi.”") and dialog.styled("[OK]") == "[lb]OK]",
		"English speech or brackets are mishandled")

	# The teacher, in Spanish or in English.
	dialog.show_event("K", "...")
	await frames()
	check(dialog.portrait.visible and dialog.portrait.texture.resource_path.ends_with("k.svg")
		and dialog.tab_style.bg_color == dialog.ACCENTS.K, "K talks without his portrait")
	for title in ["PROFESOR", "Profesor", "Teacher"]:
		dialog.show_event(title, "...")
		await frames()
		check(dialog.portrait.visible and dialog.portrait.texture.resource_path.ends_with("profesor.svg"),
			"the teacher has no portrait as " + title)

	# Anyone else, or a plain notice: no portrait, the text centred.
	dialog.show_event("AVISO", "Un aviso cualquiera.")
	await frames()
	check(not dialog.portrait.visible and dialog.text_margin.get_theme_constant("margin_left") == int(dialog.TEXT_LEFT),
		"a plain notice shows a portrait")
	check(dialog.continue_button.is_visible_in_tree() and dialog.tab_style.bg_color == dialog.ACCENT, "a notice has no way to close it")
	dialog.show_event("RYOKO", "...")
	await frames()
	dialog.close_event()
	await frames()
	check(not dialog.portrait.visible and dialog.portrait_key.is_empty(), "the portrait stays after the dialogue closes")

	print("PORTRAITS_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
