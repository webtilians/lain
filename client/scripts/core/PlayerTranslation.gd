extends Translation
## Dynamic UI strings are matched as complete templates. Captures (player
## names, identifiers, numbers) are substituted verbatim, never translated.
var catalog: Dictionary = {}
var patterns: Array = []

func configure(data: Dictionary) -> void:
	catalog = data
	locale = "en"
	var token := RegEx.new()
	token.compile("\\{\\w+\\}|%[-+0-9.]*[sdf]")
	var sources := catalog.keys()
	sources.sort_custom(func(a, b): return str(a).length() > str(b).length())
	for source in sources:
		var slots := token.search_all(source)
		if slots.is_empty():
			continue
		var pattern := "^"
		var offset := 0
		var names: Array = []
		for slot in slots:
			pattern += _escape(source.substr(offset, slot.get_start() - offset)) + "([^\\n]*?)"
			offset = slot.get_end()
			names.append(slot.get_string())
		pattern += _escape(source.substr(offset)) + "$"
		var matcher := RegEx.new()
		if matcher.compile(pattern) == OK:
			patterns.append({"regex": matcher, "target": str(catalog[source]), "slots": names})

func _escape(value: String) -> String:
	var result := ""
	for character in value:
		if character in "\\.^$|?*+()[]{}":
			result += "\\"
		result += character
	return result

func render(source: String) -> String:
	if catalog.has(source):
		return str(catalog[source])
	for item in patterns:
		var found: RegExMatch = item.regex.search(source)
		if found == null:
			continue
		var target: String = item.target
		# Replace target slots in one pass: inserted names cannot become tokens.
		var result := ""
		var cursor := 0
		for index in range(item.slots.size()):
			var slot: String = item.slots[index]
			var position := target.find(slot, cursor)
			if position < 0:
				continue
			result += target.substr(cursor, position - cursor) + found.get_string(index + 1)
			cursor = position + slot.length()
		return result + target.substr(cursor)
	if source.contains("\n"):
		var lines := source.split("\n")
		for index in range(lines.size()):
			lines[index] = render(lines[index])
		return "\n".join(lines)
	var trimmed := source.strip_edges()
	if trimmed != source and not trimmed.is_empty():
		var translated := render(trimmed)
		if translated != trimmed:
			var start := source.find(trimmed)
			return source.substr(0, start) + translated + source.substr(start + trimmed.length())
	return source

func _get_message(src_message: StringName, _context: StringName) -> StringName:
	# Godot falls back to this catalogue for locales without one; Spanish is the source.
	if not TranslationServer.get_locale().begins_with("en"):
		return &""
	var source := String(src_message)
	var translated := render(source)
	return StringName(translated) if translated != source else &""
