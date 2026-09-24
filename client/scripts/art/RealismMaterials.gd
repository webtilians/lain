extends RefCounted
## PBR materials shared by static scenery. Dimensions are in metres; normal,
## roughness and AO maps follow the SAME world-space projection as color.
const ROOT := "res://art/realism10/materials/"
var cache: Dictionary = {}

func pbr(asset: String, tint: Color, repeats: float, relief: float = .6, rough: float = 1.0) -> StandardMaterial3D:
	var key := asset + str(tint) + str(repeats) + str(relief) + str(rough)
	if cache.has(key):
		return cache[key]
	var material := StandardMaterial3D.new()
	material.resource_name = "PBR10_" + asset
	material.albedo_texture = load(ROOT + asset + "_Diffuse.jpg")
	material.normal_enabled = true
	material.normal_texture = load(ROOT + asset + "_nor_gl.png")
	material.normal_scale = relief
	material.roughness = rough
	material.roughness_texture = load(ROOT + asset + "_arm.jpg")
	material.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	material.ao_enabled = true
	material.ao_texture = material.roughness_texture
	material.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	material.ao_light_affect = .12
	material.albedo_color = tint
	material.uv1_triplanar = true
	material.uv1_world_triplanar = true
	material.uv1_scale = Vector3.ONE*repeats
	material.uv1_triplanar_sharpness = 8
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	cache[key] = material
	return material

func replacement(original: Material, label: String, indoor: bool) -> Material:
	if original == null:
		return null
	var name_value := original.resource_name.to_lower()
	if name_value.begins_with("pbr10_"):
		return original
	if original is ShaderMaterial:
		if original.shader.resource_path.ends_with("reference_surface.gdshader"):
			var tex: Texture2D = original.get_shader_parameter("albedo_map")
			if tex != null and tex.resource_path.contains("asphalt"):
				return pbr("aerial_asphalt_01", Color("b1b4b8"), .08, .8, .85)
			var tint = original.get_shader_parameter("tint")
			return pbr("plastered_wall_02", Color(tint).lightened(.14), .45, .48)
		return original
	if not original is StandardMaterial3D:
		return original
	var base := original as StandardMaterial3D
	var texture_path := base.albedo_texture.resource_path if base.albedo_texture != null else ""
	if name_value in ["road","road09"]:
		return pbr("aerial_asphalt_01",Color("afb3b7"),.08,.8,.85)
	if name_value.begins_with("wall_") or (indoor and ("Wall" in label or "plaster" in texture_path)):
		return pbr("plastered_wall_02",base.albedo_color.lightened(.20),.45,.45)
	if name_value in ["stone","pavement","trim","mortar"]:
		return pbr("concrete_floor_02",base.albedo_color.lightened(.19),.42,.55,.92)
	if name_value in ["wood","cedar"] or (indoor and ("Desk" in label or "Shelf" in label or ("Floor" in label and not "Station" in label) or "Table" in label or "Cabinet" in label) and not "Label" in label):
		return pbr("wood_floor",Color("aaabac") if "Floor" in label else base.albedo_color.lightened(.22),.44,.45,.85)
	if name_value in ["metal","steel"]:
		var key := "metal"+str(base.albedo_color)
		if not cache.has(key):
			var m: StandardMaterial3D = base.duplicate()
			m.albedo_texture = null
			m.albedo_color = base.albedo_color.lightened(.07)
			m.metallic = .72
			m.roughness = .44
			m.resource_name = "PBR10_metal"
			cache[key] = m
		return cache[key]
	if name_value in ["glass","shopglass"]:
		var key := "glass"+str(base.transparency)
		if not cache.has(key):
			var m: StandardMaterial3D = base.duplicate()
			m.metallic = 0.0
			m.roughness = .30
			m.metallic_specular = .5
			m.albedo_color = Color(.32,.40,.45,base.albedo_color.a)
			m.resource_name = "PBR10_glass"
			cache[key] = m
		return cache[key]
	if name_value in ["leaf","leaves"]:
		var m: StandardMaterial3D = base.duplicate()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
		m.backlight_enabled = true
		m.backlight = Color(.25,.32,.14)
		m.roughness = .83
		m.resource_name = "PBR10_foliage"
		return m
	if name_value.begins_with("tile") or name_value == "roof":
		var m: StandardMaterial3D = base.duplicate()
		m.roughness = .72
		m.normal_enabled = true
		m.normal_texture = load(ROOT+"plastered_wall_02_nor_gl.png")
		m.normal_scale = .2
		m.resource_name = "PBR10_ceramic"
		return m
	return original
