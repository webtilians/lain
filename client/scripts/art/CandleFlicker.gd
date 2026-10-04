extends Node
## Visual 0.12: gentle candle flicker for an interior light (presentation only).
var light: Light3D
var base_energy := 1.0
var phase := 0.0

func _ready() -> void:
	light = get_parent() as Light3D
	if light == null:
		queue_free()
		return
	base_energy = light.light_energy
	phase = randf() * 100.0

func _process(delta: float) -> void:
	phase += delta
	var wobble := sin(phase * 7.3) * 0.05 + sin(phase * 13.1 + 1.7) * 0.04 + sin(phase * 23.7) * 0.025
	light.light_energy = base_energy * (0.9 + wobble)
