extends SceneTree
## Offline authoring of the district material library (headless is fine).
## Blender exports buildings with named, untextured materials; each name below
## is saved as a .tres and mapped onto the GLBs through their .import files.
## Visual 0.12 restyles the library for the gothic night district: soot-stained
## concrete, dark brick, black iron, rust, lit windows, neon and wet ground.
const TEX := "res://art/photoreal11/textures/"
const GOTHIC := "res://art/gothic12/textures/"
const OUT := "res://art/photoreal11/materials/"

func _initialize() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	# Box-UV'd building parts: 1 UV unit = 1 m, so uv scale = 1 / physical texture size.
	save("wall_mortar", pbr(GOTHIC, "concrete_wall_006", 2.0, Color("8c8883"), .8, .85))
	save("wall_siding", pbr(GOTHIC, "dark_brick_wall", 1.05, Color("a29994"), 1.0, .9))
	save("foundation", pbr(GOTHIC, "castle_wall_slates", 2.5, Color("7d7873"), 1.0))
	save("stone", pbr(GOTHIC, "castle_wall_slates", 1.25, Color("6c6863"), 1.0))
	save("roof_slate", pbr(TEX, "grey_roof_tiles_02", 1.5, Color("5d5f66"), 1.0, .55))
	save("porch_tile", pbr(TEX, "concrete_pavement", 1.8, Color("77736e"), .6, .5))
	save("door_wood", pbr(GOTHIC, "black_painted_planks", 1.6, Color("b3aca6"), .8))
	save("concrete", pbr(GOTHIC, "concrete_wall_006", 1.5, Color("7b7874"), .7, .8))
	save("pole_concrete", pbr(TEX, "grey_plaster_02", 1.0, Color("75726d"), .6))
	# Untextured parts without UVs use world-triplanar projection.
	save("metal_paint", pbr(GOTHIC, "rust_coarse_01", 2.2, Color("9e8577"), .8, 1.0, true))
	save("shutter", pbr(GOTHIC, "rust_coarse_01", 1.6, Color("8d7a70"), .9, 1.0, true))
	save("rust", pbr(GOTHIC, "rust_coarse_01", 1.2, Color("a58a7c"), 1.0, 1.0, true))
	save("trim", plain(Color("151417"), .38, .6))
	save("iron", plain(Color("121114"), .32, .75))
	save("soffit", plain(Color("27232a"), .75))
	save("alu", plain(Color("45484e"), .32, .9))
	save("alu_dark", plain(Color("1a1918"), .38, .85))
	save("galvanized", plain(Color("505358"), .4, .85))
	save("transformer", plain(Color("46494c"), .5, .5))
	save("brass", plain(Color("7a5f30"), .38, 1.0))
	save("plastic_ivory", plain(Color("7f7a6d"), .5))
	save("rubber", plain(Color("0f0f0f"), .8))
	save("dark", plain(Color("060606"), .9))
	save("cable_black", plain(Color("070707"), .45))
	save("roof_membrane", plain(Color("232325"), .35))
	save("corridor_floor", plain(Color("2a2c2b"), .3))
	save("door_steel", plain(Color("2d2a2c"), .42, .55))
	var porcelain := plain(Color("b5b1a9"), .18)
	porcelain.metallic_specular = .6
	save("porcelain", porcelain)
	# Glass: most windows dark and wet-reflective, some lit from inside.
	var glass := plain(Color("040506"), .03)
	glass.metallic_specular = .7
	save("glass", glass)
	save("glass_frosted", plain(Color("30333a"), .3))
	save("glass_lit", glow(Color("ff9f52"), .75, Color("241509")))
	save("glass_lit_red", glow(Color("c8152c"), 1.0, Color("1e0508")))
	save("lamp", glow(Color("ffc47a"), 2.4, Color("e0d0b6")))
	# Neon and backlit signs.
	save("neon", glow(Color("46d3ff"), 3.6, Color("7fdcff")))
	save("neon_magenta", glow(Color("ff2fa0"), 3.6, Color("ff7cc6")))
	save("neon_red", glow(Color("ff2233"), 4.0, Color("ff6a70")))
	save("neon_amber", glow(Color("ffa830"), 3.2, Color("ffc877")))
	save("sign_cream", glow(Color("e8c89a"), .3, Color("b8a88f")))
	save("sign_dark", plain(Color("0b0b0e"), .4))
	var awnings := {"awning_red": "3e0a10", "awning_green": "13211a", "awning_blue": "121830", "awning_brown": "261811"}
	for awning in awnings:
		save(awning, plain(Color(awnings[awning]), .6))
	var screen := ShaderMaterial.new()
	screen.shader = load("res://shaders/gothic_screen.gdshader")
	save("screen", screen)
	# Interior fabrics used by the restyled rooms.
	save("damask", pbr(GOTHIC, "floral_jacquard", .38, Color("6e3a44"), .6, 1.0, true))
	save("leather_red", pbr(GOTHIC, "leather_red_02", .6, Color("9a2530"), .6, .7, true))
	save("black_wood", pbr(GOTHIC, "black_painted_planks", 1.6, Color("9d948c"), .8, .8, true))
	save("grate", pbr(GOTHIC, "metal_grate_rusty", .5, Color("a08a7e"), 1.0, 1.0, true))
	save("brick_world", pbr(GOTHIC, "dark_brick_wall", 1.05, Color("9a918c"), 1.0, .9, true))
	save("concrete_world", pbr(GOTHIC, "concrete_wall_006", 2.0, Color("85817c"), .8, .85, true))
	# World-mapped ground and walls for scenery authored as boxes in Godot.
	save("road_asphalt", wet_ground(TEX, "asphalt_02", 3.0, Color("6a6a6e")))
	save("sidewalk", wet_ground(TEX, "concrete_pavement", 1.8, Color("77736d")))
	save("block_wall", pbr(TEX, "concrete_block_wall", 2.0, Color("7d7a74"), 1.0, .85, true))
	print("PHOTOREAL11_MATERIALS saved")
	quit()

func pbr(root_dir: String, asset: String, size_m: float, tint: Color, relief: float, rough: float = 1.0, world: bool = false) -> StandardMaterial3D:
	var root := root_dir + asset + "/" + asset
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

func glow(emission: Color, energy: float, albedo: Color) -> StandardMaterial3D:
	var m := plain(albedo, .3)
	m.emission_enabled = true
	m.emission = emission
	m.emission_energy_multiplier = energy
	return m

func wet_ground(root_dir: String, asset: String, size_m: float, tint: Color) -> ShaderMaterial:
	var root := root_dir + asset + "/" + asset
	var noise := FastNoiseLite.new()
	noise.seed = 1212
	noise.frequency = 0.012
	noise.fractal_octaves = 3
	var puddles := NoiseTexture2D.new()
	puddles.width = 512
	puddles.height = 512
	puddles.seamless = true
	puddles.noise = noise
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/gothic_wet_ground.gdshader")
	m.set_shader_parameter("albedo_tex", load(root + "_diff_2k.jpg"))
	m.set_shader_parameter("normal_tex", load(root + "_nor_gl_2k.jpg"))
	m.set_shader_parameter("arm_tex", load(root + "_arm_2k.jpg"))
	m.set_shader_parameter("puddle_noise", puddles)
	m.set_shader_parameter("tint", tint)
	m.set_shader_parameter("tile_size", size_m)
	return m

func save(material_name: String, m: Material) -> void:
	m.resource_name = "PR11_" + material_name
	var error := ResourceSaver.save(m, OUT + material_name + ".tres")
	if error != OK:
		push_error("Cannot save material " + material_name)
