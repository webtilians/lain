extends Node3D
## Visual 0.11: shadow role of an imported photoreal model.
## Each building keeps two instances of its GLB: the visible one lives under the
## cutaway "Upper" node and casts no shadow; a shadow-only twin stays outside it,
## so sunlight keeps the real roof shape even while the cutaway hides the house.
@export var shadow_only := false

func _ready() -> void:
	apply(self)

func apply(node: Node) -> void:
	if node is GeometryInstance3D:
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY if shadow_only else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for child in node.get_children():
		apply(child)
