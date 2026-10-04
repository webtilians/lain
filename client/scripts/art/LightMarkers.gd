extends Node3D
## Visual 0.12: turns empties exported by the Blender generators into lights
## and neon signs. LIGHT_<kind>* becomes a light; SIGNV_<axis>_<neon>* becomes
## a vertical kanji sign facing that Blender axis. Presentation only.
## Attach to a model instance, or call light_up() on one.

# kind: [type, colour, energy, range, spot angle]
const LIGHTS := {
	"sodium": ["spot", Color("ff9540"), 9.0, 13.0, 58.0],
	"warm": ["omni", Color("ffb46b"), 2.2, 4.5, 0.0],
	"window": ["omni", Color("ffae62"), 1.3, 3.5, 0.0],
	"red": ["omni", Color("ff2a3a"), 2.2, 4.0, 0.0],
	"candle": ["omni", Color("ff9a45"), 2.6, 5.0, 0.0],
	"lantern": ["omni", Color("ffa24c"), 3.2, 8.0, 0.0],
	"fluo": ["omni", Color("d8f0ff"), 1.5, 4.0, 0.0],
	"magenta": ["omni", Color("ff3fb0"), 3.0, 6.0, 0.0],
	"cyan": ["omni", Color("40d8ff"), 3.0, 6.0, 0.0],
	"amber": ["omni", Color("ffae3a"), 3.0, 6.0, 0.0],
}
const NEON_COLOURS := {
	"neon": Color(0.5, 3.4, 4.2),
	"neon_magenta": Color(4.2, 0.7, 2.6),
	"neon_red": Color(4.6, 0.5, 0.6),
	"neon_amber": Color(4.2, 2.2, 0.5),
}
const WORDS := ["夜想", "血盟", "電脳", "迷宮", "終末", "月蝕", "廃墟", "闇市", "霊界", "無限", "零式", "黒猫", "赤灯", "深層"]
const FACING := {"px": PI / 2, "nx": -PI / 2, "py": PI, "ny": 0.0}
static var sign_font: Font

func _ready() -> void:
	light_up(self)

static func light_up(root: Node) -> void:
	for node in root.find_children("*", "Node3D", true, false):
		var label := str(node.name)
		if label.begins_with("LIGHT_"):
			add_light(node, label.get_slice("_", 1))
		elif label.begins_with("SIGNV_"):
			# Blender suffixes duplicates (".001" becomes "_001" on import).
			var neon := "neon"
			for key in ["neon_magenta", "neon_red", "neon_amber"]:
				if key in label:
					neon = key
			add_sign(node, label.get_slice("_", 1), neon)

static func add_light(marker: Node3D, kind: String) -> void:
	if not LIGHTS.has(kind) or marker.get_child_count() > 0:
		return
	var spec: Array = LIGHTS[kind]
	var light: Light3D
	if spec[0] == "spot":
		var spot := SpotLight3D.new()
		spot.spot_range = spec[3]
		spot.spot_angle = spec[4]
		spot.spot_attenuation = 1.1
		spot.rotation_degrees = Vector3(-90, 0, 0)
		light = spot
	else:
		var omni := OmniLight3D.new()
		omni.omni_range = spec[3]
		omni.omni_attenuation = 1.3
		light = omni
	light.light_color = spec[1]
	light.light_energy = spec[2]
	light.light_specular = 1.0
	light.shadow_enabled = false
	if kind in ["window", "fluo"]:
		light.set_meta("detail_light", true)
	marker.add_child(light)
	if kind == "candle":
		var flicker := Node.new()
		flicker.set_script(load("res://scripts/art/CandleFlicker.gd"))
		light.add_child(flicker)

static func add_sign(marker: Node3D, axis: String, neon: String) -> void:
	if marker.get_child_count() > 0:
		return
	if sign_font == null:
		var system := SystemFont.new()
		system.font_names = PackedStringArray(["Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans CJK JP", "Noto Sans JP"])
		system.font_weight = 700
		sign_font = system
	var word: String = WORDS[absi(hash(marker.global_position.snapped(Vector3.ONE * 0.1))) % WORDS.size()]
	var text := ""
	for i in word.length():
		text += word[i] + ("\n" if i < word.length() - 1 else "")
	var sign := Label3D.new()
	sign.text = text
	sign.font = sign_font
	sign.font_size = 96
	sign.pixel_size = 0.0045
	sign.line_spacing = -8.0
	sign.outline_size = 10
	sign.outline_modulate = Color(0.05, 0.02, 0.05)
	sign.modulate = NEON_COLOURS.get(neon, NEON_COLOURS["neon_magenta"])
	sign.double_sided = false
	sign.rotation.y = FACING.get(axis, 0.0)
	marker.add_child(sign)
