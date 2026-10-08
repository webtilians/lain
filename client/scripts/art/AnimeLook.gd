extends RefCounted
## The anime look (ARTE.md), laid over the realistic materials and given back when it
## is switched off. As in most anime games, people are cel-shaded (a hard edge between
## light and shadow, a hard highlight, a soft coloured rim) while the places keep their
## painted light; everything gets thin ink lines along silhouettes and creases (a
## screen-space pass in front of the camera) and a little livelier colour.
## Presentation only.
const OUTLINE := preload("res://shaders/anime_outline.gdshader")
const KEPT := "anime_original"  # meta on each node: what it wore before

var cache := {}  # "<material id>/<person>" -> its anime version

func apply(root: Node, on: bool, outlines: bool) -> void:
	for node in root.find_children("*", "GeometryInstance3D", true, false):
		dress(node, on)
	for camera in root.find_children("*", "Camera3D", true, false):
		outline(camera, on and outlines)

func dress(node: Node, on: bool) -> void:
	if not (node is MeshInstance3D or node is MultiMeshInstance3D) or node.name == "AnimeOutline":
		return
	if not on:
		if node.has_meta(KEPT):
			var kept: Dictionary = node.get_meta(KEPT)
			node.material_override = kept.override
			if node is MeshInstance3D:
				for index in kept.surfaces.size():
					node.set_surface_override_material(index, kept.surfaces[index])
			node.remove_meta(KEPT)
		return
	if node.has_meta(KEPT):
		return
	var person := is_person(node)
	if not person:
		return  # places keep their light: toon shading on rooms loses the lamps' glow
	var kept := {"override": node.material_override, "surfaces": []}
	if node.material_override != null:
		node.material_override = material(node.material_override, person)
	elif node is MeshInstance3D and node.mesh != null:
		for index in node.mesh.get_surface_count():
			kept.surfaces.append(node.get_surface_override_material(index))
			var active: Material = node.get_active_material(index)
			if active is BaseMaterial3D:
				node.set_surface_override_material(index, material(active, person))
	elif node is MultiMeshInstance3D and node.multimesh != null and node.multimesh.mesh != null \
			and node.multimesh.mesh.get_surface_count() == 1:
		node.material_override = material(node.multimesh.mesh.surface_get_material(0), person)
	node.set_meta(KEPT, kept)

func material(original: Material, person: bool) -> Material:
	if not original is BaseMaterial3D or original.has_meta("anime"):
		return original
	var key := "%d/%s" % [original.get_instance_id(), person]
	if not cache.has(key):
		var anime: BaseMaterial3D = original.duplicate()
		anime.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON
		# Painted surfaces; only people keep a hard highlight (hair, eyes, jackets).
		anime.specular_mode = BaseMaterial3D.SPECULAR_TOON if person else BaseMaterial3D.SPECULAR_DISABLED
		anime.roughness = maxf(anime.roughness, 0.6)
		# Painted surfaces, not photographed ones: no relief from normal or depth maps (it would
		# also draw ink lines along every plank and joint).
		anime.normal_enabled = false
		anime.heightmap_enabled = false
		anime.ao_enabled = false
		anime.albedo_color = livelier(anime.albedo_color)
		if person:
			anime.rim_enabled = true
			anime.rim = 1.0
			anime.rim_tint = 0.25
		anime.set_meta("anime", true)
		cache[key] = anime
	return cache[key]

static func livelier(color: Color) -> Color:
	return Color.from_hsv(color.h, minf(1.0, color.s * 1.15), color.v, color.a)

static func is_person(node: Node) -> bool:
	var at := node
	while at != null:
		if at.is_in_group("player") or at is CharacterBody3D or ("actor_id" in at and str(at.get("actor_id")) != ""):
			return true
		at = at.get_parent()
	return false

func outline(camera: Camera3D, on: bool) -> void:
	var quad := camera.get_node_or_null("AnimeOutline") as MeshInstance3D
	if quad == null and on:
		quad = MeshInstance3D.new()
		quad.name = "AnimeOutline"
		var mesh := QuadMesh.new()
		mesh.size = Vector2(2, 2)
		mesh.flip_faces = true
		quad.mesh = mesh
		quad.extra_cull_margin = 16384.0
		quad.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		quad.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
		var lines := ShaderMaterial.new()
		lines.shader = OUTLINE
		quad.material_override = lines
		camera.add_child(quad)
	if quad != null:
		quad.visible = on

static func environment(e: Environment, on: bool) -> void:
	## A little more colour, and lights that glow a little more (where the quality has glow).
	e.adjustment_enabled = on
	if not on:
		return
	e.adjustment_saturation = 1.18
	e.adjustment_contrast = 1.06
	# Shadows are a coloured mid-tone, never black: more ambient light, leaning violet.
	e.ambient_light_color = e.ambient_light_color.lerp(Color("6a5a9a"), 0.35)
	e.ambient_light_energy *= 1.5
	e.tonemap_exposure += 0.15
	e.glow_bloom = maxf(e.glow_bloom, 0.06)
	e.glow_hdr_threshold = minf(e.glow_hdr_threshold, 0.85)
