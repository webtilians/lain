extends Node3D

@onready var signal_label: Label = $HUD/Signal
@onready var confidence_label: Label = $HUD/Confidence
@onready var hint_label: Label = $HUD/Hint

func _ready() -> void:
	WorldApi.snapshot_updated.connect(_on_snapshot_updated)
	if not WorldApi.snapshot.is_empty():
		_render_snapshot(WorldApi.snapshot)

func _on_snapshot_updated(snapshot: Dictionary) -> void:
	_render_snapshot(snapshot)

func _render_snapshot(snapshot: Dictionary) -> void:
	var wired: Dictionary = snapshot.get("wired", {})
	var signals: Array = wired.get("signals", [])
	var node_signal: Dictionary = {}

	for signal_data in signals:
		if signal_data.get("node_id", "") == "NODE_07":
			node_signal = signal_data
			break

	if node_signal.is_empty():
		signal_label.text = "NODE_07 // UNKNOWN"
		confidence_label.text = ""
		hint_label.text = "E // INTERACT"
		return

	var verified := bool(node_signal.get("verified", false))
	var confidence := float(node_signal.get("confidence", 0.0)) * 100.0

	if verified:
		signal_label.text = "NODE_07 // VERIFIED"
		confidence_label.text = "DIRECT CONFIDENCE // %.0f%%" % confidence
		hint_label.text = "DIRECT SIGNAL CONFIRMED"
	else:
		signal_label.text = "NODE_07 // UNVERIFIED"
		confidence_label.text = "REMOTE CONFIDENCE // %.0f%%" % confidence
		hint_label.text = "APPROACH SIGNAL // E TO OBSERVE"
