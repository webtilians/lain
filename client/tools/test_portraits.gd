extends SceneTree
## Dialogue portraits: Ryoko and the teacher (in either language) talk with their
## drawn portrait beside the text, which moves aside to leave it room; it comes in
## once per conversation, not on every answer; anyone else, a plain notice or a
## closed dialogue shows none.
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
	check(dialog.panel.offset_left == -315.0 + dialog.PORTRAIT_SHIFT, "the text does not move aside for the portrait")
	await create_timer(0.4).timeout
	dialog.show_choices("PROLOGUE_RYOKO", "Ryoko", "«Te manda el profesor.»", choices)
	await frames()
	check(dialog.portrait.modulate.a == 1.0 and dialog.portrait.position.x == dialog.PORTRAIT_LEFT,
		"the portrait comes in again on every answer")
	var face_right: float = dialog.portrait.get_global_rect().position.x + dialog.portrait.get_global_rect().size.x * 0.68
	check(face_right < dialog.panel.get_global_rect().position.x, "the text panel covers the face")

	# The teacher, in Spanish or in English.
	for title in ["PROFESOR", "Profesor", "Teacher"]:
		dialog.show_event(title, "...")
		await frames()
		check(dialog.portrait.visible and dialog.portrait.texture.resource_path.ends_with("profesor.svg"),
			"the teacher has no portrait as " + title)

	# Anyone else, or a plain notice: no portrait, the text centred.
	dialog.show_event("AVISO", "Un aviso cualquiera.")
	await frames()
	check(not dialog.portrait.visible and dialog.panel.offset_left == -315.0, "a plain notice shows a portrait")
	dialog.show_event("RYOKO", "...")
	await frames()
	dialog.close_event()
	await frames()
	check(not dialog.portrait.visible and dialog.portrait_key.is_empty(), "the portrait stays after the dialogue closes")

	print("PORTRAITS_", "FAILED" if failures else "OK")
	quit(1 if failures else 0)
