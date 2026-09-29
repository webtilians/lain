extends SceneTree
## Offline authoring of the Visual 0.11 material library (headless is fine).
## Blender exports houses with named, untextured materials; each name below is
## saved as a .tres and mapped onto the GLBs through their .import files.
const TEX := "res://art/photoreal11/textures/"
const OUT := "res://art/photoreal11/materials/"

func _initialize() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	# Box-UV'd house parts: 1 UV unit = 1 m, so uv scale = 1 / physical texture size.
	save("wall_mortar", pbr("beige_wall_001", 3.0, Color("f2ede4"), .5))
	save("wall_siding", pbr("exterior_wall_cladding_03", 1.96, Color("d9d8d2"), .8))
	save("foundation", pbr("grey_plaster_02", 1.0, Color("a9a8a3"), .7))
	save("stone", pbr("grey_plaster_02", .5, Color("7c7a75"), .5))
	save("roof_slate", pbr("grey_roof_tiles_02", 1.5, Color("aeb3ba"), 1.0, .9))
	save("porch_tile", pbr("concrete_pavement", 1.8, Color("c9c5bd"), .6))
	save("door_wood", pbr("japanese_cedar_planks", 1.13, Color("8a6d58"), .5, .7))
	save("trim", plain(Color("3d3a37"), .55))
	save("soffit", plain(Color("c6c3ba"), .8))
	save("alu", plain(Color("c9cbcd"), .3, 1.0))
	save("alu_dark", plain(Color("3a342f"), .38, .9))
	save("brass", plain(Color("b88c4d"), .35, 1.0))
	save("metal_paint", plain(Color("46453f"), .45, .35))
	save("plastic_ivory", plain(Color("cdc8b8"), .45))
	save("rubber", plain(Color("141414"), .85))
	save("dark", plain(Color("080808"), .9))
	var glass := plain(Color("06080a"), .04)
	glass.metallic_specular = .65
	save("glass", glass)
	save("glass_frosted", plain(Color("a9b1b4"), .32))
	var lamp := plain(Color("ece5d4"), .3)
	lamp.emission_enabled = true
	lamp.emission = Color("ffd9a0")
	lamp.emission_energy_multiplier = .4
	save("lamp", lamp)
	# Utility pole.
	save("pole_concrete", pbr("grey_plaster_02", 1.0, Color("c9c8c2"), .6))
	save("galvanized", plain(Color("a3a7a7"), .42, .85))
	var porcelain := plain(Color("dcdcd6"), .18)
	porcelain.metallic_specular = .6
	save("porcelain", porcelain)
	save("transformer", plain(Color("9a9e9e"), .5, .45))
	save("cable_black", plain(Color("0b0b0b"), .55))
	# Parametric blocks (jp_block.py).
	save("concrete", pbr("grey_plaster_02", 1.5, Color("b3b2ad"), .6))
	save("roof_membrane", pbr("grey_plaster_02", 2.0, Color("7a7c79"), .4, .95))
	save("shutter", pbr("painted_metal_shutter", 2.0, Color("d8d8d4"), .8))
	save("corridor_floor", plain(Color("5b605c"), .7))
	save("door_steel", plain(Color("b9b5a6"), .4, .3))
	var awnings := {"awning_red": "7a2320", "awning_green": "234a35", "awning_blue": "25385e", "awning_brown": "5e4028"}
	for awning in awnings:
		save(awning, plain(Color(awnings[awning]), .88))
	save("sign_cream", plain(Color("d6cfbd"), .45))
	save("sign_dark", plain(Color("1c1e22"), .45))
	var neon := plain(Color("7fdcff"), .3)
	neon.emission_enabled = true
	neon.emission = Color("62d3ff")
	neon.emission_energy_multiplier = 2.5
	save("neon", neon)
	# World-triplanar ground and walls for scenery authored as boxes in Godot.
	save("road_asphalt", pbr("asphalt_02", 3.0, Color("b9b9b9"), .8, .95, true))
	save("sidewalk", pbr("concrete_pavement", 1.8, Color("d0ccc4"), .6, 1.0, true))
	save("block_wall", pbr("concrete_block_wall", 2.0, Color("d6d3cc"), 1.0, 1.0, true))
	print("PHOTOREAL11_MATERIALS saved")
	quit()

func pbr(asset: String, size_m: float, tint: Color, relief: float, rough: float = 1.0, world: bool = false) -> StandardMaterial3D:
	var root := TEX + asset + "/" + asset
	var m := StandardMaterial3D.new()
	m.albedo_texture = load(root + "_diff_2k.jpg")
	m.albedo_color = tint
	m.normal_enabled = true
	m.normal_texture = load(root + "_nor_gl_2k.jpg")
	m.normal_scale = relief
	var arm: Texture2D = load(root + "_arm_2k.jpg")
	m.roughness = rough
	m.roughness_texture = arm
	m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	m.ao_enabled = true
	m.ao_texture = arm
	m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	m.ao_light_affect = .1
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	if world:
		m.uv1_triplanar = true
		m.uv1_world_triplanar = true
		m.uv1_triplanar_sharpness = 8.0
		m.uv1_scale = Vector3.ONE / size_m
	else:
		m.uv1_scale = Vector3(1.0 / size_m, 1.0 / size_m, 1.0)
	return m

func plain(color: Color, rough: float, metal: float = 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	return m

func save(material_name: String, m: StandardMaterial3D) -> void:
	m.resource_name = "PR11_" + material_name
	var error := ResourceSaver.save(m, OUT + material_name + ".tres")
	if error != OK:
		push_error("Cannot save material " + material_name)
